"""False-success and timing regressions; synthetic records are never study evidence."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
import sys

from dx_study import load, save, summarize, validate

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def record(participant="p01", seconds=600, task="first-run", route="no-key"):
    return {"schema": "ocp-dx-observation/v1", "participant": participant, "actor": "external-human",
            "route": route, "task": task, "artifact_sha256": "a" * 64,
            "candidate_version": "0.1.0-candidate", "suite_version": "0.1.0-candidate",
            "started_at": START.isoformat(), "events": [{"kind": "complete",
            "at": (START + timedelta(seconds=seconds)).isoformat(), "evidence_sha256": "b" * 64,
            "work": "sample-replay" if task == "first-run" else "independent-work"}]}


def row(report, route="no-key", task="first-run"):
    return next(r for r in report["routes_and_tasks"] if r["route"] == route and r["task"] == task)


class StudyTests(unittest.TestCase):
    def test_no_observations_cannot_be_human_success(self):
        result = summarize([])
        self.assertEqual(result["external_participants"], 0)
        self.assertFalse(result["h12_pass"])
        self.assertIsNone(row(result)["completed_median_seconds"])

    def test_success_does_not_authorize_h12(self):
        self.assertFalse(summarize([record()])["h12_pass"])

    def test_automated_runs_never_count_as_people(self):
        r = record(); r["actor"] = "automated-rehearsal"
        result = summarize([r])
        self.assertEqual(result["external_participants"], 0)
        self.assertEqual(result["automated_records_excluded"], 1)

    def test_slow_and_unfinished_attempts_remain_in_denominator(self):
        data = [record(f"p{i:02d}", seconds=600) for i in range(1, 6)]
        data[3]["events"] = []; data[4] = record("p05", seconds=901)
        r = row(summarize(data))
        self.assertEqual((r["participants"], r["within_target"], r["incomplete_or_failed"]), (5, 3, 1))

    def test_assisted_success_is_not_document_only_success(self):
        r = record()
        r["events"][0:0] = [{"kind": "support-start", "at": START.isoformat()},
                            {"kind": "support-end", "at": (START + timedelta(seconds=30)).isoformat()}]
        result = row(summarize([r]))
        self.assertEqual(result["within_target"], 1)
        self.assertEqual(result["within_target_without_support"], 0)

    def test_key_wait_is_not_subtracted(self):
        r = record(seconds=960, route="omelet-trial")
        r["events"][0:0] = [{"kind": "key-requested", "at": START.isoformat()},
                            {"kind": "key-issued", "at": (START + timedelta(seconds=900)).isoformat()}]
        result = row(summarize([r]), route="omelet-trial")
        self.assertEqual(result["completed_median_seconds"], 960)
        self.assertEqual(result["within_target"], 0)

    def test_first_attempt_failure_cannot_be_replaced_by_retake(self):
        first = record(); first["events"][0] = {"kind": "failed", "at": (START + timedelta(seconds=10)).isoformat()}
        retry = record(seconds=900); retry["started_at"] = (START + timedelta(seconds=800)).isoformat()
        result = row(summarize([retry, first]))
        self.assertEqual(result["participants"], 1)
        self.assertEqual(result["completed"], 0)

    def test_routes_are_not_pooled(self):
        data = [record("p01", 1), record("p02", 1000, route="omelet-trial")]
        result = summarize(data)
        self.assertEqual(row(result)["within_target"], 1)
        self.assertEqual(row(result, "omelet-trial")["within_target"], 0)

    def test_sample_replay_is_not_independent_adoption(self):
        r = record(task="own-input"); r["events"][0]["work"] = "sample-replay"
        self.assertEqual(summarize([r])["independent_participants"], [])

    def test_independence_counts_unique_participants(self):
        result = summarize([record(task="own-input"), record(task="integrate-app"), record("p02", task="independent-engine")])
        self.assertEqual(result["independent_participants"], ["p01", "p02"])

    def test_app_integration_60_minute_boundary(self):
        r = row(summarize([record(task="integrate-app", seconds=3601)]), task="integrate-app")
        self.assertEqual(r["within_target"], 0)

    def test_no_invented_time_target_for_engine_authoring(self):
        r = row(summarize([record(task="independent-engine", seconds=4000)]), task="independent-engine")
        self.assertIsNone(r["target_seconds"])
        self.assertIsNone(r["within_target"])
        self.assertEqual(r["completed_median_seconds"], 4000)

    def test_completion_requires_evidence(self):
        r = record(); del r["events"][0]["evidence_sha256"]
        with self.assertRaises(ValueError): validate(r)

    def test_timestamp_rollback_and_missing_timezone_rejected(self):
        for at in ((START - timedelta(seconds=1)).isoformat(), "2026-01-01T00:00:00"):
            r = record(); r["events"][0]["at"] = at
            with self.assertRaises(ValueError): validate(r)

    def test_cannot_resume_a_finished_attempt(self):
        r = record(); r["events"].append({"kind": "support-start", "at": (START + timedelta(seconds=900)).isoformat()})
        with self.assertRaises(ValueError): validate(r)

    def test_incomplete_key_wait_cannot_complete(self):
        r = record(route="omelet-trial"); r["events"].insert(0, {"kind": "key-requested", "at": START.isoformat()})
        with self.assertRaises(ValueError): validate(r)

    def test_mixed_artifacts_and_duplicate_observations_rejected(self):
        r = record("p02"); r["artifact_sha256"] = "c" * 64
        for records in ([record(), r], [record(), record()]):
            with self.assertRaises(ValueError): summarize(records)

    def test_personal_names_and_free_text_not_accepted(self):
        r = record(); r["participant"] = "person@example.invalid"
        with self.assertRaises(ValueError): validate(r)
        r = record(); r["secret"] = "must-not-be-stored"
        with self.assertRaises(ValueError): validate(r)

    def test_private_permissions_and_no_overwriting_start(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / "record.json"
            save(path, record(), create=True)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): save(path, record(), create=True)
            save(path, record(seconds=5))
            self.assertEqual(load(path), record(seconds=5))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_symlink_records_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / "real.json"; save(path, record(), create=True)
            link = Path(temp).resolve() / "link.json"; link.symlink_to(path)
            with self.assertRaises(ValueError): save(link, record())
            with self.assertRaises(ValueError): load(link)


if __name__ == "__main__":
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(StudyTests))
    passed = result.wasSuccessful() and result.testsRun >= 20 and not result.skipped
    print(json.dumps({"status": "PASS" if passed else "FAIL", "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                      "scope": "Synthetic timing-tool regressions only; zero external participants; not H12 acceptance"}))
    sys.exit(0 if passed else 1)
