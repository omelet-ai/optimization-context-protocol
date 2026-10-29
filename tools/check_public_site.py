"""Check the exact documentation-only artifact before uploading it to Pages."""
import argparse
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from build_public_site import ASSETS, CONTRACTS, REPO, ROOT, SCHEMAS, canonical_base, readme_commands
from check_h21 import Page


class PublicSite(unittest.TestCase):
    directory = None
    base = None

    @classmethod
    def setUpClass(cls):
        cls.html = {p.relative_to(cls.directory).as_posix(): p.read_text() for p in cls.directory.rglob("*.html")}
        cls.pages = {name: Page(body) for name, body in cls.html.items()}

    def test_01_exact_public_inventory(self):
        expected = {"index.html", "start/index.html", "start/local/index.html", "start/engine/index.html",
                    "start/omelet/index.html", "guides/apps/index.html", "examples/index.html",
                    "reference/index.html", "project/index.html", "ko/index.html", "404.html",
                    "LICENSE.txt", "NOTICE.txt", "THIRD_PARTY_NOTICES.txt", "robots.txt", "sitemap.xml", ".nojekyll"}
        expected |= {"assets/" + name for name in ASSETS}
        expected |= {"contracts/" + name for name in CONTRACTS.values()}
        expected |= {"contracts/schemas/" + name for name in SCHEMAS}
        paths = list(self.directory.rglob("*"))
        self.assertFalse(any(p.is_symlink() for p in paths))
        self.assertEqual({p.relative_to(self.directory).as_posix() for p in paths if p.is_file()}, expected)

    def test_02_links_fragments_and_source_targets(self):
        for name, page in self.pages.items():
            for link in page.links:
                resolved = urljoin(self.base + name, link)
                parsed = urlsplit(resolved)
                self.assertEqual(parsed.scheme, "https", (name, link))
                if resolved.startswith(REPO + "/blob/main/"):
                    path = unquote(urlsplit(resolved).path.split("/blob/main/", 1)[1])
                    self.assertTrue((ROOT / path).is_file(), (name, link))
                if not resolved.startswith(self.base):
                    continue
                relative = unquote(urlsplit(resolved).path[len(urlsplit(self.base).path):])
                if not relative or relative.endswith("/"):
                    relative += "index.html"
                path = (self.directory / relative).resolve()
                self.assertTrue(path.is_relative_to(self.directory))
                self.assertTrue(path.is_file(), (name, link))
                if parsed.fragment and path.suffix == ".html":
                    self.assertIn(parsed.fragment, Page(path.read_text()).ids)

    def test_03_no_private_data_packages_or_obsolete_claims(self):
        patterns = [rb"ocp_trial_[A-Za-z0-9_-]{43}", rb"-----BEGIN .*PRIVATE KEY-----", rb"/Users/[^/\s]+/", rb"https://[^\s\"<>]+\.trycloudflare\.com"]
        for path in self.directory.rglob("*"):
            if not path.is_file():
                continue
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, path.read_bytes()), path.name)
        for name, text in self.html.items():
            for stale in ("Local review edition", "Public distribution is pending", "downloads/ocp-developer-kit", "공개 라이선스·배포와 상시 trial은 아직 확정되지"):
                self.assertNotIn(stale, text, name)
            for tag, attrs in self.pages[name].tags:
                self.assertNotIn(tag, ("iframe", "form"))
                if tag == "script" and attrs.get("src"):
                    self.assertTrue(urljoin(self.base + name, attrs["src"]).startswith(self.base))

    def test_native_release_is_discoverable_without_source_build(self):
        url = REPO + '/releases/tag/v0.1.1-preview.1'
        for name in ['index.html', 'start/index.html', 'start/local/index.html', 'ko/index.html']:
            self.assertIn(url, self.pages[name].links, name)
            self.assertIn('SHA256SUMS', self.html[name], name)
        for name, body in self.html.items():
            for obsolete in ['prebuilt native downloads are not published', 'no release download is published yet', '사전 빌드 다운로드는 제공하지 않습니다', 'Native prebuilt downloads and registry releases are not offered', 'no prebuilt package downloads are published', 'Native 사전 빌드 다운로드와 레지스트리 패키지는 제공하지 않습니다']:
                self.assertNotIn(obsolete, body, name)

    def test_04_readme_commands_are_identical(self):
        observed = {}
        for page in self.pages.values():
            observed.update(page.commands)
        for marker in ("readme-build", "readme-examples", "readme-mcp", "readme-native-build", "readme-native-mcp"):
            self.assertEqual(observed[marker], readme_commands(marker))
        self.assertIn("--profile all", observed["readme-mcp"])
        worker = re.search(r'<!-- ocp:worker-analysis -->\s*```sh\n(.*?)\n```',
                           (ROOT / 'docs/users/WORKER_ANALYSIS.md').read_text(), re.S)[1]
        self.assertEqual(observed['worker-analysis'], worker)
        self.assertIn('VERIFICATION_SCOPE.md', self.html['guides/apps/index.html'])

    def test_05_metadata_indexing_and_404(self):
        expected = []
        for name, page in self.pages.items():
            self.assertEqual(len(page.ids), len(set(page.ids)), name)
            self.assertEqual(sum(t == "h1" for t, _ in page.tags), 1, name)
            self.assertEqual(sum(t == "main" for t, _ in page.tags), 1, name)
            if name == "404.html":
                self.assertIn(('meta', {'name': 'robots', 'content': 'noindex'}), page.tags)
                continue
            canonical = self.base + ("" if name == "index.html" else name.removesuffix("index.html"))
            self.assertIn(('link', {'rel': 'canonical', 'href': canonical}), page.tags)
            self.assertIn(('meta', {'name': 'robots', 'content': 'index, follow'}), page.tags)
            expected.append(canonical)
        root = ET.parse(self.directory / "sitemap.xml").getroot()
        self.assertEqual(set(expected), {node.text for node in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")})
        self.assertIn("Allow: /", (self.directory / "robots.txt").read_text())

    def test_06_real_saved_example_and_licenses(self):
        demo = json.loads((self.directory / "assets/example.json").read_text())
        self.assertEqual(demo["routing"]["independent_check"]["total_cost"], 18)
        self.assertEqual(demo["routing"]["result"]["status"], "feasible")
        self.assertEqual(demo["rejected"]["result"]["kind"], "failure")
        self.assertIn("Precomputed at site build", self.html["examples/index.html"])
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            self.assertEqual((ROOT / name).read_bytes(), (self.directory / (name.removesuffix(".md") + ".txt")).read_bytes())

    def test_07_base_url_rejects_unsafe_or_ambiguous_input(self):
        self.assertEqual(canonical_base("https://ocp.omelet.ai"), "https://ocp.omelet.ai/")
        for invalid in ("http://ocp.omelet.ai", "https://key@ocp.omelet.ai", "https://ocp.omelet.ai/?key=x", "https://ocp.omelet.ai/#x", "https://ocp.omelet.ai/../x", 'https://ocp.omelet.ai/\"x'):
            with self.assertRaises(ValueError):
                canonical_base(invalid)

    def test_08_entry_paths_disclose_invitation_condition(self):
        for name in ('index.html', 'start/index.html'):
            self.assertIn('Invitation only', self.html[name])
            self.assertIn('Recommended when invited', self.html[name])
            self.assertNotIn('Recommended first experience', self.html[name])
            self.assertTrue(any(link.endswith('/guides/apps/index.html#mcp') for link in self.pages[name].links))
        self.assertIn('Run locally', self.html['index.html'])
        self.assertIn('Public trial enrollment is not open', self.html['start/omelet/index.html'])

    def test_09_planning_examples_preserve_actual_evidence(self):
        demo = json.loads((self.directory / 'assets/example.json').read_text())
        for key, profile, cost in (('worker', 'worker.scheduling', 7), ('inventory', 'inventory.replenishment', 16)):
            data = demo[key]
            self.assertEqual(data['input'], data['request']['input'])
            self.assertEqual(data['result']['domain_profile'], {'id': profile, 'version': '0.1.0'})
            self.assertEqual(data['request']['request_id'], data['result']['request_id'])
            self.assertEqual(data['result']['status'], 'optimal')
            self.assertTrue(data['independent_check']['feasible'])
            self.assertEqual(data['independent_check']['total_cost'], cost)
            self.assertEqual(data['result']['metrics'][0]['value'], cost)
            self.assertEqual(data['evaluation']['metrics'][0]['value'], cost)
            self.assertIn(key, self.pages['examples/index.html'].ids)

    def test_10_entrypoints_distinguish_core_and_native_source_paths(self):
        for name in ('index.html', 'start/index.html', 'start/local/index.html',
                     'start/engine/index.html', 'guides/apps/index.html',
                     'reference/index.html', 'project/index.html', 'examples/index.html'):
            self.assertIn('data-edition-status', self.html[name], name)
            self.assertIn('Core 0.1 and the native v1 candidate are public source previews.', self.html[name], name)
            self.assertTrue(any(link.endswith('/start/local/index.html#native') for link in self.pages[name].links), name)
        self.assertIn('Core 0.1과 native v1 후보를 공개 소스로 제공합니다.', self.html['ko/index.html'])
        readme = (ROOT / 'README.md').read_text()
        self.assertIn('Existing Core 0.1 imports and synchronous semantics remain supported', readme)
        self.assertIn('native', self.pages['start/local/index.html'].ids)
        self.assertIn('build_native_candidate.py', self.pages['start/local/index.html'].commands['readme-native-build'])
        self.assertIn('--domain worker-scheduling --input worker-input.json', self.pages['start/local/index.html'].commands['readme-native-mcp'])
        for name, page in self.pages.items():
            for stale in ('local, unpublished candidate', 'remain local and unpublished', '미공개 후보'):
                self.assertNotIn(stale, self.html[name])
            for link in page.links:
                self.assertFalse(any(package in link for package in ('.whl', '.tgz', '.zip')), (name, link))

    def test_11_readme_and_site_comparison_cells_match(self):
        readme = (ROOT / 'README.md').read_text()
        marked = re.findall(r'<!-- ocp:core-native-table:start -->\s*(.*?)\s*<!-- ocp:core-native-table:end -->', readme, re.S)
        self.assertEqual(len(marked), 1)
        rows = marked[0].splitlines()
        expected = [cell.strip().replace('`', '') for i, row in enumerate(rows) if i != 1
                    for cell in row.strip().strip('|').split('|')]
        tables = re.findall(r'<table data-core-native>(.*?)</table>', self.html['reference/index.html'], re.S)
        self.assertEqual(len(tables), 1)
        actual = [unescape(re.sub(r'<[^>]+>', '', cell)) for cell in
                  re.findall(r'<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>', tables[0], re.S)]
        self.assertEqual(actual, expected)
        self.assertIn('Core 0.1', actual)
        self.assertIn('Native v1 candidate', actual)

    def test_12_native_lifecycle_and_tools_have_separate_guidance(self):
        apps = self.html['guides/apps/index.html']
        self.assertIn('native-mcp', self.pages['guides/apps/index.html'].ids)
        tools = re.findall(r'<th scope="row"><code>(ocp_native_\w+)</code></th>', apps)
        self.assertEqual(tools, ['ocp_native_' + name for name in
                         ('context', 'requirements', 'validate', 'submit', 'job', 'result', 'cancel', 'evaluate')])
        self.assertIn('Doctor discovers six tools', apps)
        self.assertIn('ocp_candidate.native', apps)
        self.assertIn('ocp-candidate/native', apps)
        reference = unescape(self.html['reference/index.html'])
        for meaning in ('contractVersion: "1"', 'domainPayloadFormat: "ocp-core-request/0.1.0"',
                        'JobResult.result', 'same idempotency key and input',
                        'confirm a terminal job state', 'not mathematical optimality',
                        'not the full', 'no removal date is set'):
            self.assertIn(meaning, reference)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    PublicSite.directory = Path(args.directory).resolve()
    PublicSite.base = canonical_base(args.base_url)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicSite))
    files = {p.relative_to(PublicSite.directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PublicSite.directory.rglob("*")) if p.is_file()}
    print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "files": files, "scope": "static_public_artifact; no deployment, model call or external-human acceptance"}))
    raise SystemExit(not result.wasSuccessful())
