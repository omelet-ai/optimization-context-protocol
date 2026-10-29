import json
from pathlib import Path
import sys
import tempfile
import unittest

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


if __name__ == '__main__':
    r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Links))
    print(json.dumps({'status': 'PASS' if r.wasSuccessful() else 'FAIL', 'tests_run': r.testsRun,
        'errors': len(r.errors), 'failures': len(r.failures), 'skipped': len(r.skipped)}))
    raise SystemExit(not r.wasSuccessful())
