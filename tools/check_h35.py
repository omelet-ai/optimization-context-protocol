"""Fresh installed CSV worker scenario app, input rejection and independent checks."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from build_invitation_kit import build
from isolated_candidate import clean_env
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from safe_test_result import DiagnosticResult


class WorkerAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ocp-worker-analysis-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name).resolve()
        cls.kit = cls.work / 'python kit'
        build(cls.kit, target_kind='python')
        home = cls.work / 'empty home'; home.mkdir()
        cls.env = clean_env(home)
        cls.env.update(PATH=os.defpath, PIP_NO_INDEX='1', PIP_FIND_LINKS=str(ROOT / '.harness/work/wheels'))
        cls.python = cls.work / 'installed/bin/python'
        cls.run_ok([sys._base_executable, '-B', 'install.py', '--profile', 'byo', '--venv', cls.python.parent.parent])
        cls.run_ok([cls.python, '-I', '-B', '-c', 'import importlib.util; assert all(importlib.util.find_spec(x) is None for x in ("ortools", "mcp"))'])
        sys.path.insert(0, str(cls.kit / 'ocp_candidate-0.1.0-py3-none-any.whl'))
        spec = importlib.util.spec_from_file_location('worker_analysis', cls.kit / 'worker_analysis.py')
        cls.app = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.app)
        cls.files = [cls.kit / ('worker-' + name) for name in ('workers.csv', 'tasks.csv', 'costs.csv', 'scenarios.json')]
        cls.output = cls.work / 'first analysis'
        cls.result = json.loads(cls.run_ok([cls.python, '-I', '-B', 'worker_analysis.py', '--workers', cls.files[0],
            '--tasks', cls.files[1], '--costs', cls.files[2], '--scenarios', cls.files[3], '--output', cls.output, '--run-id', 'fresh']).stdout)

    @classmethod
    def run_ok(cls, argv, expected=0):
        result = subprocess.run([str(x) for x in argv], cwd=cls.kit, env=cls.env, text=True, capture_output=True, timeout=180)
        if result.returncode != expected:
            raise AssertionError(result.stdout[-2000:] + result.stderr[-2000:])
        return result

    def reject(self, index, transform, expected=None):
        with tempfile.TemporaryDirectory(dir=self.work) as directory:
            files = []
            for source in self.files:
                dest = Path(directory) / source.name; shutil.copy2(source, dest); files.append(dest)
            files[index].write_text(transform(files[index].read_text()))
            output = Path(directory) / 'output'
            with patch.object(self.app.Client, 'execute', side_effect=AssertionError('Must not execute')) as execute:
                with self.assertRaises(self.app.AnalysisError) as error:
                    self.app.analyze(*files, output, 'invalid')
                execute.assert_not_called()
            if expected: self.assertIn(expected, str(error.exception))
            self.assertFalse(output.exists())

    def test_01_installed_real_three_scenarios(self):
        cases = self.result['scenarios']
        self.assertEqual([c['response']['status'] for c in cases], ['optimal', 'optimal', 'infeasible'])
        self.assertEqual([c['independent_check']['total_cost'] if c['independent_check'] else None for c in cases], [12, 14, None])
        self.assertEqual([c['comparison']['cost_delta'] for c in cases], [0, 2, None])
        self.assertEqual(self.result['execute_calls'], 3); self.assertEqual(self.result['model_calls'], 0)

    def test_02_provenance_and_readable_assignments(self):
        import hashlib
        self.assertEqual(list(self.result['input_sha256'].values()), [hashlib.sha256(p.read_bytes()).hexdigest() for p in self.files])
        text = (self.output / 'analysis.md').read_text()
        self.assertIn('not comparable', text); self.assertIn('| receive | 0–60 |', text)
        self.assertEqual(json.loads((self.output / 'analysis.json').read_text()), self.result)
        self.assertEqual(len({c['request']['request_id'] for c in self.result['scenarios']}), 3)

    def test_03_all_scenarios_validate_before_execution(self):
        self.reject(3, lambda s: s.replace('"value": 9', '"value": -1'), 'INPUT_REJECTED')

    def test_04_missing_cost_not_inferred(self):
        self.reject(2, lambda s: s.replace('receive,alice,2\n', ''), 'MISSING_COST')

    def test_05_duplicate_and_unexpected_cost(self):
        self.reject(2, lambda s: s + 'receive,alice,2\n', 'DUPLICATE_COST')
        self.reject(2, lambda s: s + 'receive,casey,2\n', 'UNEXPECTED_COST')

    def test_06_units_and_unknown_changes(self):
        self.reject(3, lambda s: s.replace('minute', 'hour'), 'INPUT_REJECTED')
        self.reject(3, lambda s: s.replace('set_cost', 'add_fairness'), 'UNSUPPORTED_CHANGE')

    def test_07_unknown_worker_and_duplicate_tasks(self):
        self.reject(1, lambda s: s.replace('alice|bob', 'ghost|bob'), 'INVALID_ELIGIBILITY')
        self.reject(1, lambda s: s + 'receive,0,60,alice|bob\n', 'DUPLICATE_TASK')

    def test_08_output_preserved_without_execution(self):
        before = (self.output / 'analysis.json').read_bytes()
        with patch.object(self.app.Client, 'execute') as execute:
            with self.assertRaisesRegex(self.app.AnalysisError, 'OUTPUT_EXISTS'):
                self.app.analyze(*self.files, self.output, 'repeat')
            execute.assert_not_called()
        self.assertEqual((self.output / 'analysis.json').read_bytes(), before)

    def test_09_incompatible_costs_and_null_not_compared(self):
        first = self.result['scenarios'][0]
        for field in ('definition', 'unit'):
            changed = deepcopy(first); changed['response']['metrics'][0][field] = 'different'
            self.assertIsNone(self.app.comparison(first, changed)['cost_delta'])
        self.assertIsNone(self.app.comparison(first, self.result['scenarios'][2])['cost_delta'])

    def test_10_checker_detects_bad_solution_and_cost(self):
        from conformance.core_contract import ContractError
        for change in ('cost', 'solution'):
            case = deepcopy(self.result['scenarios'][0])
            if change == 'cost': case['response']['metrics'][0]['value'] += 1
            else: case['response']['solution']['assignments'].pop()
            with self.assertRaises(ContractError): self.app.verify_result(case['request'], case['response'])

    def test_11_each_scenario_starts_from_baseline(self):
        cases = self.result['scenarios']
        self.assertEqual(cases[2]['request']['input']['tasks'][0]['costs']['alice'], 2)
        self.assertEqual(cases[1]['request']['input']['tasks'][0]['costs']['alice'], 9)

    def test_12_exact_documented_command(self):
        import re
        text = (self.kit / 'WORKER_ANALYSIS.md').read_text()
        command = re.search(r'<!-- ocp:worker-analysis -->\s*```sh\n(.*?)\n```', text, re.S)[1]
        (self.kit / '.agent').symlink_to(self.python.parent.parent)
        result = json.loads(self.run_ok(['/bin/sh', '-eu', '-c', command]).stdout)
        self.assertEqual(result['scenarios'][0]['independent_check']['total_cost'], 12)


if __name__ == '__main__':
    result = unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkerAnalysis))
    ok = result.wasSuccessful() and result.testsRun >= 12 and not result.skipped
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'tests_run': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
                      'failure_diagnostics': result.diagnostics, 'model_calls': 0,
                      'scope': 'Fresh installed CSV worker analysis, actual solves and independent checks; synthetic data, no external users'}))
    sys.exit(0 if ok else 1)
