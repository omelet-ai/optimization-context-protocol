"""Publication boundaries: reject drift, missing grants and unselected index files."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import verify_repository as guard


class RepositorySelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ocp-public-selection-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.selection = json.loads((ROOT / guard.SELECTION).read_text())
        for name in self.selection["files"]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.policy = json.loads((self.root / "provenance/publication.json").read_text())
        self.root_patch = patch.object(guard, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def save(self):
        (self.root / guard.SELECTION).write_text(json.dumps(self.selection))
        (self.root / "provenance/publication.json").write_text(json.dumps(self.policy))

    def test_01_scoped_source_approval(self):
        report = guard.verify()
        self.assertTrue(report["public_release_authorized"])
        self.assertEqual(report["files"], len(self.selection["files"]))

    def test_02_each_rights_grant_required(self):
        original = deepcopy(self.policy)
        for key in ("rights_approved", "license_approved", "patent_disclosure_approved", "publication_authorized"):
            with self.subTest(key=key):
                self.policy = deepcopy(original)
                self.policy[key] = False
                self.save()
                with self.assertRaises(ValueError): guard.verify()

    def test_03_inventory_mismatch(self):
        self.policy["public_allowlist"].remove("README.md")
        self.save()
        with self.assertRaises(ValueError): guard.verify()

    def test_04_no_duplicate_public_paths(self):
        self.policy["public_allowlist"].append("README.md")
        self.save()
        with self.assertRaises(ValueError): guard.verify()

    def test_05_license_integrity(self):
        (self.root / "LICENSE").write_text("Different license")
        with self.assertRaises(ValueError): guard.verify()

    def test_06_deployment_and_registry_stay_separate(self):
        original = deepcopy(self.policy)
        for key in ("registry_publication_authorized", "site_deployment_authorized", "trial_deployment_authorized"):
            with self.subTest(key=key):
                self.policy = deepcopy(original)
                self.policy[key] = True
                self.save()
                with self.assertRaises(ValueError): guard.verify()

    def test_07_target_is_exact(self):
        self.policy["repository"] = "example/another-repository"
        self.save()
        with self.assertRaises(ValueError): guard.verify()

    def test_08_cannot_allow_private_material(self):
        name = ".private/not-for-publication.txt"
        (self.root / name).parent.mkdir()
        (self.root / name).write_text("synthetic fixture")
        self.selection["files"].append(name)
        self.policy["public_allowlist"].append(name)
        self.save()
        with self.assertRaises(ValueError): guard.verify()

    def test_09_no_symlink_export(self):
        target = self.root / "NOTICE"
        target.unlink()
        target.symlink_to(self.root / "LICENSE")
        with self.assertRaises(ValueError): guard.verify()

    def test_10_secret_pattern_rejected(self):
        token = "gh" + "p_" + "a" * 30
        (self.root / "NOTICE").write_text(token)
        with self.assertRaises(ValueError): guard.verify()

    def test_11_missing_approval_record(self):
        self.policy["approval_record"] = "absent.md"
        self.save()
        with self.assertRaises(ValueError): guard.verify()

    def test_12_private_mode_cannot_claim_publication(self):
        self.selection.update(scope="private_repository_only", visibility="private", publication_approved=False)
        self.save()
        with self.assertRaises(ValueError): guard.verify()
        self.policy.update(publication_authorized=False, public_allowlist=[])
        self.save()
        self.assertFalse(guard.verify()["public_release_authorized"])

    def test_13_actual_index_must_equal_inventory(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "--", *self.selection["files"]], check=True)
        self.assertEqual(guard.verify(index=True)["files"], len(self.selection["files"]))
        (self.root / "unexpected.txt").write_text("synthetic fixture")
        subprocess.run(["git", "-C", str(self.root), "add", "unexpected.txt"], check=True)
        with self.assertRaises(ValueError): guard.verify(index=True)

    def test_14_build_verification_is_separate_gate(self):
        for verified, expected in ((False, 2), (True, 0)):
            self.policy["independent_build_verified"] = verified
            self.save()
            result = subprocess.run([sys.executable, "-B", "tools/check_public_release.py"],
                                    cwd=self.root, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == "__main__":
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(RepositorySelectionTests))
    print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}))
    sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
