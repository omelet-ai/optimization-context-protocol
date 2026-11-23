"""Fail-closed CI policy and platform diagnostics; no hosted-run claims."""
from copy import deepcopy
import importlib.util
import contextlib
import io
import json
import hashlib
import tempfile
import tarfile
import zipfile
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from ci_policy import WORKFLOW, validate
from check_public_ci import passed, require_success, selected_path
import quickstart
from build_native_candidate import local_wheel_references, verify_node_exports

inspection_spec = importlib.util.spec_from_file_location(
    "inspection_artifact_test", ROOT / "tools/native_tests/inspection_suite.py")
inspection_artifact = importlib.util.module_from_spec(inspection_spec)
inspection_spec.loader.exec_module(inspection_artifact)


class PublicCI(unittest.TestCase):
    def setUp(self):
        self.flow = json.loads((ROOT / WORKFLOW).read_text())

    def rejected(self):
        with self.assertRaises(ValueError): validate(json.dumps(self.flow))

    def test_explicit_pending_selection_preserves_historical_default(self):
        with patch('check_public_ci.read_plan', return_value={'source_selection': 'provenance/routing-preview-selection.json'}):
            self.assertEqual(selected_path(), 'provenance/routing-preview-selection.json')
            self.assertEqual(selected_path('provenance/public-format-candidate-selection.json'), 'provenance/public-format-candidate-selection.json')

    def node_archive(self, missing=(), export=None, symlink=None):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        metadata = {'main': 'dist/client.js', 'types': 'dist/client.d.ts', 'exports': {
            '.': {'types': './dist/client.d.ts', 'default': './dist/client.js'},
            './knowledge': {'types': './dist/knowledge.d.ts', 'default': './dist/knowledge.js'},
            './fingerprint': {'types': './dist/fingerprint.d.ts', 'default': './dist/fingerprint.js'},
            './native': {'types': './dist/native.d.mts', 'import': './dist/native.mjs'}}}
        if export is not None:
            metadata['exports']['./extra'] = export
        contents = {'package.json': json.dumps(metadata).encode()}
        for stem, extension in [('client', 'js'), ('knowledge', 'js'), ('fingerprint', 'js'), ('native', 'mjs')]:
            contents['dist/' + stem + '.' + extension] = b'export {};'
            contents['dist/' + stem + ('.d.mts' if extension == 'mjs' else '.d.ts')] = b'export {};'
        archive = root / 'sdk.tgz'
        with tarfile.open(archive, 'w:gz') as package:
            for name, content in contents.items():
                # Even a successful compiler output cannot compensate for a
                # missing member in the actual archive installed by a consumer.
                staged = root / name; staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(content)
                if name in missing:
                    continue
                member = tarfile.TarInfo('package/' + name)
                if name == symlink:
                    member.type = tarfile.SYMTYPE; member.linkname = 'client.js'
                    package.addfile(member)
                else:
                    member.size = len(content); package.addfile(member, io.BytesIO(content))
        return archive

    def test_packed_node_exports_include_javascript_types_and_conditions(self):
        self.assertEqual(verify_node_exports(self.node_archive()), 8)

    def test_packed_node_exports_reject_missing_javascript_despite_compiler_output(self):
        for name in ['dist/knowledge.js', 'dist/fingerprint.js', 'dist/native.mjs']:
            with self.subTest(name=name):
                archive = self.node_archive(missing=[name])
                self.assertTrue((archive.parent / name).is_file())
                with self.assertRaisesRegex(ValueError, 'NODE_EXPORT_MISSING: ' + name):
                    verify_node_exports(archive)

    def test_packed_node_exports_reject_missing_types(self):
        for name in ['dist/knowledge.d.ts', 'dist/fingerprint.d.ts', 'dist/native.d.mts']:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'NODE_EXPORT_MISSING: ' + name):
                verify_node_exports(self.node_archive(missing=[name]))

    def test_packed_node_exports_reject_unsafe_targets(self):
        for target in ['../client.js', '/dist/client.js', './dist/../client.js', './dist\\client.js',
                       'C:/dist/client.js', 'file:///dist/client.js', './%2e%2e/client.js']:
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'NODE_EXPORT_PATH_INVALID'):
                verify_node_exports(self.node_archive(export=target))

    def test_packed_node_exports_reject_symlink_entrypoint(self):
        with self.assertRaisesRegex(ValueError, 'NODE_EXPORT_MISSING: dist/fingerprint.js'):
            verify_node_exports(self.node_archive(symlink='dist/fingerprint.js'))

    def test_pending_selection_contains_advertised_sdk_source_modules(self):
        selection = json.loads((ROOT / 'provenance/public-format-candidate-selection.json').read_text())
        self.assertFalse(selection['publication_approved'])
        for name in ['client.ts', 'knowledge.ts', 'fingerprint.ts']:
            self.assertIn('sdk/typescript/src/' + name, selection['files'])

    def worker_fixture(self, package='ocp-worker-greedy-example', version='0.1.2.dev1'):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        name = 'ocp_worker_greedy_example-0.1.2.dev1-py3-none-any.whl'
        with zipfile.ZipFile(root / name, 'w') as wheel:
            wheel.writestr('ocp_worker_greedy_example-0.1.2.dev1.dist-info/METADATA',
                           'Metadata-Version: 2.4\nName: ' + package + '\nVersion: ' + version + '\n')
        (root / 'manifest.json').write_text(json.dumps({'example_wheels': {'worker_greedy': name},
            'files': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()}}))
        return root, name

    def test_exact_worker_artifact_accepts_verified_manifest_selection(self):
        root, name = self.worker_fixture()
        self.assertEqual(inspection_artifact.worker_example_wheel(root), root / name)

    def test_exact_worker_artifact_rejects_missing_file(self):
        root, name = self.worker_fixture(); (root / name).unlink()
        with self.assertRaisesRegex(ValueError, 'WORKER_WHEEL_MISSING'):
            inspection_artifact.worker_example_wheel(root)

    def test_exact_worker_artifact_rejects_tampered_bytes(self):
        root, name = self.worker_fixture(); (root / name).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'WORKER_WHEEL_HASH_MISMATCH'):
            inspection_artifact.worker_example_wheel(root)

    def test_exact_worker_artifact_rejects_wrong_package_or_version(self):
        for package, version in [('different-package', '0.1.2.dev1'), ('ocp-worker-greedy-example', '0.1.1')]:
            with self.subTest(package=package, version=version):
                root, _ = self.worker_fixture(package, version)
                with self.assertRaisesRegex(ValueError, 'WORKER_WHEEL_IDENTITY_MISMATCH'):
                    inspection_artifact.worker_example_wheel(root)

    def test_kit_guide_replaces_only_exact_built_artifact_names(self):
        old = './ocp_worker_greedy_example-0.1.1-py3-none-any.whl'
        current = 'ocp_worker_greedy_example-0.1.2.dev1-py3-none-any.whl'
        guide = 'Published 0.1.1. Install ' + old + ' and keep other text.'
        self.assertEqual(local_wheel_references(guide, [current]), guide.replace(old, './' + current))
        self.assertIn(old, guide)

    def test_kit_guide_rejects_unbuilt_or_ambiguous_artifact(self):
        old = 'ocp_worker_greedy_example-0.1.1-py3-none-any.whl'
        current = 'ocp_worker_greedy_example-0.1.2.dev1-py3-none-any.whl'
        with self.assertRaisesRegex(ValueError, 'DOCUMENTED_WHEEL_NOT_BUILT'):
            local_wheel_references(old, [])
        with self.assertRaisesRegex(ValueError, 'AMBIGUOUS_BUILT_WHEEL'):
            local_wheel_references(old, [old, current])

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
