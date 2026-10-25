"""Private, local timing records for real DX studies; never an H12 approval."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import tempfile

SCHEMA = "ocp-dx-observation/v1"
ROUTES = ("no-key", "omelet-trial", "byo")
TASKS = ("first-run", "own-input", "integrate-app", "independent-engine")
EVENTS = ("key-requested", "key-issued", "support-start", "support-end", "complete", "failed")


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO string")
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Timestamp needs a timezone")
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(record):
    if set(record) != {"schema", "participant", "actor", "route", "task", "artifact_sha256",
                       "suite_version", "candidate_version", "started_at", "events"}:
        raise ValueError("Unexpected observation fields")
    if record.get("schema") != SCHEMA or not re.fullmatch(r"p[0-9]{2,4}", record.get("participant", "")):
        raise ValueError("Invalid record or pseudonymous participant ID")
    if record.get("actor") not in ("external-human", "automated-rehearsal"):
        raise ValueError("Explicit actor provenance is required")
    if record.get("route") not in ROUTES or record.get("task") not in TASKS:
        raise ValueError("Unknown route or task")
    if not re.fullmatch(r"[0-9a-f]{64}", record.get("artifact_sha256", "")):
        raise ValueError("An exact candidate artifact hash is required")
    if not record.get("suite_version") or not record.get("candidate_version"):
        raise ValueError("Candidate and checker versions are required")
    previous = timestamp(record["started_at"])
    events = record.get("events")
    if not isinstance(events, list):
        raise ValueError("Events must be a list")
    terminal, support, key = False, False, False
    for event in events:
        kind = event.get("kind")
        expected = {"kind", "at", "evidence_sha256", "work"} if kind == "complete" else {"kind", "at"}
        if set(event) != expected:
            raise ValueError("Unexpected event fields")
        at = timestamp(event["at"])
        if kind not in EVENTS or at < previous or terminal:
            raise ValueError("Invalid event order or event after completion")
        if kind == "support-start":
            if support:
                raise ValueError("Support already started")
            support = True
        elif kind == "support-end":
            if not support:
                raise ValueError("Support has not started")
            support = False
        elif kind == "key-requested":
            if record["route"] != "omelet-trial" or key:
                raise ValueError("Invalid key request")
            key = True
        elif kind == "key-issued":
            if not key:
                raise ValueError("No pending key request")
            key = False
        elif kind in ("complete", "failed"):
            terminal = True
            if kind == "complete":
                if support or key:
                    raise ValueError("Close pending support/key wait before completion")
                if not re.fullmatch(r"[0-9a-f]{64}", event.get("evidence_sha256", "")):
                    raise ValueError("Completion requires a saved evidence hash")
                if event.get("work") not in ("sample-replay", "independent-work"):
                    raise ValueError("Distinguish sample replay from independent work")
                if record["task"] == "first-run" and event["work"] != "sample-replay":
                    raise ValueError("First run is not an independent implementation")
        previous = at
    return record


def summarize(records):
    records = [validate(record) for record in records]
    seen = set()
    for record in records:
        key = (record["actor"], record["participant"], record["route"], record["task"], record["started_at"])
        if key in seen:
            raise ValueError("Duplicate observation")
        seen.add(key)
    human = [r for r in records if r["actor"] == "external-human"]
    identities = {(r["candidate_version"], r["suite_version"], r["artifact_sha256"]) for r in human}
    if len(identities) > 1:
        raise ValueError("Analyze each pinned candidate and suite separately")
    rows = []
    # Retakes never replace a failed first attempt or restart the clock.
    for route in ROUTES:
        selected = {}
        for record in sorted(human, key=lambda r: timestamp(r["started_at"])):
            if record["route"] == route:
                selected.setdefault((record["participant"], record["task"]), record)
        for task in TASKS:
            group = [r for (_, t), r in selected.items() if t == task]
            target = {"first-run": 900, "integrate-app": 3600}.get(task)
            complete, within, unassisted, durations, independent = 0, 0, 0, [], set()
            assisted = 0
            for record in group:
                assisted += any(e["kind"] == "support-start" for e in record["events"])
                last = record["events"][-1] if record["events"] else {}
                if last.get("kind") == "complete":
                    complete += 1
                    elapsed = (timestamp(last["at"]) - timestamp(record["started_at"])).total_seconds()
                    durations.append(elapsed)
                    within += target is not None and elapsed <= target
                    unassisted += target is not None and elapsed <= target and not any(
                        e["kind"] == "support-start" for e in record["events"])
                    if task != "first-run" and last["work"] == "independent-work":
                        independent.add(record["participant"])
            rows.append({"route": route, "task": task, "participants": len(group), "completed": complete,
                         "target_seconds": target, "within_target": within if target is not None else None,
                         "assisted": assisted, "independent_participants": sorted(independent),
                         "within_target_without_support": unassisted if target is not None else None,
                         "completed_median_seconds": statistics.median(durations) if durations else None,
                         "incomplete_or_failed": len(group) - complete})
    return {"status": "OBSERVATIONS_ONLY", "h12_pass": False,
            "scope": "Recorded timing, not verification of participant identity, consent, or independent acceptance",
            "external_participants": len({r["participant"] for r in human}),
            "independent_participants": sorted({p for row in rows for p in row["independent_participants"]}),
            "automated_records_excluded": len(records) - len(human), "routes_and_tasks": rows}


def load(path):
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Invalid observation file")
    return validate(json.loads(path.read_text()))


def save(path, record, *, create=False):
    validate(record)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("Observation files must not traverse symlinks")
    path.parent.mkdir(parents=True, exist_ok=True)
    # No keys, real names, free-form input, responses or support notes are stored.
    content = json.dumps(record, indent=2) + "\n"
    if create:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
    else:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            pending = Path(stream.name)
            stream.write(content)
        try:
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("record", type=Path)
    start.add_argument("--participant", required=True)
    start.add_argument("--actor", choices=("external-human", "automated-rehearsal"), required=True)
    start.add_argument("--route", choices=ROUTES, required=True)
    start.add_argument("--task", choices=TASKS, required=True)
    start.add_argument("--artifact", type=Path, required=True)
    start.add_argument("--candidate-version", required=True)
    start.add_argument("--suite-version", required=True)
    event = commands.add_parser("event")
    event.add_argument("record", type=Path)
    event.add_argument("kind", choices=EVENTS)
    event.add_argument("--evidence", type=Path)
    event.add_argument("--work", choices=("sample-replay", "independent-work"))
    report = commands.add_parser("report")
    report.add_argument("records", type=Path, nargs="+")
    args = parser.parse_args()
    if args.command == "start":
        record = {"schema": SCHEMA, "participant": args.participant, "actor": args.actor,
                  "route": args.route, "task": args.task, "artifact_sha256": sha(args.artifact),
                  "candidate_version": args.candidate_version, "suite_version": args.suite_version,
                  "started_at": now(), "events": []}
        save(args.record, record, create=True)
        print(json.dumps({"status": "STARTED", "human_acceptance_verified": False}))
    elif args.command == "event":
        record = load(args.record)
        item = {"kind": args.kind, "at": now()}
        if args.kind == "complete":
            if not args.evidence or not args.work:
                raise ValueError("Completion needs --evidence and --work")
            item.update(evidence_sha256=sha(args.evidence), work=args.work)
        record["events"].append(item)
        save(args.record, record)
        print(json.dumps({"status": "RECORDED", "human_acceptance_verified": False}))
    else:
        print(json.dumps(summarize([load(path) for path in args.records]), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}), file=sys.stderr)
        sys.exit(1)
