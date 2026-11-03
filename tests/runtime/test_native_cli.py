"""Installed CLI, real stdio probes and intentionally broken startup checks."""
import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import venv

from mcp import Client, StdioServerParameters
from ocp_runtime import native_cli

ARGS = None
EVENTS = []


def environment_path(value):
    # macOS /tmp and /private/tmp identify the same directory. Resolve its
    # parent only: resolving the Python symlink would hide a wrong venv.
    path = Path(value)
    return str(path.parent.resolve()/path.name)


def comparable_config(value):
    value = deepcopy(value)
    for server in value['mcpServers'].values():
        server['command'] = environment_path(server['command'])
    return value


class NativeCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable = Path(sys.executable).parent / 'ocp-native'
        cls.environment = {'PATH': os.defpath, 'HOME': str(ARGS.output),
            'PYTHONDONTWRITEBYTECODE': '1', 'PIP_CONFIG_FILE': os.devnull}
        destination = ARGS.output/'without-checker'
        venv.EnvBuilder(with_pip=True, symlinks=True).create(destination)
        cls.no_checker = destination/'bin/python'
        manifest = json.loads((ARGS.kit/'manifest.json').read_text())
        command = [str(cls.no_checker), '-B', '-m', 'pip', 'install', '--no-index', '--no-cache-dir', '--no-compile',
                   '-c', str(ARGS.kit/'constraints.txt')]
        for path in ARGS.wheelhouse:
            command += ['--find-links', str(path)]
        command += [str(ARGS.kit/manifest['python_wheels']['contracts']),
                    str(ARGS.kit/manifest['python_wheels']['sdk'])+'[reference,native,mcp]']
        completed = subprocess.run(command, env=cls.environment, capture_output=True, text=True, timeout=120)
        (ARGS.output/'without-checker-install.log').write_text(completed.stdout+completed.stderr)
        if completed.returncode:
            raise RuntimeError('NO_CHECKER_INSTALL_FAILED: '+completed.stderr[-2000:])

    def command(self, arguments, expected=0, python=None):
        command = ([str(python), '-I', '-B', '-m', 'ocp_runtime.native_cli'] if python else [str(self.executable)])
        result = subprocess.run(command+arguments, cwd=ARGS.output, env=self.environment,
                                capture_output=True, text=True, timeout=50)
        EVENTS.append({'argv': command+arguments, 'returncode': result.returncode,
                       'stdout': result.stdout, 'stderr': result.stderr})
        self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
        return result

    def test_help_and_version_without_optional_mcp(self):
        self.assertIn('doctor', self.command(['--help']).stdout)
        self.assertEqual(self.command(['--version']).stdout.strip(), '0.2.0a2')
        self.assertIn('doctor', self.command(['--help'], python=ARGS.without_mcp_python).stdout)

    def test_config_and_legacy_wrapper(self):
        default = json.loads(self.command(['config']).stdout)
        self.assertEqual(environment_path(default['mcpServers']['ocp-native-local']['command']), environment_path(sys.executable))
        named = json.loads(self.command(['config', '--name', 'my-optimization', '--verification']).stdout)
        self.assertEqual(named['mcpServers']['my-optimization']['args'][-1], '--verification')
        wrapper = subprocess.run([sys.executable, '-I', '-B', str(ARGS.kit/'mcp_config.py')],
            cwd=ARGS.output, env=self.environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(wrapper.returncode, 0, wrapper.stderr)
        self.assertEqual(comparable_config(json.loads(wrapper.stdout)), comparable_config(default))

    def test_evidence_config_implies_verification_and_wrapper_matches(self):
        selected = json.loads(self.command(['config', '--evidence']).stdout)
        self.assertEqual(selected['mcpServers']['ocp-native-local']['args'][-2:], ['--verification','--evidence'])
        both = json.loads(self.command(['config', '--verification','--evidence']).stdout)
        self.assertEqual(selected, both)
        wrapper = subprocess.run([sys.executable,'-I','-B',str(ARGS.kit/'mcp_config.py'),'--evidence'],
            cwd=ARGS.output,env=self.environment,capture_output=True,text=True,timeout=30)
        self.assertEqual(wrapper.returncode, 0, wrapper.stderr)
        self.assertEqual(comparable_config(json.loads(wrapper.stdout)), comparable_config(selected))
        module = json.loads(self.command(['config','--evidence'],python=sys.executable).stdout)
        self.assertEqual(comparable_config(module), comparable_config(selected))

    def test_invalid_config_and_timeout_argument(self):
        failed = self.command(['config', '--name', 'bad/name'], expected=1)
        self.assertEqual(failed.stdout, '')
        self.assertEqual(json.loads(failed.stderr)['code'], 'INVALID_SERVER_NAME')
        self.command(['doctor', '--timeout', '0'], expected=2)

    def test_routing_selection_config_and_probe(self):
        selected = json.loads(self.command(['config', '--domain', 'routing-basic', '--evidence']).stdout)
        self.assertEqual(selected['mcpServers']['ocp-native-local']['args'][-2:], ['--domain', 'routing-basic'])
        for flags, count in [([], 8), (['--verification'], 9), (['--evidence'], 11)]:
            report = json.loads(self.command(['doctor', '--domain', 'routing-basic', '--probe', *flags]).stdout)
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(report['domains'], ['routing-basic'])
            self.assertEqual([c['domain'] for c in report['probe']['catalogs']], ['routing-basic'])
            self.assertEqual(len(report['probe']['tools']), count)

    def test_invalid_domain_selection_never_emits_config(self):
        for names in [('unknown',), ('routing-basic', 'routing-basic')]:
            flags = [part for name in names for part in ('--domain', name)]
            failed = self.command(['config', *flags], expected=1)
            self.assertEqual(failed.stdout, '')
            self.assertIn('INVALID_DOMAIN_SELECTION', failed.stderr)
            report = json.loads(self.command(['doctor', '--probe', *flags], expected=1).stdout)
            self.assertEqual(report['probe']['status'], 'NOT_RUN')

    def test_domain_selection_validates_before_provider_creation(self):
        from ocp_runtime.native_server import reference_domains
        with patch('ocp_runtime.providers.make_provider') as factory:
            for names in [[], 'routing-basic', ['unknown'], ['routing-basic', 'routing-basic']]:
                with self.assertRaisesRegex(ValueError, 'INVALID_DOMAIN_SELECTION'):
                    reference_domains(names)
            factory.assert_not_called()
        self.assertEqual([r.domain.problem_type for r in reference_domains(['routing-basic'])], ['routing-basic'])

    def test_multiple_nonrouting_domains_keep_canonical_order(self):
        report = json.loads(self.command(['doctor', '--probe', '--evidence',
            '--domain', 'inventory-replenishment', '--domain', 'worker-scheduling']).stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['domains'], ['worker-scheduling', 'inventory-replenishment'])
        self.assertEqual([c['domain'] for c in report['probe']['catalogs']], report['domains'])

    def test_probe_rejects_broader_than_selected_server(self):
        all_domains = native_cli.configuration()
        with patch.object(native_cli, 'configuration', return_value=all_domains):
            report = native_cli.doctor(probe=True, domains=['routing-basic'])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['probe']['code'], 'MCP_DOMAIN_MISMATCH')

    def test_static_doctor(self):
        report = json.loads(self.command(['doctor', '--verification']).stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['probe']['status'], 'NOT_RUN')
        self.assertEqual(len(report['domains']), 3)
        self.assertEqual(report['solve_calls'], 0)

    def test_static_evidence_doctor_distinguishes_versions_without_probe(self):
        report = json.loads(self.command(['doctor','--evidence']).stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['probe']['status'], 'NOT_RUN')
        self.assertEqual(report['features']['expected_tool_count'], 11)
        self.assertEqual(report['features']['evidence'], {'enabled': True, 'version': '0.5.0'})
        self.assertEqual(report['features']['verification'], {'enabled': True, 'version': '0.1.0'})
        self.assertEqual(report['contracts'], {'native':'1','domain_payload':'ocp-core-request/0.1.0'})
        self.assertEqual(len(report['profiles']), 3)
        self.assertEqual(report['solve_calls'], 0)
        self.assertEqual(report['model_calls'], 0)

    def test_real_discovery_with_eight_nine_and_eleven_tools(self):
        for flags, count in [([], 8), (['--verification'], 9), (['--evidence'], 11)]:
            with self.subTest(flags=flags):
                report = json.loads(self.command(['doctor', '--probe', *flags]).stdout)
                self.assertEqual(report['status'], 'PASS')
                self.assertEqual(report['probe']['status'], 'PASS')
                self.assertEqual(len(report['probe']['tools']), count)
                self.assertEqual(len(report['probe']['catalogs']), 3)
                self.assertEqual(report['solve_calls'], 0)
                self.assertEqual(report['features']['expected_tool_count'], count)
                if '--evidence' in flags:
                    self.assertEqual(report['probe']['feature_versions'], {'verification':'0.1.0','evidence':'0.5.0'})

    def test_discovery_rejects_wrong_feature_version_and_scope(self):
        from ocp_runtime.native_evidence import EvidenceService
        from ocp_runtime.native_server import reference_domains
        from foundry_capability_contract import MemoryJobStore
        clients = {item.domain.problem_type:item.domain for item in reference_domains()}
        service = EvidenceService(clients, MemoryJobStore())
        original = {'verification':{'version':'0.1.0'},'evidence':service.context()}
        kwargs = {'verification':True,'evidence':True,'domains':list(clients)}
        native_cli.check_features(original, **kwargs)
        for field, value in [('version','0.0.0'),('capability_scope',None)]:
            bad=deepcopy(original); bad['evidence'][field]=value
            with self.assertRaisesRegex(native_cli.SetupError,'MCP_FEATURE_MISMATCH'):
                native_cli.check_features(bad, **kwargs)
        for field, value in [('configured_domains',['invented']),('selected_domain','worker-scheduling'),
                             ('selected_profile',{'id':'invented','version':'1'}),('catalog_scope','SELECTED_DOMAIN_ONLY')]:
            bad=deepcopy(original); bad['evidence']['capability_scope'][field]=value
            with self.assertRaisesRegex(native_cli.SetupError,'MCP_FEATURE_MISMATCH'):
                native_cli.check_features(bad, **kwargs)
        bad=deepcopy(original); del bad['evidence']['capability_scope']['selected_domain']
        with self.assertRaises(native_cli.SetupError): native_cli.check_features(bad, **kwargs)
        with self.assertRaises(native_cli.SetupError): native_cli.check_features(original, domains=list(clients))

    def test_console_serve_keeps_stdout_as_protocol(self):
        async def exercise():
            params = StdioServerParameters(command=str(self.executable), args=['serve', '--verification'], env=self.environment)
            async with Client(params, read_timeout_seconds=30) as client:
                self.assertEqual(len((await client.list_tools()).tools), 9)
                async def call(name, arguments):
                    response = await client.call_tool(name, arguments)
                    self.assertFalse(response.is_error)
                    value = response.structured_content
                    EVENTS.append({'entrypoint': 'ocp-native serve --verification', 'tool': name,
                                   'arguments': arguments, 'result': value})
                    return value
                context = await call('ocp_native_context', {'domain': 'worker-scheduling'})
                self.assertEqual(len(context['availableDomains']), 3)
                catalog = context['catalog']
                await call('ocp_native_requirements', {'domain': 'worker-scheduling', 'selection': catalog['selectionTemplate']})
                request = catalog['requestTemplate']
                request.update(request_id='cli-smoke', input=json.loads((ARGS.kit/'worker-input.json').read_text()))
                validation = await call('ocp_native_validate', {'domain': 'worker-scheduling', 'problem': request})
                self.assertTrue(validation['valid'])
                job = (await call('ocp_native_submit', {'domain': 'worker-scheduling', 'problem': request,
                                                     'idempotency_key': 'cli-smoke'}))['job']
                started = time.monotonic()
                while job['status'] in ('queued', 'running'):
                    self.assertLess(time.monotonic()-started, 20)
                    await asyncio.sleep(.05)
                    job = await call('ocp_native_job', {'domain': 'worker-scheduling', 'job_id': job['jobId']})
                self.assertEqual(job['status'], 'succeeded')
                result = await call('ocp_native_result', {'domain': 'worker-scheduling', 'job_id': job['jobId']})
                self.assertEqual(result['result']['metrics'][0]['value'], 7)
                report = await call('ocp_native_verify', {'domain': 'worker-scheduling', 'job_id': job['jobId']})
                self.assertEqual(report['verification']['status'], 'PASS')
        asyncio.run(exercise())

    def test_console_evidence_serve_prepares_submits_and_explains(self):
        async def exercise():
            params = StdioServerParameters(command=str(self.executable), args=['serve','--evidence'], env=self.environment)
            async with Client(params, read_timeout_seconds=30) as client:
                self.assertEqual(len((await client.list_tools()).tools), 11)
                async def call(name, args):
                    response = await client.call_tool(name,args)
                    self.assertFalse(response.is_error,response.structured_content)
                    EVENTS.append({'entrypoint':'ocp-native serve --evidence','tool':name,'arguments':args,'result':response.structured_content})
                    return response.structured_content
                domain='worker-scheduling'
                context=await call('ocp_native_context',{'domain':domain})
                self.assertEqual(context['evidence']['version'],'0.5.0')
                problem=context['catalog']['requestTemplate']
                problem.update(request_id='cli-evidence',input=json.loads((ARGS.kit/'worker-input.json').read_text()))
                record=await call('ocp_native_prepare',{'domain':domain,'problem':problem,'requirements':[],
                                  'source_text':'Use the supplied synthetic worker data.','detail':'compact'})
                submitted=await call('ocp_native_submit',{'domain':domain,'problem':record['problem'],'idempotency_key':'cli-evidence'})
                self.assertEqual(submitted['input_validation']['origin'],'SUBMIT_PRECHECK')
                job=submitted['job']; started=time.monotonic()
                while job['status'] in ('queued','running'):
                    self.assertLess(time.monotonic()-started,20)
                    await asyncio.sleep(.05)
                    job=await call('ocp_native_job',{'domain':domain,'job_id':job['jobId']})
                explained=await call('ocp_native_explain',{'domain':domain,'job_id':job['jobId'],
                                    'preparation_id':record['preparation_id']})
                self.assertEqual(explained['verification']['status'],'PASS')
                self.assertEqual(explained['facts']['objective']['value'],7)
                self.assertEqual(explained['comparison']['reason'],'BASELINE_NOT_PROVIDED')
                self.assertEqual(explained['preparation']['status'],'PASS')
        asyncio.run(exercise())

    def test_missing_mcp_is_actionable_and_config_emits_nothing(self):
        report = json.loads(self.command(['doctor', '--probe'], expected=1, python=ARGS.without_mcp_python).stdout)
        self.assertEqual(report['probe']['status'], 'NOT_RUN')
        self.assertTrue(any(issue['code']=='MISSING_DEPENDENCY' and issue['package']=='mcp' for issue in report['issues']))
        result = self.command(['config'], expected=1, python=ARGS.without_mcp_python)
        self.assertEqual(result.stdout, '')
        self.assertEqual(json.loads(result.stderr)['status'], 'FAIL')

    def test_missing_checker_affects_only_optional_verification(self):
        self.assertEqual(json.loads(self.command(['doctor', '--probe'], python=self.no_checker).stdout)['status'], 'PASS')
        report = json.loads(self.command(['doctor', '--probe', '--verification'], expected=1, python=self.no_checker).stdout)
        self.assertEqual(report['probe']['status'], 'NOT_RUN')
        self.assertTrue(any(issue['package']=='ocp-conformance-candidate' for issue in report['issues']))
        evidence = json.loads(self.command(['doctor','--probe','--evidence'],expected=1,python=self.no_checker).stdout)
        self.assertEqual(evidence['probe']['status'],'NOT_RUN')
        for action in ('config','serve'):
            failed = self.command([action,'--evidence'],expected=1,python=self.no_checker)
            self.assertEqual(failed.stdout,'')
            self.assertEqual(json.loads(failed.stderr)['status'],'FAIL')

    def test_timeout_cleans_up_real_child(self):
        with tempfile.TemporaryDirectory(dir=ARGS.output) as directory:
            pid_file = Path(directory)/'pid.txt'
            script = 'import os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(60)'
            broken = {'mcpServers': {'ocp-native-local': {'command': sys.executable,
                'args': ['-I', '-B', '-c', script, str(pid_file)]}}}
            start = time.monotonic()
            with patch.object(native_cli, 'configuration', return_value=broken):
                report = native_cli.doctor(probe=True, timeout=1)
            EVENTS.append({'fault_injection': 'Silent server process', 'report': report})
            self.assertEqual(report['status'], 'FAIL')
            self.assertLess(time.monotonic()-start, 15)
            self.assertTrue(pid_file.is_file(), 'The timeout test must launch an actual child')
            pid = int(pid_file.read_text())
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                self.fail('Timed-out probe left its child process running')

    def test_successful_probe_cleans_up_real_child(self):
        with tempfile.TemporaryDirectory(dir=ARGS.output) as directory:
            pid_file = Path(directory)/'pid.txt'
            script = ('import os,sys;from pathlib import Path;'
                      'Path(sys.argv[1]).write_text(str(os.getpid()));'
                      'os.execv(sys.executable,[sys.executable,"-I","-B","-m","ocp_runtime.native_mcp"])')
            observed = {'mcpServers': {'ocp-native-local': {'command': sys.executable,
                'args': ['-I', '-B', '-c', script, str(pid_file)]}}}
            with patch.object(native_cli, 'configuration', return_value=observed):
                report = native_cli.doctor(probe=True, timeout=30)
            EVENTS.append({'instrumentation': 'PID observed before exec of real server', 'report': report})
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(len(report['probe']['tools']), 8)
            pid = int(pid_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_exited_server_cannot_report_pass(self):
        broken = {'mcpServers': {'ocp-native-local': {'command': sys.executable,
            'args': ['-I', '-B', '-c', 'raise SystemExit(7)']}}}
        with patch.object(native_cli, 'configuration', return_value=broken):
            report = native_cli.doctor(probe=True, timeout=5)
        EVENTS.append({'fault_injection': 'Server exits with code 7', 'report': report})
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['probe']['status'], 'FAIL')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wheelhouse', type=Path, action='append', required=True)
    parser.add_argument('--without-mcp-python', type=Path, required=True)
    ARGS = parser.parse_args()
    ARGS.kit, ARGS.output = ARGS.kit.resolve(), ARGS.output.resolve()
    ARGS.output.mkdir(exist_ok=False)
    report_path = ARGS.output/'result.json'
    report_path.write_text(json.dumps({'status': 'INCOMPLETE'}))
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeCLI))
    report = {'status': 'PASS' if result.wasSuccessful() else 'FAIL', 'tests_run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'model_calls': 0, 'scope': 'Installed CLI and real local stdio; timeout/exit failures deliberately injected',
        'events': EVENTS}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='events'}))
    raise SystemExit(not result.wasSuccessful())
