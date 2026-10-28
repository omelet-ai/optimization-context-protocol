"""Synthetic negative publication-gate fixtures; never records real approval."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_native_publication import verify


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root / 'provenance').mkdir()
        self.policy = {'repository': 'omelet-ai/optimization-context-protocol', 'scope': 'native_github_source',
                       'approvals': {k: False for k in ['source_rights', 'license_and_notices', 'patent_disclosure', 'exact_github_publication']},
                       'proposed_files': ['provenance/native-publication.json', 'provenance/native-origin-inventory.json', 'source.py']}
        (self.root / 'source.py').write_text('value = 1\n')
        self.write()
        (self.root / 'provenance/native-origin-inventory.json').write_text(json.dumps({'files': {
            'source.py': {'candidate_sha256': hashlib.sha256((self.root / 'source.py').read_bytes()).hexdigest()}}}))

    def write(self):
        (self.root / 'provenance/native-publication.json').write_text(json.dumps(self.policy))

    def test_pending_is_reviewable_but_not_authorized(self):
        result = verify(self.root)
        self.assertEqual(result['status'], 'PASS'); self.assertFalse(result['publication_authorized'])
        with self.assertRaises(PermissionError): verify(self.root, True)

    def test_core_approval_does_not_authorize_native(self):
        (self.root / 'provenance/publication.json').write_text(json.dumps({'publication_authorized': True}))
        with self.assertRaises(PermissionError): verify(self.root, True)

    def test_source_level_rights_cannot_be_skipped(self):
        self.policy['approvals'] = {key: True for key in self.policy['approvals']}; self.write()
        with self.assertRaisesRegex(PermissionError, 'source rights'): verify(self.root, True)

    def test_missing_source_rejected(self):
        (self.root / 'source.py').unlink()
        with self.assertRaises(FileNotFoundError): verify(self.root)

    def test_symlink_rejected(self):
        (self.root / 'source.py').unlink(); (self.root / 'source.py').symlink_to('provenance/native-publication.json')
        with self.assertRaisesRegex(ValueError, 'Symlink'): verify(self.root)

    def test_changed_extracted_source_rejected(self):
        (self.root / 'source.py').write_text('value = 2\n')
        with self.assertRaisesRegex(ValueError, 'drift'): verify(self.root)

    def test_credential_candidate_rejected(self):
        (self.root / 'source.py').write_text('token = ' + repr('gh' + 'p_' + 'A' * 36))
        with self.assertRaisesRegex(ValueError, 'github_token'): verify(self.root)

    def test_forbidden_and_traversal_paths_rejected(self):
        for name in ['../outside', '.private/notes.md', '.env.local', '/absolute', 'package.whl']:
            self.policy['proposed_files'][-1] = name; self.write()
            with self.assertRaises(ValueError): verify(self.root)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Publication))
    print(json.dumps({'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}))
    raise SystemExit(not result.wasSuccessful())
