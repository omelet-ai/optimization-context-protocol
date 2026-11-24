import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from binary_fixture_policy import FIXTURES, reviewed_fixture_text, validated_xml
import verify_repository as verifier

FIXTURE_DATA = {}
for name in FIXTURES:
    kind = "matrix" if "/matrix/" in name else "coordinates"
    with ZipFile(ROOT / name) as data:
        FIXTURE_DATA[kind] = {"source_path": name, "parts": {n: data.read(n).decode() for n in data.namelist()}}


def workbook(kind="matrix"):
    return (ROOT / FIXTURE_DATA[kind]["source_path"]).read_bytes()


def archive(parts, *, duplicate=False, symlink=False):
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as result:
        for name, text in parts.items():
            info = ZipInfo(name)
            info.compress_type = ZIP_DEFLATED
            if symlink and name == "xl/workbook.xml":
                info.create_system = 3
                info.external_attr = 0o120777 << 16
            result.writestr(info, text.encode())
        if duplicate:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                result.writestr("xl/workbook.xml", parts["xl/workbook.xml"])
    return output.getvalue()


class FixturePolicy(unittest.TestCase):
    def test_exact_two_fixtures_expose_all_xml_to_existing_scanner(self):
        for kind, fixture in FIXTURE_DATA.items():
            text = reviewed_fixture_text(fixture["source_path"], workbook(kind))
            for part in fixture["parts"].values():
                self.assertIn(part, text)

    def test_unknown_path_rejected_even_with_valid_bytes(self):
        with self.assertRaisesRegex(ValueError, "XLSX_PATH_NOT_REVIEWED"):
            reviewed_fixture_text("customer/real.xlsx", workbook())

    def test_changed_byte_rejected(self):
        data = bytearray(workbook()); data[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "XLSX_BYTES_NOT_REVIEWED"):
            reviewed_fixture_text(FIXTURE_DATA["matrix"]["source_path"], bytes(data))

    def test_appended_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, "XLSX_BYTES_NOT_REVIEWED"):
            reviewed_fixture_text(FIXTURE_DATA["matrix"]["source_path"], workbook() + b"extra")

    def test_duplicate_members_rejected(self):
        with self.assertRaisesRegex(ValueError, "XLSX_EXACT_PART_SET_REQUIRED"):
            validated_xml(archive(FIXTURE_DATA["matrix"]["parts"], duplicate=True))

    def test_macro_or_extra_part_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["xl/vbaProject.bin"] = "binary"
        with self.assertRaisesRegex(ValueError, "XLSX_EXACT_PART_SET_REQUIRED"):
            validated_xml(archive(parts))

    def test_traversal_part_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["../secret.xml"] = parts.pop("xl/workbook.xml")
        with self.assertRaisesRegex(ValueError, "XLSX_EXACT_PART_SET_REQUIRED"):
            validated_xml(archive(parts))

    def test_external_relationship_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["_rels/.rels"] = parts["_rels/.rels"].replace('Target="xl/workbook.xml"', 'Target="https://invalid.example/x" TargetMode="External"')
        with self.assertRaisesRegex(ValueError, "XLSX_EXTERNAL_RELATIONSHIP"):
            validated_xml(archive(parts))

    def test_relative_escape_relationship_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["_rels/.rels"] = parts["_rels/.rels"].replace('Target="xl/workbook.xml"', 'Target="../secret.xml"')
        with self.assertRaisesRegex(ValueError, "XLSX_EXTERNAL_RELATIONSHIP"):
            validated_xml(archive(parts))

    def test_entity_declaration_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["xl/workbook.xml"] = '<!DOCTYPE x [<!ENTITY x "test">]><x>&x;</x>'
        with self.assertRaisesRegex(ValueError, "XLSX_XML_DECLARATION_FORBIDDEN"):
            validated_xml(archive(parts))

    def test_large_expanded_member_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["xl/workbook.xml"] = '<x>' + 'a' * 7_000 + '</x>'
        with self.assertRaisesRegex(ValueError, "XLSX_UNSAFE_MEMBER"):
            validated_xml(archive(parts))

    def test_symlink_member_rejected(self):
        with self.assertRaisesRegex(ValueError, "XLSX_UNSAFE_MEMBER"):
            validated_xml(archive(FIXTURE_DATA["matrix"]["parts"], symlink=True))

    def test_broken_zip_rejected(self):
        with self.assertRaisesRegex(ValueError, "XLSX_INVALID_ARCHIVE_OR_XML"):
            validated_xml(b"not zip")

    def test_archive_size_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "XLSX_ARCHIVE_SIZE"):
            validated_xml(b"x" * 20_001)

    def test_malformed_xml_is_rejected(self):
        parts = copy.deepcopy(FIXTURE_DATA["matrix"]["parts"])
        parts["xl/workbook.xml"] = "<not-closed>"
        with self.assertRaisesRegex(ValueError, "XLSX_INVALID_ARCHIVE_OR_XML"):
            validated_xml(archive(parts))


class SelectionIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.files = ["README.md", "LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "provenance/publication.json", "provenance/candidate-selection.json", *FIXTURES]
        for name in self.files:
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            if name in FIXTURES:
                kind = "matrix" if "/matrix/" in name else "coordinates"
                target.write_bytes(workbook(kind))
            else:
                target.write_text("Synthetic policy test fixture.\n")
        (self.root / "README.md").write_text("[matrix](" + FIXTURE_DATA["matrix"]["source_path"] + ")\n")
        license_hash = hashlib.sha256((self.root / "LICENSE").read_bytes()).hexdigest()
        (self.root / "provenance/publication.json").write_text(json.dumps({"license_sha256": license_hash, "publication_authorized": False}))
        self.selection = {"scope": "public_source_candidate", "repository": "omelet-ai/optimization-context-protocol", "visibility": "public", "publication_approved": False, "approval_status": "PENDING_EXACT_CANDIDATE_REVIEW", "license": "Apache-2.0", "files": self.files}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.root / "provenance/candidate-selection.json").write_text(json.dumps(self.selection))

    def check(self):
        with patch.object(verifier, "ROOT", self.root):
            return verifier.verify(selection_path="provenance/candidate-selection.json")

    def test_site_fonts_require_exact_upstream_bytes_paths_and_license(self):
        license_name = verifier.SITE_FONT_LICENSE
        fonts = list(verifier.SITE_FONTS)
        for name in [license_name, *fonts]:
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_bytes((ROOT / name).read_bytes())
            self.files.append(name)
        self.save()
        self.assertEqual(self.check()["status"], "PASS")
        original = (self.root / fonts[0]).read_bytes()
        (self.root / fonts[0]).write_bytes(original + b"x")
        with self.assertRaisesRegex(ValueError, "Unexpected site font"):
            self.check()
        (self.root / fonts[0]).write_bytes(original)
        alias = "site/assets/another.woff2"
        (self.root / alias).write_bytes(original)
        self.files.append(alias)
        self.save()
        with self.assertRaisesRegex(ValueError, "Unexpected site font"):
            self.check()
        self.files.remove(alias)
        self.save()
        (self.root / license_name).write_text("changed")
        with self.assertRaisesRegex(ValueError, "Missing or changed site font license"):
            self.check()

    def test_complete_candidate_selection_accepts_exact_workbooks_without_approval(self):
        result = self.check()
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["public_release_authorized"])

    def test_binary_does_not_bypass_missing_markdown_target(self):
        (self.root / "README.md").write_text("[not selected](missing.md)")
        with self.assertRaisesRegex(ValueError, "Link outside selection"):
            self.check()

    def test_candidate_cannot_inherit_approval(self):
        self.selection["publication_approved"] = True; self.save()
        with self.assertRaisesRegex(ValueError, "Repository approval does not match scope"):
            self.check()

    def test_new_workbook_path_is_not_generic_binary_allowance(self):
        name = "examples/arbitrary.xlsx"
        (self.root / name).write_bytes(workbook()); self.files.append(name); self.save()
        with self.assertRaisesRegex(ValueError, "XLSX_PATH_NOT_REVIEWED"):
            self.check()

    def test_existing_sensitive_text_scan_is_retained_for_xml(self):
        with patch.object(verifier, "reviewed_fixture_text", return_value="-----BEGIN " + "PRIVATE KEY-----"):
            with self.assertRaisesRegex(ValueError, "private_key"):
                self.check()

    def test_existing_forbidden_path_check_precedes_binary_policy(self):
        name = ".private/source.xlsx"
        (self.root / name).parent.mkdir(); (self.root / name).write_bytes(workbook())
        self.files.append(name); self.save()
        with self.assertRaisesRegex(ValueError, "Excluded repository path"):
            self.check()


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print(json.dumps({"status": "PASS" if result.wasSuccessful() and not result.skipped else "FAIL", "tests_run": result.testsRun,
                      "errors": len(result.errors), "failures": len(result.failures), "skipped": len(result.skipped),
                      "scope": "Exact synthetic XLSX source-selection policy; no publication approval", "publication_authorized": False}))
    raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
