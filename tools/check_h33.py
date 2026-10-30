"""Public status consistency and documentation-only artifact regression."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_public_site import build
from check_public_site import PublicSite


class PublicDocs(unittest.TestCase):
    def test_01_current_contracts_do_not_claim_private_source(self):
        paths = [ROOT / 'spec/README.md', ROOT / 'spec/core/CORE_0_1.md',
                 *sorted((ROOT / 'spec/profiles').glob('*.md')),
                 ROOT / 'spec/bindings/HTTP_MCP_0_1.md', ROOT / 'docs/users/GETTING_STARTED.md']
        for path in paths:
            text = path.read_text()
            for stale in ('비공개 기술 후보', 'Status: private candidate', '공개 권리·라이선스와 외부 환경은 아직 미승인'):
                self.assertNotIn(stale, text, path.name)

    def test_02_status_distinguishes_source_site_and_services(self):
        text = (ROOT / 'docs/users/PROJECT_STATUS.md').read_text()
        for phrase in ('Apache-2.0', 'GitHub Pages', 'no PyPI/npm release', 'not a stable release',
                       'no public self-service signup', 'not external developers', 'MCP SDK'):
            self.assertIn(phrase, text)

    def test_03_source_approval_does_not_expand_service_scope(self):
        review = json.loads((ROOT / 'provenance/publication.json').read_text())
        self.assertTrue(review['publication_authorized'])
        self.assertEqual(review['scope'], 'github_source_repository_only')
        for key in ('registry_publication_authorized', 'site_deployment_authorized', 'trial_deployment_authorized'):
            self.assertFalse(review[key])

    def test_04_core_structure_and_namespace_retained(self):
        schema = json.loads((ROOT / 'spec/schemas/core-0.1.schema.json').read_text())
        self.assertEqual(schema['$id'], 'urn:ocp:candidate:core:0.1.0')
        self.assertNotIn('private', schema['title'])
        self.assertIn('conformance', schema['$defs'])

    def test_05_readme_links_live_documentation_not_localhost(self):
        text = (ROOT / 'README.md').read_text()
        self.assertIn('https://omelet-ai.github.io/optimization-context-protocol/', text)
        self.assertNotIn('a hosted public website and open trial enrollment are not available yet', text)

    def test_06_released_examples_are_not_described_as_unpublished(self):
        for name in ('NATIVE_LOCAL_CANDIDATE.md', 'NATIVE_PROJECT_WORKFLOW.md',
                     'NATIVE_PROFILE_EXTENSION.md', 'NATIVE_BYO_WORKER.md'):
            text = (ROOT / 'docs/users' / name).read_text()
            self.assertIn('v0.1.1-preview.1', text, name)
            for stale in ('publication approvals do not publish these new example packages',
                          'included in the earlier public native kit', 'Older native kits lack these files'):
                self.assertNotIn(stale, text, name)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='ocp-public-docs-') as directory:
        PublicSite.directory = Path(directory).resolve() / 'site'
        PublicSite.base = 'https://omelet-ai.github.io/optimization-context-protocol/'
        build(PublicSite.directory, PublicSite.base)
        suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(PublicDocs),
                                   unittest.defaultTestLoader.loadTestsFromTestCase(PublicSite)])
        result = unittest.TextTestRunner().run(suite)
        ok = result.wasSuccessful() and not result.skipped
        print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'tests_run': result.testsRun,
                          'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
                          'scope': 'Local public docs and static artifact; no deployment or registry publication'}))
        sys.exit(0 if ok else 1)
