"""Local, fail-closed development gates; not a product conformance runner."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import subprocess
import sys
import time
import uuid


class HarnessError(ValueError):
    pass


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise HarnessError("Invalid project-relative path")
    path = PurePosixPath(value.rstrip("/"))
    if path.is_absolute() or ".." in path.parts or str(path) == ".":
        raise HarnessError("Unsafe project-relative path: " + value)
    if path.parts[0] in {".harness", ".git"}:
        raise HarnessError("Evidence and Git metadata cannot be source inputs")
    return path.as_posix()


class Harness:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.plan = json.loads((self.root / "harness/plan.json").read_text())
        self.validate()
        self.stages = {s["id"]: s for s in self.plan["stages"]}
        self.runs = self.root / ".harness/runs"
        if any(p.is_symlink() for p in (self.root / ".harness", self.runs)):
            raise HarnessError("Evidence directories cannot be symlinks")

    def validate(self):
        plan = self.plan
        if plan.get("schema") != "ocp-development-harness/v1":
            raise HarnessError("Unsupported harness schema")
        stages = plan.get("stages", [])
        if not stages or not isinstance(stages, list):
            raise HarnessError("A nonempty stage list is required")
        ids = [s["id"] for s in stages]
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[HDF][0-9]{2}", x) for x in ids):
            raise HarnessError("Duplicate or invalid stage ID")
        covered = set()
        for path in plan.get("shared_inputs", []):
            relative_path(path)
        for stage in stages:
            if stage.get("mode") not in {"local", "external", "deferred"}:
                raise HarnessError("Invalid mode: " + stage["id"])
            if not stage.get("title") or not stage.get("acceptance") or not stage.get("tasks"):
                raise HarnessError("Title, acceptance and task mapping are required")
            covered.update(stage["tasks"])
            dependencies = stage.get("depends_on", [])
            if len(set(dependencies)) != len(dependencies) or any(d not in ids for d in dependencies):
                raise HarnessError("Unknown or duplicate dependency")
            if not stage.get("inputs"):
                raise HarnessError("Explicit source inputs are required")
            for path in stage["inputs"]:
                relative_path(path)
            checks = stage.get("checks")
            if not isinstance(checks, list):
                raise HarnessError("Checks must be a list")
            if stage["mode"] != "local" and checks:
                raise HarnessError("External evidence verification is not implemented")
            check_ids = set()
            for check in checks:
                cid = check.get("id")
                if not isinstance(cid, str) or not cid or cid in check_ids:
                    raise HarnessError("Duplicate or missing check ID")
                check_ids.add(cid)
                argv = check.get("argv")
                if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
                    raise HarnessError("Use an explicit nonempty argv array")
                timeout = check.get("timeout_seconds")
                if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
                    raise HarnessError("Checks need a bounded timeout")
                if not isinstance(check.get("expect"), dict) or check["expect"].get("status") != "PASS":
                    raise HarnessError("Checks must return a JSON PASS report")
                if "min_tests" in check and (type(check["min_tests"]) is not int or check["min_tests"] < 1):
                    raise HarnessError("Test checks must require a positive count")
        missing = set(plan.get("required_tasks", [])) - covered
        if missing:
            raise HarnessError("Unmapped tasks: " + ", ".join(sorted(missing)))
        graph = {s["id"]: s.get("depends_on", []) for s in stages}
        visited, active = set(), set()

        def visit(sid):
            if sid in active:
                raise HarnessError("Cyclic gate dependencies")
            if sid in visited:
                return
            active.add(sid)
            for dep in graph[sid]:
                visit(dep)
            active.remove(sid)
            visited.add(sid)

        for sid in ids:
            visit(sid)

    def checked_path(self, path):
        target = self.root / relative_path(path)
        current = target
        while current != self.root:
            if current.is_symlink():
                raise HarnessError("Symlink source input: " + path)
            current = current.parent
        if not target.resolve().is_relative_to(self.root):
            raise HarnessError("Source input escapes workspace")
        return target

    def snapshot(self, stage):
        files = {}
        for name in self.plan.get("shared_inputs", []) + stage["inputs"]:
            target = self.checked_path(name)
            if not target.exists():
                raise HarnessError("Missing input: " + name)
            paths = sorted(target.rglob("*")) if target.is_dir() else [target]
            # Include directory membership so additions, removals and empty directories matter.
            files[relative_path(name)] = "directory" if target.is_dir() else "file"
            for path in paths:
                relative = path.relative_to(self.root).as_posix()
                self.checked_path(relative)
                if path.is_file():
                    files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                elif path.is_dir():
                    files[relative] = "directory"
                else:
                    raise HarnessError("Non-regular source input: " + relative)
        return files

    def latest(self, sid):
        matches = sorted(self.runs.glob(sid + "-*.json")) if self.runs.exists() else []
        if not matches:
            return None, None
        path = matches[-1]
        if path.is_symlink():
            raise HarnessError("Evidence reports cannot be symlinks")
        raw = path.read_bytes()
        try:
            report = json.loads(raw)
            if not isinstance(report, dict):
                raise ValueError("Not an object")
            return report, hashlib.sha256(raw).hexdigest()
        except (ValueError, UnicodeError):
            return {"result": "INVALID_EVIDENCE"}, hashlib.sha256(raw).hexdigest()

    def input_record(self, stage, states):
        return {
            "files": self.snapshot(stage),
            "stage_definition": stage,
            "environment": {"python": sys.version, "platform": platform.platform()},
            "dependencies": {d: states[d]["evidence_sha256"] for d in stage["depends_on"]},
        }

    def statuses(self):
        states = {}

        def visit(sid):
            if sid in states:
                return
            stage = self.stages[sid]
            for dep in stage["depends_on"]:
                visit(dep)
            result = {"id": sid, "title": stage["title"], "tasks": stage["tasks"]}
            blocked = [d for d in stage["depends_on"] if states[d]["status"] != "PASS"]
            if stage["mode"] == "deferred":
                result.update(status="DEFERRED")
            elif blocked:
                result.update(status="BLOCKED", dependencies=blocked)
            elif stage["mode"] == "external":
                result.update(status="WAITING_EXTERNAL", reason="Real evidence and scoped authorization required")
            elif not stage["checks"]:
                result.update(status="READY_TO_IMPLEMENT")
            else:
                report, sha = self.latest(sid)
                if report is None:
                    result.update(status="READY_TO_VERIFY")
                elif report.get("result") != "PASS":
                    status = report.get("result")
                    result.update(status=status if status in {"FAIL", "STALE", "INCOMPLETE"} else "INVALID_EVIDENCE")
                else:
                    checks = report.get("checks", [])
                    recorded_inputs = report.get("inputs")
                    recorded_stage = recorded_inputs.get("stage_definition", {}) if isinstance(recorded_inputs, dict) else {}
                    recorded_checks = recorded_stage.get("checks", []) if isinstance(recorded_stage, dict) else []
                    valid = (report.get("stage") == sid and report.get("schema") == "ocp-gate-run/v1"
                             and report.get("finished_at") and isinstance(checks, list)
                             and isinstance(recorded_checks, list) and len(recorded_checks) > 0
                             and len(checks) == len(recorded_checks)
                             and all(isinstance(c, dict) and isinstance(expected, dict)
                                     and c.get("id") == expected.get("id")
                                     and c.get("result") == "PASS" and c.get("returncode") == 0
                                     and c.get("timed_out") is False
                                     for c, expected in zip(checks, recorded_checks)))
                    if not valid:
                        result.update(status="INVALID_EVIDENCE")
                    else:
                        try:
                            current = digest(self.input_record(stage, states))
                            valid_inputs = report.get("input_digest") == digest(report.get("inputs")) == current
                            result.update(status="PASS" if valid_inputs else "STALE", evidence_sha256=sha,
                                          run_id=report.get("run_id"))
                        except HarnessError as exc:
                            result.update(status="STALE", reason=str(exc))
            states[sid] = result

        for sid in self.stages:
            visit(sid)
        return states

    def execute_check(self, check):
        argv = [sys.executable if x == "{python}" else x for x in check["argv"]]
        env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT") if key in os.environ}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
        started = time.monotonic()
        result = {"id": check["id"], "argv": check["argv"], "result": "FAIL", "timed_out": False}
        try:
            process = subprocess.Popen(argv, cwd=self.root, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=(os.name == "posix"))
            try:
                stdout, stderr = process.communicate(timeout=check["timeout_seconds"])
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.communicate()
                raise
            result.update(returncode=process.returncode,
                          stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                          stderr_sha256=hashlib.sha256(stderr).hexdigest())
            if process.returncode != 0:
                result["reason"] = "nonzero_exit"
            else:
                try:
                    payload = json.loads(stdout)
                    matched = isinstance(payload, dict) and all(
                        key in payload and type(payload[key]) is type(value) and payload[key] == value
                        for key, value in check["expect"].items())
                    if "min_tests" in check:
                        matched = (matched and type(payload.get("tests_run")) is int
                                   and payload["tests_run"] >= check["min_tests"])
                    result.update(result="PASS" if matched else "FAIL", reason="verified_report" if matched else "report_mismatch")
                    if matched:
                        # Deliberately retain only technical report metadata, never raw logs or arbitrary payloads.
                        result["verified_report"] = {key: payload[key] for key in (
                            "tests_run", "failures", "errors", "skipped", "scope", "artifact_sha256", "versions"
                        ) if key in payload}
                except (ValueError, UnicodeError, AttributeError):
                    result["reason"] = "invalid_json_report"
        except subprocess.TimeoutExpired:
            result.update(timed_out=True, returncode=None, reason="timeout")
        except OSError:
            result.update(returncode=None, reason="command_unavailable")
        result["duration_seconds"] = round(time.monotonic() - started, 4)
        return result

    def run(self, sid):
        if sid not in self.stages:
            raise HarnessError("Unknown stage: " + sid)
        stage = self.stages[sid]
        states = self.statuses()
        if states[sid]["status"] in {"BLOCKED", "WAITING_EXTERNAL", "DEFERRED", "READY_TO_IMPLEMENT"}:
            raise HarnessError("Gate cannot run: " + sid + " " + states[sid]["status"])
        self.runs.mkdir(parents=True, exist_ok=True)
        lock = self.root / ".harness/run.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise HarnessError("Another run or interrupted lock exists; inspect .harness/run.lock")
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(json.dumps({"pid": os.getpid(), "stage": sid, "started_at": now()}))
            # Read again inside the lock, including every prerequisite.
            states = self.statuses()
            if any(states[d]["status"] != "PASS" for d in stage["depends_on"]):
                raise HarnessError("Prerequisite changed before execution")
            inputs = self.input_record(stage, states)
            run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
            report = {"schema": "ocp-gate-run/v1", "stage": sid, "run_id": run_id,
                      "started_at": now(), "finished_at": None, "result": "INCOMPLETE", "inputs": inputs,
                      "input_digest": digest(inputs), "checks": [], "scope": stage["acceptance"],
                      "not_verified": ["Other gates", "Publication authorization", "Production or customer acceptance"]}
            destination = self.runs / (sid + "-" + run_id + ".json")
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            for check in stage["checks"]:
                outcome = self.execute_check(check)
                report["checks"].append(outcome)
                if outcome["result"] != "PASS":
                    break
            report["result"] = "PASS" if len(report["checks"]) == len(stage["checks"]) and all(
                c["result"] == "PASS" for c in report["checks"]) else "FAIL"
            try:
                after = self.statuses()
                if any(after[d]["status"] != "PASS" for d in stage["depends_on"]):
                    report["result"] = "STALE"
                elif digest(self.input_record(stage, after)) != report["input_digest"]:
                    report["result"] = "STALE"
            except HarnessError:
                report["result"] = "STALE"
            report["finished_at"] = now()
            pending = destination.with_suffix(".tmp")
            pending.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            pending.replace(destination)
            return report
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "status", "next", "run"])
    parser.add_argument("stage", nargs="?")
    args = parser.parse_args()
    try:
        harness = Harness(Path(__file__).resolve().parents[1])
        if args.command == "validate":
            output = {"status": "PASS", "scope": "harness_plan_only", "stages": len(harness.stages)}
        elif args.command == "run":
            if not args.stage:
                raise HarnessError("run needs a stage ID")
            report = harness.run(args.stage)
            output = {"stage": args.stage, "status": report["result"], "run_id": report["run_id"],
                      "checks": report["checks"], "scope": report["scope"]}
        else:
            states = list(harness.statuses().values())
            if args.command == "next":
                output = {"technical": [s for s in states if s["status"] in {
                    "READY_TO_IMPLEMENT", "READY_TO_VERIFY", "FAIL", "STALE", "INCOMPLETE", "INVALID_EVIDENCE"}],
                    "external": [s for s in states if s["status"] == "WAITING_EXTERNAL"]}
            else:
                output = {"scope": "development_gates_not_product_certification", "stages": states}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if args.command != "run" or report["result"] == "PASS" else 1
    except (HarnessError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
