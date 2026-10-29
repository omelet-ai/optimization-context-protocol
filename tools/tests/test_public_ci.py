"""Fail-closed CI policy and platform diagnostics; no hosted-run claims."""
from copy import deepcopy
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from ci_policy import WORKFLOW, validate
from check_public_ci import passed, require_success
import quickstart


class PublicCI(unittest.TestCase):
    def setUp(self):
        self.flow = json.loads((ROOT / WORKFLOW).read_text())

    def rejected(self):
        with self.assertRaises(ValueError): validate(json.dumps(self.flow))

    def test_read_only_workflow(self):
        validate(json.dumps(self.flow))

    def test_platform_runtime_selection_cannot_drift(self):
        self.flow['jobs']['public-source']['strategy']['matrix']['include'][1]['python'] = '3.12.15'
        self.rejected()
        self.setUp()
        self.flow['jobs']['windows-boundary']['steps'][1]['with']['python-version'] = '3.12.15'
        self.rejected()

    def test_privileged_event_rejected(self):
        self.flow['on']['pull_request_target'] = {}; self.rejected()

    def test_write_token_rejected(self):
        self.flow['permissions']['contents'] = 'write'; self.rejected()

    def test_oidc_rejected(self):
        self.flow['permissions']['id-token'] = 'write'; self.rejected()

    def test_mutable_action_ref_rejected(self):
        self.flow['jobs']['public-source']['steps'][0]['uses'] = 'actions/checkout@v4'; self.rejected()

    def test_checkout_credential_persistence_rejected(self):
        self.flow['jobs']['public-source']['steps'][0]['with']['persist-credentials'] = True; self.rejected()

    def test_self_hosted_rejected(self):
        self.flow['jobs']['public-source']['runs-on'] = 'self-hosted'; self.rejected()

    def test_failure_cannot_be_ignored(self):
        self.flow['jobs']['public-source']['continue-on-error'] = True; self.rejected()

    def test_step_failure_cannot_be_ignored(self):
        self.flow['jobs']['public-source']['steps'][-1]['continue-on-error'] = True; self.rejected()

    def test_secrets_not_forwarded(self):
        self.flow['jobs']['public-source']['steps'][-1]['env'] = {'KEY': '${{ secrets.SERVICE_KEY }}'}; self.rejected()

    def test_extra_job_rejected(self):
        self.flow['jobs']['release'] = {}; self.rejected()

    def test_artifacts_not_uploaded(self):
        self.flow['jobs']['public-source']['steps'].append({'uses': 'actions/upload-artifact@' + 'a' * 40}); self.rejected()

    def test_required_gate_cannot_omit_lane(self):
        self.flow['jobs']['required']['needs'].pop(); self.rejected()

    def test_required_gate_cannot_mask_failure(self):
        self.flow['jobs']['required']['steps'][0]['run'] = 'true'; self.rejected()

    def test_required_gate_handles_failed_and_skipped_lanes(self):
        # Exercise the actual final shell condition, including cancelled/skipped.
        command = self.flow['jobs']['required']['steps'][0]['run']
        for left, right in [('success','success'), ('failure','success'), ('success','cancelled'), ('skipped','success')]:
            result = subprocess.run(['/bin/sh', '-c', command], env={'PUBLIC_RESULT': left, 'WINDOWS_RESULT': right})
            self.assertEqual(result.returncode == 0, left == right == 'success')

    def test_no_success_from_empty_skipped_or_incomplete_reports(self):
        baseline = {'status': 'PASS', 'tests_run': 2, 'errors': 0, 'failures': 0, 'skipped': 0}
        passed(baseline)
        for key, value in [('status','FAIL'), ('tests_run',0), ('tests_run',True), ('errors',1), ('failures',1), ('skipped',1)]:
            report = dict(baseline, **{key:value})
            with self.assertRaises(ValueError): passed(report)
        for key in baseline:
            report = deepcopy(baseline); del report[key]
            with self.assertRaises(ValueError): passed(report)

    def test_failed_child_reports_bounded_diagnostics(self):
        output = io.StringIO()
        failure = subprocess.CompletedProcess([], 1, 'x' * 9000, 'missing pinned dependency')
        with contextlib.redirect_stderr(output), self.assertRaises(RuntimeError):
            require_success('install', failure)
        self.assertIn('missing pinned dependency', output.getvalue())
        self.assertLess(len(output.getvalue()), 8100)

    def test_core_windows_error_is_platform_not_python(self):
        # Unit injection tests the branch only. A real Windows subprocess is a
        # separate workflow lane and is never claimed by this test.
        with patch.object(quickstart, 'os', SimpleNamespace(name='nt')):
            with self.assertRaises(quickstart.SetupError) as error: quickstart.setup('unused')
        self.assertEqual(error.exception.code, 'PLATFORM_NOT_SUPPORTED')

    def test_native_windows_guard_precedes_manifest_and_writes(self):
        spec = importlib.util.spec_from_file_location('native_install_test', ROOT / 'examples/native/install.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(module, 'os', SimpleNamespace(name='nt')), patch.object(sys, 'argv', ['install.py']):
            with self.assertRaisesRegex(ValueError, '^PLATFORM_NOT_SUPPORTED$'): module.main()


if __name__ == '__main__':
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicCI))
    ok = result.wasSuccessful() and not result.skipped
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'tests_run': result.testsRun,
                      'errors': len(result.errors), 'failures': len(result.failures), 'skipped': len(result.skipped)}))
    raise SystemExit(not ok)
