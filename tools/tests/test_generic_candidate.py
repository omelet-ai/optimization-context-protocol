"""Boundary tests for the offline installed generic harness; no service calls."""
from copy import deepcopy
import json
import os
import signal
import subprocess
import textwrap
import time
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import check_generic_candidate as harness


class GenericHarness(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.work=Path(self.temp.name).resolve()
        self.source=self.work/'source';self.source.mkdir()

    def test_new_sibling_output_accepted(self):
        self.assertEqual(harness.output_path(self.source,self.work/'output'),self.work/'output')

    def test_output_inside_or_equal_source_rejected(self):
        for path in [self.source,self.source/'nested']:
            with self.assertRaises(ValueError):harness.output_path(self.source,path)

    def test_existing_output_preserved(self):
        path=self.work/'output';path.mkdir();(path/'sentinel').write_text('keep')
        with self.assertRaises(ValueError):harness.output_path(self.source,path)
        self.assertEqual((path/'sentinel').read_text(),'keep')

    def test_symlink_output_parent_rejected(self):
        link=self.work/'link';link.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(ValueError):harness.output_path(self.source,link/'new')

    def test_environment_does_not_forward_credentials_or_pythonpath(self):
        with patch.dict(os.environ,{'TEST_SECRET':'synthetic','PYTHONPATH':'unexpected','PIP_INDEX_URL':'https://invalid.example'}):
            env=harness.clean_environment(self.work,python=sys.executable,wheels=self.work/'wheels')
        for key in ('TEST_SECRET','PYTHONPATH','PIP_INDEX_URL'):self.assertNotIn(key,env)
        self.assertEqual(env['PIP_NO_INDEX'],'1');self.assertEqual(env['PIP_CONFIG_FILE'],os.devnull)
        self.assertEqual(env['HOME'],str(self.work/'home'))

    def test_marker_extracts_only_generic_block_verbatim(self):
        text='```sh\nlegacy\n```\n<!-- ocp:generic-quickstart:start -->\n```sh\nline 1\nline 2\n```\n<!-- ocp:generic-quickstart:end -->'
        self.assertEqual(harness.extract_quickstart(text),'line 1\nline 2')
        self.assertIn(harness.extract_quickstart((ROOT/'README.md').read_text()),(ROOT/'README.md').read_text())

    def test_missing_duplicate_or_non_shell_markers_rejected(self):
        text='<!-- ocp:generic-quickstart:start -->\n```sh\ntrue\n```\n<!-- ocp:generic-quickstart:end -->'
        for value in ('',text+text,text.replace('```sh','```python'),text.replace('```\n<!--','```\nextra\n<!--')):
            with self.assertRaises(ValueError):harness.extract_quickstart(value)

    def test_empty_skipped_failed_or_malformed_reports_rejected(self):
        baseline={'status':'PASS','tests_run':16,'errors':0,'failures':0,'skipped':0}
        harness.passed(baseline,16)
        for key,value in [('status','FAIL'),('tests_run',0),('tests_run',True),('errors',1),('failures',1),('skipped',1),('errors',False)]:
            report={**baseline,key:value}
            with self.assertRaises(ValueError):harness.passed(report,16)
        for key in baseline:
            report=deepcopy(baseline);del report[key]
            with self.assertRaises(ValueError):harness.passed(report,16)

    def test_dependency_wheel_conflict_rejected_before_copy(self):
        a=self.work/'a';b=self.work/'b';a.mkdir();b.mkdir();(a/'one.whl').write_bytes(b'a');(b/'one.whl').write_bytes(b'b')
        with self.assertRaisesRegex(ValueError,'CONFLICTING'):harness.collect_wheels([a,b],self.work/'out')
        self.assertFalse((self.work/'out').exists())

    def test_empty_or_symlink_wheelhouse_rejected(self):
        a=self.work/'a';a.mkdir()
        with self.assertRaisesRegex(ValueError,'EMPTY'):harness.collect_wheels([a],self.work/'out')
        file=self.work/'one.whl';file.write_bytes(b'x');(a/'one.whl').symlink_to(file)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):harness.collect_wheels([a],self.work/'out')

    def test_exact_current_selection_is_pending_and_retains_old_paths(self):
        report,paths=harness.source_selection(ROOT,harness.DEFAULT_SELECTION)
        old=json.loads((ROOT/'provenance/repository-selection.json').read_text())['files']
        self.assertTrue(set(old)<=set(paths));self.assertFalse(report['public_release_authorized'])
        self.assertEqual(report['scope'],'pending_public_source_candidate')

    def test_isolated_cli_loads_verifier_before_version_gate(self):
        output = self.work / 'no-build'
        result = subprocess.run([sys.executable, '-I', '-B', ROOT / 'tools/check_generic_candidate.py',
            '--source', ROOT, '--output', output, '--wheelhouse', self.work / 'absent',
            '--expected-version', 'incorrect-synthetic-version'], text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['error'], 'ValueError: EXPECTED_VERSION_MISMATCH')
        self.assertEqual(result.stderr, ''); self.assertFalse(output.exists())

    def test_selection_escape_rejected(self):
        for value in ('../outside.json','/outside.json','a/../b.json'):
            with self.assertRaises(ValueError):harness.source_selection(ROOT,value)

    def test_child_success_and_failure_receipts(self):
        env=harness.clean_environment(self.work,python=sys.executable)
        result=harness.run_command([sys.executable,'-I','-B','-c','print("synthetic")'],cwd=self.work,env=env,log=self.work/'ok.log',timeout=10)
        self.assertEqual(result['returncode'],0);self.assertFalse(result['timed_out']);self.assertFalse(result['unexpected_group_after_parent'])
        with self.assertRaisesRegex(RuntimeError,'CHILD_FAILED'):
            harness.run_command([sys.executable,'-I','-B','-c','raise SystemExit(7)'],cwd=self.work,env=env,log=self.work/'failed.log',timeout=10)
        self.assertEqual(json.loads((self.work/'failed.receipt.json').read_text())['returncode'],7)

    def test_child_timeout_is_failure_and_reaped(self):
        with self.assertRaisesRegex(RuntimeError,'CHILD_FAILED'):
            harness.run_command([sys.executable,'-I','-B','-c','import time;time.sleep(10)'],cwd=self.work,env=harness.clean_environment(self.work,python=sys.executable),log=self.work/'timeout.log',timeout=.05)
        result=json.loads((self.work/'timeout.receipt.json').read_text());self.assertTrue(result['timed_out']);self.assertIsNotNone(result['returncode'])

    def test_sigint_closes_owned_parent_and_descendant_before_propagating(self):
        child = self.work / 'owned.py'
        child.write_text(textwrap.dedent("""
            import json, signal, subprocess, sys, time
            from pathlib import Path
            descendant = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(60)'])
            def close(signum, frame):
                descendant.terminate()
                descendant.wait(timeout=2)
                raise SystemExit(0)
            signal.signal(signal.SIGTERM, close)
            Path(sys.argv[1]).write_text(json.dumps({'pid': descendant.pid}))
            time.sleep(60)
        """))
        controller = self.work / 'controller.py'
        controller.write_text(textwrap.dedent("""
            import os, signal, sys, threading, time
            from pathlib import Path
            sys.path.insert(0, sys.argv[1])
            import check_generic_candidate as h
            work = Path(sys.argv[2]); ready = work / 'ready.json'
            def interrupt():
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline: time.sleep(.01)
                os.kill(os.getpid(), signal.SIGINT)
            timer = threading.Thread(target=interrupt, daemon=True); timer.start()
            try:
                h.run_command([sys.executable, '-I', '-B', work / 'owned.py', ready], cwd=work,
                              env=h.clean_environment(work, python=sys.executable), log=work / 'interrupt.log', timeout=10)
            except KeyboardInterrupt: pass
            else: raise AssertionError('INTERRUPTION_NOT_PROPAGATED')
            timer.join(timeout=1)
        """))
        result = subprocess.run([sys.executable, '-I', '-B', controller, ROOT / 'tools', self.work],
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.work / 'interrupt.receipt.json').read_text())
        descendant = json.loads((self.work / 'ready.json').read_text())['pid']
        self.assertEqual(receipt['status'], 'FAIL'); self.assertEqual(receipt['exception_type'], 'KeyboardInterrupt')
        self.assertTrue(receipt['interrupted']); self.assertTrue(receipt['process_reaped'])
        self.assertTrue(receipt['group_absent_after_cleanup']); self.assertEqual(receipt['closure'], 'CLOSED')
        self.assertFalse(harness.group_alive(receipt['pgid']))
        with self.assertRaises(ProcessLookupError): os.kill(descendant, 0)

    def test_normal_parent_exit_with_lingering_child_is_failure_after_cleanup(self):
        program = "import subprocess,sys;subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(60)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
        with self.assertRaisesRegex(RuntimeError, 'CHILD_FAILED'):
            harness.run_command([sys.executable, '-I', '-B', '-c', program], cwd=self.work,
                                env=harness.clean_environment(self.work, python=sys.executable), log=self.work / 'lingering.log', timeout=5)
        receipt = json.loads((self.work / 'lingering.receipt.json').read_text())
        self.assertEqual(receipt['returncode'], 0); self.assertTrue(receipt['unexpected_group_after_parent'])
        self.assertEqual(receipt['status'], 'FAIL')
        # Some POSIX sandboxes briefly return EPERM while an orphan exits.
        # Such a probe is recorded UNKNOWN even when later absence is observed.
        self.assertIn(receipt['closure'], ('CLOSED', 'UNKNOWN'))
        if receipt['closure'] == 'UNKNOWN': self.assertTrue(receipt['cleanup_errors'])
        self.assertTrue(receipt['process_reaped']); self.assertTrue(receipt['group_absent_after_cleanup'])
        self.assertFalse(harness.group_alive(receipt['pgid']))

    def test_unknown_group_probe_cannot_pass(self):
        with patch.object(harness, 'group_alive', side_effect=[PermissionError('probe'), False, False, False]):
            with self.assertRaisesRegex(RuntimeError, 'CHILD_FAILED'):
                harness.run_command([sys.executable, '-I', '-B', '-c', 'pass'], cwd=self.work,
                                    env=harness.clean_environment(self.work, python=sys.executable), log=self.work / 'unknown.log', timeout=5)
        receipt = json.loads((self.work / 'unknown.receipt.json').read_text())
        self.assertEqual(receipt['status'], 'FAIL'); self.assertEqual(receipt['closure'], 'UNKNOWN')
        self.assertEqual(receipt['cleanup_errors'], ['PermissionError'])

    def detached_controller(self, mode):
        controller = self.work / ('detached-' + mode + '.py')
        controller.write_text(textwrap.dedent("""
            import json, os, signal, subprocess, sys, time
            from pathlib import Path
            sys.path.insert(0, sys.argv[1]); import check_generic_candidate as h
            registry = Path(sys.argv[2]); mode = sys.argv[3]
            deadline = time.monotonic() + 2
            while not (registry / 'owner.json').exists() and time.monotonic() < deadline: time.sleep(.01)
            delay = '.2' if mode in ('normal', 'incomplete') else '60'
            child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time;time.sleep(' + delay + ')'],
                                     start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            Path(sys.argv[4]).write_text(str(child.pid))
            if mode == 'incomplete': raise SystemExit(0)
            h.register_detached_process(registry, child.pid)
            if mode == 'normal': child.wait(timeout=2)
            elif mode == 'interrupt': os.kill(os.getpid(), signal.SIGINT)
            elif mode == 'forced': os.kill(os.getpid(), signal.SIGKILL)
        """))
        registry = self.work / ('registry-' + mode); log = self.work / ('detached-' + mode + '.log')
        command = [sys.executable, '-I', '-B', controller, ROOT / 'tools', registry, mode, self.work / (mode + '.pid')]
        def fixture_cleanup():
            # Preserve test ownership even if the harness under test fails.
            if (registry / 'child.json').exists():
                record = harness.registry_read(registry / 'child.json')
                row = record['child']; current = harness.process_details(row['pid'])
                if current is not None and harness.process_identity(current) == row:
                    harness.close_registered_groups([{'owner': row, 'tracked': [row]}])
        self.addCleanup(fixture_cleanup)
        return registry, log, command

    def test_detached_sdk_like_normal_exit_has_positive_closure(self):
        registry, log, command = self.detached_controller('normal')
        receipt = harness.run_command(command, cwd=self.work, env=harness.clean_environment(self.work, python=sys.executable),
                                      log=log, timeout=5, process_registry=registry)
        self.assertEqual(receipt['status'], 'PASS'); self.assertEqual(receipt['closure'], 'CLOSED')
        self.assertEqual(len(receipt['registered_groups']), 1)
        self.assertEqual(receipt['registered_groups'][0]['group_after_cleanup'], [])

    def test_detached_sdk_like_group_closed_after_controller_interrupt_or_death(self):
        for mode in ('interrupt', 'forced'):
            with self.subTest(mode=mode):
                registry, log, command = self.detached_controller(mode)
                with self.assertRaisesRegex(RuntimeError, 'CHILD_FAILED'):
                    harness.run_command(command, cwd=self.work, env=harness.clean_environment(self.work, python=sys.executable),
                                        log=log, timeout=5, process_registry=registry)
                receipt = json.loads(log.with_suffix('.receipt.json').read_text())
                self.assertEqual(receipt['status'], 'FAIL'); self.assertEqual(receipt['closure'], 'CLOSED')
                self.assertTrue(receipt['process_reaped']); self.assertTrue(receipt['group_absent_after_cleanup'])
                self.assertEqual(len(receipt['registered_groups']), 1)
                detached = receipt['registered_groups'][0]
                self.assertTrue(detached['cleanup_signals']); self.assertEqual(detached['group_after_cleanup'], [])
                self.assertFalse(harness.group_alive(detached['owner']['pgid']))

    def test_incomplete_detached_registration_cannot_claim_closed(self):
        registry, log, command = self.detached_controller('incomplete')
        with self.assertRaisesRegex(RuntimeError, 'CHILD_FAILED'):
            harness.run_command(command, cwd=self.work, env=harness.clean_environment(self.work, python=sys.executable),
                                log=log, timeout=5, process_registry=registry)
        receipt = json.loads(log.with_suffix('.receipt.json').read_text())
        self.assertEqual(receipt['closure'], 'UNKNOWN'); self.assertEqual(receipt['status'], 'FAIL')
        self.assertIn('INCOMPLETE', receipt['registration_error'])
        pid = int((self.work / 'incomplete.pid').read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                if not harness.group_alive(pid):
                    break
            except PermissionError:
                # macOS can briefly deny a signal-0 probe while the orphan exits.
                pass
            time.sleep(.02)
        else:
            self.fail(f'Did not observe the exit of fixture process group {pid}')

    def test_kernel_group_permission_error_is_not_an_empty_group(self):
        import ctypes, errno
        from types import SimpleNamespace
        class Denied:
            def __call__(self, *args):
                ctypes.set_errno(errno.EPERM)
                return 0
        with patch.object(harness.sys, 'platform', 'darwin'), patch.object(harness.ctypes, 'CDLL', return_value=SimpleNamespace(proc_listpids=Denied())):
            with self.assertRaisesRegex(OSError, 'GROUP_ENUMERATION_FAILED'):
                harness.group_members(12345)
        ctypes.set_errno(0)

    def test_tampered_detached_birth_identity_never_signals_foreign_group(self):
        foreign = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time;time.sleep(10)'], start_new_session=True)
        try:
            owner = harness.process_identity(harness.process_details(os.getpid()))
            registry = self.work / 'tampered'; registry.mkdir(mode=0o700)
            child = harness.process_identity(harness.process_details(foreign.pid)); child['started'] += '-wrong'
            harness.registry_write(registry / 'owner.json', owner)
            harness.registry_write(registry / 'child.json', {'controller': owner, 'child': child})
            harness.registry_write(registry / 'complete.json', {'controller': owner, 'children': [foreign.pid]})
            with self.assertRaisesRegex(ValueError, 'IDENTITY_CHANGED'):
                harness.registered_groups(registry, owner)
            self.assertIsNone(foreign.poll())
        finally:
            foreign.terminate(); foreign.wait(timeout=3)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GenericHarness));ok=result.wasSuccessful()and not result.skipped
    print(json.dumps({'status':'PASS'if ok else'FAIL','tests_run':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped),'publication_authorized':False}));raise SystemExit(not ok)
