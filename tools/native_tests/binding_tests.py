"""Runs from a fresh installed Python environment, outside repository imports."""
from copy import deepcopy
import hashlib
import importlib
from importlib.resources import files
import json
from pathlib import Path
import unittest

from ocp_candidate.native import NativeClient, NativeError, native_contract, native_validate


class Bindings(unittest.TestCase):
    def test_01_native_sources_installed_and_hash_identical(self):
        root=files('foundry_capability_contract');origin=json.loads(root.joinpath('ORIGIN.json').read_text())
        prefix='shared/ocp-contracts/capability-contract/python/src/foundry_capability_contract/'
        for name,digest in origin['files'].items():
            relative=name.removeprefix(prefix) if name.startswith(prefix) else 'capability-contract-v1.json'
            self.assertEqual(hashlib.sha256(root.joinpath(relative).read_bytes()).hexdigest(),digest)
        self.assertEqual(origin['commit'],'7547036d1bc9464d6c43a9bdf7cff0a78e8560d7')

    def test_02_shared_schema_cases(self):
        for case in json.loads(Path('contract-cases.json').read_text()):
            with self.subTest(case=case['id']):
                if case['valid']: native_validate(case['component'],case['value'])
                else:
                    with self.assertRaises(NativeError):native_validate(case['component'],case['value'])

    def test_03_native_canonical_vectors(self):
        from foundry_capability_contract import canonical_digest
        for v in json.loads(Path('vectors.json').read_text())['vectors']:
            self.assertEqual(canonical_digest(json.loads(v['input'])),v['digest'])

    def test_04_core_client_unchanged(self):
        from ocp_candidate import Client
        from ocp_runtime.providers import make_provider
        client=Client(make_provider('worker.scheduling'))
        self.assertEqual(client.describe()['core_version'],'0.1.0')
        self.assertEqual(client.request({})['execution_profile']['id'],'execution.sync')

    def test_05_malformed_endpoint_credentials_refused(self):
        for url in ['http://external.invalid/v1','https://' + 'u:p' + '@example.org/v1','https://example.org/v1?q=x']:
            with self.assertRaises(NativeError):NativeClient(url,'synthetic')
        for token in ['', 'abc\nsecret']:
            with self.assertRaises(NativeError):NativeClient('http://127.0.0.1:9',token)

    def test_06_missing_tenant_and_key_no_network(self):
        client=NativeClient('http://127.0.0.1:9','synthetic')
        with self.assertRaisesRegex(NativeError,'TENANT_REQUIRED'):client.job('abc',tenant='')
        with self.assertRaisesRegex(NativeError,'IDEMPOTENCY_KEY_REQUIRED'):client.submit({},tenant='local',idempotency_key='')
        self.assertTrue(NativeError('UNREACHABLE').retryable)
        self.assertFalse(NativeError('INVALID_HEADER').retryable)

    def test_07_shared_components_not_manually_redeclared(self):
        schema=native_contract()
        self.assertEqual(schema['components']['schemas']['Capabilities']['required'],['contractVersion','problemType','catalogDigest'])
        with self.assertRaises(NativeError):native_validate('MadeUp',{})

    def test_08_installed_source_never_imports_sibling_checkout(self):
        import sys
        for name,module in list(sys.modules.items()):
            if name.startswith(('ocp_candidate','ocp_runtime','foundry_capability_contract')) and getattr(module,'__file__',None):
                self.assertIn('site-packages',module.__file__)
                self.assertNotIn('/Projects/',module.__file__)


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Bindings))
    print(json.dumps({'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped)}))
    raise SystemExit(not r.wasSuccessful())
