"""Regression tests for gate control, using isolated synthetic check processes."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "harness.py"
spec = importlib.util.spec_from_file_location("ocp_development_harness", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Harness, HarnessError = module.Harness, module.HarnessError


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ocp-harness-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ("harness", "tools", "src", "checks"):
            (self.root / directory).mkdir()
        (self.root / "src/value.txt").write_text("original")
        (self.root / "tools/harness.py").write_text("test runtime identity")
        self.write_check("print('{\"status\": \"PASS\", \"tests_run\": 1}')")
        check = {"id": "actual-check", "argv": ["{python}", "-B", "checks/check.py"],
                 "timeout_seconds": 5, "expect": {"status": "PASS"}, "min_tests": 1}
        self.plan = {
            "schema": "ocp-development-harness/v1", "required_tasks": ["HARNESS-00"],
            "shared_inputs": ["harness/plan.json", "tools/harness.py"],
            "stages": [{"id": "H00", "title": "Control test", "tasks": ["HARNESS-00"],
                        "depends_on": [], "mode": "local", "inputs": ["src/", "checks/"],
                        "acceptance": "Synthetic check process; no product claims", "checks": [check]}],
        }
        self.save_plan()

    def write_check(self, code):
        (self.root / "checks/check.py").write_text(code + "\n")

    def save_plan(self):
        (self.root / "harness/plan.json").write_text(json.dumps(self.plan))

    def harness(self):
        self.save_plan()
        return Harness(self.root)

    def add_stage(self, sid="H01", mode="local", checks=None):
        self.plan["stages"].append({
            "id": sid, "title": sid, "tasks": ["HARNESS-00"], "depends_on": ["H00"],
            "mode": mode, "inputs": ["src/", "checks/"], "acceptance": "Test only",
            "checks": [] if checks is None else checks,
        })

    def state(self, harness, sid="H00"):
        return harness.statuses()[sid]["status"]

    def test_initial_gate_is_not_pass(self):
        self.assertEqual(self.state(self.harness()), "READY_TO_VERIFY")

    def test_success_requires_real_execution(self):
        harness = self.harness()
        report = harness.run("H00")
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["checks"][0]["returncode"], 0)
        self.assertEqual(self.state(harness), "PASS")

    def test_empty_checks_do_not_pass(self):
        self.plan["stages"][0]["checks"] = []
        harness = self.harness()
        self.assertEqual(self.state(harness), "READY_TO_IMPLEMENT")
        with self.assertRaises(HarnessError):
            harness.run("H00")

    def test_dependency_blocks_execution(self):
        self.add_stage(checks=self.plan["stages"][0]["checks"])
        harness = self.harness()
        with self.assertRaises(HarnessError):
            harness.run("H01")
        self.assertEqual(self.state(harness, "H01"), "BLOCKED")
        harness.run("H00")
        self.assertEqual(self.state(harness, "H01"), "READY_TO_VERIFY")

    def test_planned_child_opens_only_after_parent_pass(self):
        self.add_stage()
        harness = self.harness()
        harness.run("H00")
        self.assertEqual(self.state(harness, "H01"), "READY_TO_IMPLEMENT")

    def test_external_gate_cannot_be_run(self):
        self.add_stage("D00", "external")
        harness = self.harness()
        harness.run("H00")
        self.assertEqual(self.state(harness, "D00"), "WAITING_EXTERNAL")
        with self.assertRaises(HarnessError):
            harness.run("D00")

    def test_deferred_gate_never_runs(self):
        self.add_stage("F03", "deferred")
        harness = self.harness()
        self.assertEqual(self.state(harness, "F03"), "DEFERRED")
        with self.assertRaises(HarnessError):
            harness.run("F03")

    def test_source_edit_invalidates_success(self):
        harness = self.harness()
        harness.run("H00")
        (self.root / "src/value.txt").write_text("changed")
        self.assertEqual(self.state(harness), "STALE")

    def test_added_source_invalidates_success(self):
        harness = self.harness()
        harness.run("H00")
        (self.root / "src/new.txt").write_text("new")
        self.assertEqual(self.state(harness), "STALE")

    def test_deleted_source_invalidates_success(self):
        harness = self.harness()
        harness.run("H00")
        (self.root / "src/value.txt").unlink()
        self.assertEqual(self.state(harness), "STALE")

    def test_suite_edit_invalidates_success(self):
        harness = self.harness()
        harness.run("H00")
        (self.root / "tools/harness.py").write_text("new runner")
        self.assertEqual(self.state(harness), "STALE")

    def test_added_check_makes_previous_success_stale(self):
        harness = self.harness()
        harness.run("H00")
        check = dict(self.plan["stages"][0]["checks"][0])
        check["id"] = "new-check"
        self.plan["stages"][0]["checks"].append(check)
        self.assertEqual(self.state(self.harness()), "STALE")

    def test_parent_rerun_invalidates_child_evidence(self):
        self.add_stage(checks=self.plan["stages"][0]["checks"])
        harness = self.harness()
        harness.run("H00")
        harness.run("H01")
        self.assertEqual(self.state(harness, "H01"), "PASS")
        harness.run("H00")
        self.assertEqual(self.state(harness, "H01"), "STALE")

    def test_latest_failure_does_not_fall_back_to_pass(self):
        harness = self.harness()
        harness.run("H00")
        self.write_check("raise SystemExit(7)")
        result = harness.run("H00")
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(self.state(harness), "FAIL")
        self.assertEqual(len(list(harness.runs.glob("H00-*.json"))), 2)

    def test_timeout_is_failure(self):
        self.plan["stages"][0]["checks"][0]["timeout_seconds"] = 0.05
        self.write_check("import time; time.sleep(2)")
        report = self.harness().run("H00")
        self.assertEqual(report["result"], "FAIL")
        self.assertTrue(report["checks"][0]["timed_out"])

    def test_zero_tests_cannot_pass(self):
        self.write_check("print('{\"status\": \"PASS\", \"tests_run\": 0}')")
        self.assertEqual(self.harness().run("H00")["result"], "FAIL")

    def test_exit_zero_without_json_is_failure(self):
        self.write_check("print('Everything is fine')")
        self.assertEqual(self.harness().run("H00")["result"], "FAIL")

    def test_claimed_failure_with_exit_zero_is_failure(self):
        self.write_check("print('{\"status\": \"FAIL\", \"tests_run\": 1}')")
        self.assertEqual(self.harness().run("H00")["result"], "FAIL")

    def test_boolean_test_count_is_not_integer_evidence(self):
        self.write_check("print('{\"status\": \"PASS\", \"tests_run\": true}')")
        self.assertEqual(self.harness().run("H00")["result"], "FAIL")

    def test_source_mutation_during_check_is_stale(self):
        self.write_check("from pathlib import Path\nPath('src/value.txt').write_text('mutated')\n"
                         "print('{\"status\": \"PASS\", \"tests_run\": 1}')")
        self.assertEqual(self.harness().run("H00")["result"], "STALE")

    def test_malformed_latest_evidence_is_not_ignored(self):
        harness = self.harness()
        harness.run("H00")
        (harness.runs / "H00-9999.json").write_text("not json")
        self.assertEqual(self.state(harness), "INVALID_EVIDENCE")

    def test_incomplete_latest_evidence_blocks_old_pass(self):
        harness = self.harness()
        harness.run("H00")
        (harness.runs / "H00-9999.json").write_text('{"result":"INCOMPLETE"}')
        self.assertEqual(self.state(harness), "INCOMPLETE")

    def test_pass_without_check_evidence_is_invalid(self):
        harness = self.harness()
        harness.run("H00")
        (harness.runs / "H00-9999.json").write_text('{"result":"PASS"}')
        self.assertEqual(self.state(harness), "INVALID_EVIDENCE")

    def test_lock_prevents_overlapping_runs(self):
        harness = self.harness()
        (self.root / ".harness").mkdir()
        (self.root / ".harness/run.lock").write_text("active")
        with self.assertRaises(HarnessError):
            harness.run("H00")

    def test_secrets_are_not_forwarded_to_checks(self):
        self.write_check("import os\nassert 'OCP_HARNESS_TEST_SECRET' not in os.environ\n"
                         "print('{\"status\": \"PASS\", \"tests_run\": 1}')")
        with patch.dict(os.environ, {"OCP_HARNESS_TEST_SECRET": "synthetic-marker"}):
            self.assertEqual(self.harness().run("H00")["result"], "PASS")

    def test_symlink_input_is_rejected(self):
        (self.root / "src/link").symlink_to(self.root / "checks/check.py")
        with self.assertRaises(HarnessError):
            self.harness().run("H00")

    def test_symlink_evidence_directory_is_rejected(self):
        (self.root / ".harness").symlink_to(self.root / "src", target_is_directory=True)
        with self.assertRaises(HarnessError):
            self.harness()

    def test_symlink_evidence_report_is_rejected(self):
        harness = self.harness()
        harness.run("H00")
        (harness.runs / "H00-9999.json").symlink_to(self.root / "src/value.txt")
        with self.assertRaises(HarnessError):
            harness.statuses()

    def test_parent_traversal_is_rejected(self):
        self.plan["stages"][0]["inputs"] = ["../outside"]
        with self.assertRaises(HarnessError):
            self.harness()

    def test_cycle_is_rejected(self):
        self.add_stage()
        self.plan["stages"][0]["depends_on"] = ["H01"]
        with self.assertRaises(HarnessError):
            self.harness()

    def test_unknown_dependency_is_rejected(self):
        self.plan["stages"][0]["depends_on"] = ["H99"]
        with self.assertRaises(HarnessError):
            self.harness()

    def test_unmapped_task_is_rejected(self):
        self.plan["required_tasks"].append("OSS-99")
        with self.assertRaises(HarnessError):
            self.harness()

    def test_nonlocal_check_configuration_is_rejected(self):
        self.plan["stages"][0]["mode"] = "external"
        with self.assertRaises(HarnessError):
            self.harness()

    def test_missing_executable_is_failure(self):
        self.plan["stages"][0]["checks"][0]["argv"] = ["/this-executable-does-not-exist"]
        report = self.harness().run("H00")
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["checks"][0]["reason"], "command_unavailable")

    def test_records_verified_counts_without_arbitrary_payload(self):
        self.write_check("print('{\"status\":\"PASS\",\"tests_run\":1,\"token\":\"synthetic-secret\"}')")
        report=self.harness().run("H00")
        self.assertEqual(report["checks"][0]["verified_report"],{"tests_run":1})
        self.assertNotIn("synthetic-secret",json.dumps(report))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HarnessTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    passed = result.wasSuccessful() and result.testsRun > 0 and not result.skipped
    print(json.dumps({"status": "PASS" if passed else "FAIL", "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}))
    sys.exit(0 if passed else 1)
