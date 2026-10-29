"""Dimensioned verification, independent package, installed apps and real MCP."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv

from build_invitation_kit import build
from isolated_candidate import clean_env
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from conformance.assessment import assess, digest
from conformance.core_contract import ContractError
from conformance.runner import CHECKERS, verify_bundle
from check_h02 import request as routing_request, result as routing_result
from safe_test_result import DiagnosticResult

PROFILES = {'routing.basic': ('basic-input.json', 18), 'worker.scheduling': ('worker-input.json', 7),
            'inventory.replenishment': ('inventory-input.json', 16)}


class VerificationScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ocp-verification-'); cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name).resolve(); cls.kit = cls.work / 'kit'
        build(cls.kit, target_kind='python')
        home = cls.work / 'home'; home.mkdir()
        cls.env = clean_env(home); cls.env.update(PATH=os.defpath, PIP_NO_INDEX='1', PIP_FIND_LINKS=str(ROOT / '.harness/work/wheels'))
        cls.python = cls.work / 'agent/bin/python'
        cls.run_ok([sys._base_executable, '-B', 'start.py', '--mcp', '--venv', cls.python.parent.parent])
        cls.reports = {}
        for profile, (name, _) in PROFILES.items():
            cls.reports[profile] = json.loads(cls.run_ok([cls.python, '-I', '-B', 'multi_app.py', '--profile', profile,
                '--input', name, '--request-id', 'scope-' + profile]).stdout)
        cls.checkpython = cls.work / 'checker only/bin/python'
        venv.EnvBuilder(with_pip=True).create(cls.checkpython.parent.parent)
        cls.run_ok([cls.checkpython, '-B', '-m', 'pip', 'install', '--no-index', '--no-cache-dir', '--no-compile',
                    '--find-links', ROOT / '.harness/work/wheels', cls.kit / 'ocp_conformance_candidate-0.1.0-py3-none-any.whl'])

    @classmethod
    def run_ok(cls, argv, expected=0):
        result = subprocess.run([str(x) for x in argv], cwd=cls.kit, env=cls.env, text=True, capture_output=True, timeout=180)
        if result.returncode != expected: raise AssertionError(result.stdout[-2500:] + result.stderr[-2500:])
        return result

    def worker(self):
        case = deepcopy(self.reports['worker.scheduling'])
        return case['request'], case['response']

    def test_01_installed_three_domain_dimensions(self):
        for profile, (_, cost) in PROFILES.items():
            report = self.reports[profile]['verification']; checks = report['checks']
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(checks['feasibility']['status'], 'PASS')
            self.assertEqual(checks['objective_recomputation']['value'], cost)
            self.assertEqual(checks['execution_attestation']['status'], 'NOT_CHECKED')
            self.assertEqual(checks['optimality']['status'], 'NOT_CLAIMED' if profile == 'routing.basic' else 'PASS')

    def test_02_solution_only_is_partial_not_proven(self):
        request, result = self.worker(); report = assess(request, result, mode='solution')
        self.assertEqual(report['status'], 'PARTIAL')
        self.assertEqual(report['checks']['feasibility']['status'], 'PASS')
        self.assertEqual(report['checks']['optimality']['status'], 'NOT_CHECKED')
        self.assertEqual(report['response_status'], 'optimal')

    def test_03_wrong_cost_fails(self):
        request, result = self.worker(); result['metrics'][0]['value'] += 1
        report = assess(request, result)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['checks']['structure_and_semantics']['reason'], 'EVALUATION_MISMATCH')

    def test_04_missing_assignment_fails(self):
        request, result = self.worker(); result['solution']['assignments'].pop()
        self.assertEqual(assess(request, result)['status'], 'FAIL')

    def test_05_bad_proof_keeps_valid_solution_separate(self):
        request, result = self.worker(); result['proof']['evidence']['objective'] += 1
        report = assess(request, result)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['checks']['feasibility']['status'], 'PASS')
        self.assertEqual(report['checks']['optimality']['status'], 'FAIL')

    def test_06_timeout_unknown_no_cost_or_infeasibility(self):
        request, result = self.worker()
        result.update(status='unknown', termination='time_limit', solution=None, proof=None, metrics=[], constraints=[])
        report = assess(request, result)
        self.assertEqual(report['status'], 'PASS')
        self.assertIsNone(report['checks']['objective_recomputation']['value'])
        self.assertEqual(report['checks']['feasibility']['status'], 'NOT_APPLICABLE')
        self.assertEqual(report['checks']['infeasibility']['status'], 'NOT_CLAIMED')

    def test_07_actual_infeasible_claim_checked(self):
        problem = json.loads((self.kit / 'worker-input.json').read_text())
        for worker in problem['workers']: worker['max_minutes'] = 0
        path = self.work / 'no-capacity.json'; path.write_text(json.dumps(problem))
        report = json.loads(self.run_ok([self.python, '-I', '-B', 'multi_app.py', '--profile', 'worker.scheduling',
            '--input', path, '--request-id', 'infeasible']).stdout)
        self.assertEqual(report['response']['status'], 'infeasible')
        self.assertEqual(report['verification']['checks']['infeasibility']['status'], 'PASS')
        self.assertIsNone(report['verification']['checks']['objective_recomputation']['value'])

    def test_08_large_solution_valid_but_optimality_out_of_scope(self):
        problem = deepcopy(routing_request()['input'])
        problem['visits'] = [{'id': 'v' + str(i), 'demand': 1} for i in range(8)]
        problem['vehicles'] = [{'id': 'truck', 'capacity': 8}]
        ids = ['hub'] + [v['id'] for v in problem['visits']]
        problem['matrix'].update(node_ids=ids, values=[[int(i != j) for j in range(9)] for i in range(9)])
        request = routing_request(problem); result = routing_result(request)
        result.update(status='optimal', solution={'routes': [{'vehicle_id': 'truck', 'visits': ids[1:]}]},
                      proof={'claim': 'optimal', 'method': 'exhaustive-enumeration', 'scope': 'synthetic fixture', 'evidence': {'objective': 9}})
        result['metrics'][0]['value'] = 9
        report = assess(request, result)
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['checks']['feasibility']['status'], 'PASS')
        self.assertEqual(report['checks']['objective_recomputation']['value'], 9)
        self.assertEqual(report['checks']['optimality']['reason'], 'ORACLE_SCOPE_EXCEEDED')
        self.assertEqual(assess(request, result, mode='solution')['status'], 'PARTIAL')
        with self.assertRaises(ContractError): CHECKERS[('routing.basic', '0.1.0')](request, result)
        result.update(status='feasible', proof=None)
        self.assertEqual(assess(request, result)['status'], 'PASS')

    def test_09_checker_only_package_without_any_provider(self):
        path = self.work / 'three-transcripts.json'; path.write_text(json.dumps(self.reports))
        code = '''import importlib.util,json,sys
assert all(importlib.util.find_spec(x) is None for x in ('ocp_candidate','ocp_routing','ocp_planning','ocp_runtime','ortools','mcp'))
from conformance.assessment import assess
for value in json.load(open(sys.argv[1])).values():
 assert assess(value['request'],value['response'])['status']=='PASS'
'''
        self.run_ok([self.checkpython, '-I', '-B', '-c', code, path])

    def test_10_actual_mcp_context_guidance_not_check_results(self):
        code = '''import asyncio,os,sys
from mcp import Client,StdioServerParameters
async def main():
 async with Client(StdioServerParameters(command=sys.executable,args=['-I','-B','-m','ocp_runtime.mcp_server','--profile','all'],env={'PATH':os.defpath}),read_timeout_seconds=60) as host:
  assert len((await host.list_tools()).tools)==6
  for profile in ('routing.basic','worker.scheduling','inventory.replenishment'):
   guide=(await host.call_tool('ocp_context',{'profile':profile})).structured_content
   value=guide['verification_guidance']
   assert value['report_version']=='0.1.0'
   assert set(value['dimensions'])=={'feasibility','objective_recomputation','optimality','infeasibility','execution_attestation'}
   assert 'status' not in value and 'checks' not in value
   assert 'no check or solve' in value['execution']
asyncio.run(main())
'''
        self.run_ok([self.python, '-I', '-B', '-c', code])

    def test_11_actual_mcp_smoke_has_dimensioned_check(self):
        for profile, (name, cost) in PROFILES.items():
            report = json.loads(self.run_ok([self.python, '-I', '-B', 'local_agent.py', 'smoke', '--profile', profile,
                '--input', name, '--request-id', 'smoke-' + profile]).stdout)
            self.assertEqual(report['verification']['checks']['objective_recomputation']['value'], cost)
            self.assertEqual(report['execute_calls'], 1); self.assertEqual(report['model_calls'], 0)

    def test_12_checker_cli_exit_status_and_hash(self):
        request, result = self.worker(); path = self.work / 'transcript.json'
        path.write_text(json.dumps({'request': request, 'response': result, 'verification': {'status': 'forged'}}))
        before = path.read_bytes()
        for mode, expected, status in [('full', 0, 'PASS'), ('solution', 2, 'PARTIAL')]:
            report = json.loads(self.run_ok([self.checkpython, '-I', '-B', '-m', 'conformance.assessment', '--transcript', path, '--mode', mode], expected).stdout)
            self.assertEqual(report['status'], status)
            self.assertEqual(report['response_sha256'], digest(result))
        self.assertEqual(path.read_bytes(), before)

    def test_13_unsupported_profile_and_identity_rejected(self):
        request, result = self.worker(); request['domain_profile']['version'] = '9.0.0'
        self.assertEqual(assess(request, result)['status'], 'FAIL')
        request, result = self.worker(); result['request_id'] = 'different'
        self.assertEqual(assess(request, result)['status'], 'FAIL')

    def test_14_original_never_mutated(self):
        request, result = self.worker(); original = deepcopy((request, result))
        for mode in ('full', 'solution'):
            report = assess(request, result, mode=mode)
            self.assertEqual((request, result), original)
            self.assertEqual(report['response_sha256'], digest(original[1]))

    def test_15_old_runner_and_measurement_compatible(self):
        request, result = self.worker(); artifact = b'synthetic artifact not engine execution evidence'
        bundle = {'artifact_sha256': hashlib.sha256(artifact).hexdigest(), 'implementation': result['provenance']['implementation'],
                  'cases': [{'id': 'existing', 'request': request, 'response': result}]}
        report = verify_bundle(bundle, artifact)
        self.assertEqual(set(report), {'status', 'report', 'scope'})
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(CHECKERS[('worker.scheduling', '0.1.0')](request, result)['total_cost'], 7)

    def test_16_bad_original_proof_not_hidden_by_solution_mode(self):
        request, result = self.worker(); result['proof'] = None
        self.assertEqual(assess(request, result, mode='solution')['status'], 'FAIL')

    def test_17_omitted_constraint_and_null_to_zero_rejected(self):
        request, result = self.worker(); result['constraints'].pop()
        self.assertEqual(assess(request, result)['status'], 'FAIL')
        request, result = self.worker(); result['metrics'][0].update(status='not_evaluated', value=0, reason='not checked')
        self.assertEqual(assess(request, result)['status'], 'FAIL')

    def test_18_profile_bound_and_unknown_mode_rejected(self):
        request, result = self.worker(); request['input']['tasks'] *= 3
        self.assertEqual(assess(request, result)['status'], 'FAIL')
        with self.assertRaises(ValueError): assess(request, result, mode='guess')

    def test_19_other_metric_names_preserve_existing_profiles(self):
        fixture = json.loads((ROOT / 'cases/assignment/fixture.json').read_text())
        report = assess(fixture['request'], fixture['result'])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['checks']['objective_recomputation']['value'], fixture['expected_cost'])
        coordinate = json.loads((ROOT / 'cases/routing/coordinates.json').read_text())
        request = routing_request(coordinate['input']); result = routing_result(request)
        request['domain_profile']['id'] = result['domain_profile']['id'] = 'routing.coordinates'
        result['solution'] = coordinate['witness']; result['metrics'][0]['value'] = coordinate['expected_total_m']
        for item in result['metrics'] + result['constraints']:
            item['definition'] = item['definition'].replace('routing.basic.', 'routing.coordinates.')
        report = assess(request, result)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['checks']['objective_recomputation']['value'], coordinate['expected_total_m'])
        result['metrics'][0]['value'] += 1
        self.assertEqual(assess(request, result)['status'], 'FAIL')


if __name__ == '__main__':
    result = unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(VerificationScope))
    ok = result.wasSuccessful() and result.testsRun >= 18 and not result.skipped
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'tests_run': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
                      'failure_diagnostics': result.diagnostics, 'model_calls': 0,
                      'scope': 'Independent installed checker, actual app/MCP execution, proof-scope and mutation checks; no model or external acceptance'}))
    sys.exit(0 if ok else 1)
