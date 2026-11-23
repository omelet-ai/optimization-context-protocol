import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_workspace import verify_document_links


class Links(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'README.md').write_text('[guide](docs/start.md#install)\n')
        (self.root / 'docs').mkdir(); (self.root / 'docs/start.md').write_text('# Install\n')

    def test_partial_generated_copy_does_not_hide_authored_error(self):
        generated = self.root / '.harness/work/build'; generated.mkdir(parents=True)
        (generated / 'README.md').write_text('[license](LICENSE)\n')
        verify_document_links(self.root)
        (self.root / 'docs/start.md').unlink()
        with self.assertRaises(AssertionError): verify_document_links(self.root)

    def test_authored_broken_link_is_rejected(self):
        (self.root / 'docs/start.md').write_text('[missing](missing.md)\n')
        with self.assertRaises(AssertionError): verify_document_links(self.root)

    def test_unclosed_source_code_fence_is_rejected(self):
        (self.root / 'docs/start.md').write_text('```sh\necho hello\n')
        with self.assertRaises(AssertionError): verify_document_links(self.root)

    def test_source_link_escape_is_rejected(self):
        (self.root / 'docs/start.md').write_text('[outside](../../)\n')
        with self.assertRaises(AssertionError): verify_document_links(self.root)

    def test_excluded_roots_are_pruned_before_entry(self):
        for name in ('.private', 'reference', '.harness'):
            p = self.root / name / 'deep/broken.md'
            p.parent.mkdir(parents=True); p.write_text('[bad](missing)\n')
        visited = []; walk = os.walk
        def recording(*args, **kwargs):
            for row in walk(*args, **kwargs):
                visited.append(Path(row[0])); yield row
        with patch('verify_workspace.os.walk', recording):
            verify_document_links(self.root)
        self.assertEqual(set(visited), {self.root.resolve(), (self.root / 'docs').resolve()})

    def test_nested_exclusion_names_remain_authored(self):
        for name in ('.private', 'reference', '.harness'):
            with self.subTest(name=name):
                p = self.root / 'examples' / name / 'broken.md'
                p.parent.mkdir(parents=True); p.write_text('[bad](missing)\n')
                with self.assertRaises(AssertionError): verify_document_links(self.root)
                p.unlink()

    def test_symlink_directory_is_not_followed(self):
        with tempfile.TemporaryDirectory() as other:
            external = Path(other)
            (external / 'broken.md').write_text('[bad](missing)\n')
            (self.root / 'linked').symlink_to(external, target_is_directory=True)
            verify_document_links(self.root)

    def test_unreadable_authored_directory_is_rejected(self):
        def unreadable(*args, **kwargs):
            kwargs['onerror'](PermissionError('synthetic unreadable authored directory'))
            yield
        with patch('verify_workspace.os.walk', unreadable):
            with self.assertRaises(PermissionError): verify_document_links(self.root)


if __name__ == '__main__':
    r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Links))
    print(json.dumps({'status': 'PASS' if r.wasSuccessful() else 'FAIL', 'tests_run': r.testsRun,
        'errors': len(r.errors), 'failures': len(r.failures), 'skipped': len(r.skipped)}))
    raise SystemExit(not r.wasSuccessful())
