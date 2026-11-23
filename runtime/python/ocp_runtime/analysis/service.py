"""Persisted analysis plans with bounded child jobs and resumable supervision.

SQLite records are optimization computation state, not customer application data.
The controller executes only declared candidate requests, with no automatic retry
of failed or uncertain calculations. Worker/protocol implementations are reused.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
import json
import math
import time
import uuid

from ocp_runtime._worker_contract.jobs.model import TERMINAL
from ocp_candidate.server_package import at, PackageError
from ocp_runtime.execution.jobs import JobService
from ocp_runtime.execution.sqlite_store import SQLiteJobStore
from .plans import AnalysisError, build_plan, verify_plan


class AnalysisService:
    def __init__(self, service, database, *, max_job_seconds=30):
        if type(max_job_seconds) not in (float, int) or not math.isfinite(max_job_seconds) or max_job_seconds <= 0:
            raise ValueError("INVALID_JOB_BUDGET")
        self.service, self.store, self.max_job_seconds = service, SQLiteJobStore(database), max_job_seconds
        with self.store._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, body TEXT NOT NULL)")

    @staticmethod
    def _read(db, principal, analysis_id):
        row = db.execute("SELECT body FROM analyses WHERE id=? AND tenant=?", (analysis_id, principal.tenant)).fetchone()
        if not row:
            raise AnalysisError("ANALYSIS_NOT_FOUND")
        return json.loads(row[0])

    @staticmethod
    def _write(db, body):
        db.execute("UPDATE analyses SET body=? WHERE id=?", (json.dumps(body, allow_nan=False), body["id"]))

    def plan(self, principal, playbook_id, input_value, configuration, **options):
        JobService._authorize(principal, "read")
        plan = build_plan(self.service, playbook_id, input_value, configuration, **options)
        body = {"id": str(uuid.uuid4()), "plan": plan, "status": "planned", "cancel_requested": False,
                "created_at": datetime.now(UTC).isoformat(), "started_at": None, "deadline": None,
                "controller": None, "lease_until": 0, "attempts_started": 0,
                "candidates": [{"id": c["id"], "job_id": None, "status": "not_started"} for c in plan["candidates"]]}
        with self.store._transaction() as db:
            db.execute("INSERT INTO analyses VALUES (?,?,?)", (body["id"], principal.tenant, json.dumps(body)))
        return deepcopy(body)

    def status(self, principal, analysis_id):
        JobService._authorize(principal, "read")
        with self.store._transaction() as db:
            return self._read(db, principal, analysis_id)

    def cancel(self, principal, analysis_id):
        JobService._authorize(principal, "cancel")
        with self.store._transaction() as db:
            body = self._read(db, principal, analysis_id)
            if body["status"] not in {"completed", "stopped"}:
                body["cancel_requested"] = True
                if body["status"] == "planned":
                    body["status"] = "stopped"
                    body["stop_reason"] = "cancelled_before_execution"
                self._write(db, body)
            return body

    def _jobs(self, analysis_id, remaining):
        jobs = JobService(self.service, store=self.store, budget_seconds=max(0.01, min(self.max_job_seconds, remaining)))
        jobs.problem_type += "/analysis/" + analysis_id
        return jobs

    def _stop_child(self, jobs, principal, job):
        if job.status not in TERMINAL and getattr(self.service.connector, "isolation", None) == "local_process":
            return jobs.cancel(principal, job.id)
        return job

    def run(self, principal, analysis_id, *, expected_plan_fingerprint):
        JobService._authorize(principal, "execute")
        owner = str(uuid.uuid4())
        with self.store._transaction() as db:
            body = self._read(db, principal, analysis_id)
            if body["plan"]["plan_fingerprint"] != expected_plan_fingerprint:
                raise AnalysisError("PLAN_CONFIRMATION_MISMATCH")
            verify_plan(self.service, body["plan"])
            if body["status"] in {"completed", "stopped"}:
                return body
            now = time.time()
            if body["controller"] and body["lease_until"] > now:
                raise AnalysisError("ANALYSIS_ALREADY_RUNNING")
            body["controller"], body["lease_until"], body["status"] = owner, now + 5, "running"
            if body["started_at"] is None:
                body["started_at"], body["deadline"] = now, now + body["plan"]["budget"]["timeout_seconds"]
            self._write(db, body)
        futures = []
        with ThreadPoolExecutor(max_workers=body["plan"]["budget"]["concurrency"]) as pool:
            while True:
                with self.store._transaction() as db:
                    current = self._read(db, principal, analysis_id)
                    if current["controller"] != owner:
                        raise AnalysisError("CONTROLLER_LEASE_LOST")
                    body["cancel_requested"] = current["cancel_requested"]
                    body["lease_until"] = time.time() + 5
                    self._write(db, body)
                remaining = body["deadline"] - time.time()
                stopping = body["cancel_requested"] or remaining <= 0
                jobs = self._jobs(analysis_id, remaining)
                for entry in body["candidates"]:
                    if entry["job_id"] is not None:
                        job = jobs.get(principal, entry["job_id"])
                        if job is None:
                            entry.update(status="failed", error={"code": "CHILD_JOB_UNAVAILABLE"})
                            continue
                        if stopping and job.status not in TERMINAL:
                            job = self._stop_child(jobs, principal, job)
                        entry.update(status=job.status.value, result=job.result, error=job.error,
                                     cancel_requested=job.cancel_requested, attempt=job.attempt)
                # Existing queued/running jobs survive reconnect. A new worker
                # may claim queued work; an expired active lease becomes uncertain.
                for future in futures:
                    if future.done() and future.exception() is not None:
                        # Infrastructure failure is visible and stops new work.
                        # Do not turn a worker exception into a busy retry loop.
                        body["controller_error"] = {"code": "WORKER_CONTROLLER_FAILED"}
                        body["cancel_requested"], stopping = True, True
                futures = [f for f in futures if not f.done()]
                active = [e for e in body["candidates"] if e["status"] in {"queued", "running"}]
                if not stopping:
                    for entry, candidate in zip(body["candidates"], body["plan"]["candidates"]):
                        if len(active) >= body["plan"]["budget"]["concurrency"]:
                            break
                        if entry["status"] != "not_started":
                            continue
                        if body["attempts_started"] >= body["plan"]["budget"]["max_calls"] or time.time() >= body["deadline"]:
                            break
                        # Stable keys recover a submission whose response was lost.
                        job, _ = jobs.submit(principal, candidate["request"]["input"], candidate["request"]["configuration"], idempotency_key=analysis_id + ":" + entry["id"])
                        entry.update(job_id=job.id, status=job.status.value)
                        body["attempts_started"] += 1
                        active.append(entry)
                while not stopping and len(futures) < len(active):
                    futures.append(pool.submit(jobs.worker().run_once))
                if not active and (stopping or all(e["status"] != "not_started" for e in body["candidates"])):
                    body["status"] = "stopped" if stopping else "completed"
                    body["stop_reason"] = "controller_failure" if body.get("controller_error") else "cancel_requested" if body["cancel_requested"] else "time_budget" if remaining <= 0 else "candidates_finished"
                    body["finished_at"] = time.time()
                    body["controller"], body["lease_until"] = None, 0
                with self.store._transaction() as db:
                    fresh = self._read(db, principal, analysis_id)
                    if fresh["controller"] != owner:
                        raise AnalysisError("CONTROLLER_LEASE_LOST")
                    body["cancel_requested"] = body["cancel_requested"] or fresh["cancel_requested"]
                    self._write(db, body)
                if body["status"] in {"completed", "stopped"}:
                    return deepcopy(body)
                time.sleep(0.02)

    def compare(self, principal, analysis_id):
        body = self.status(principal, analysis_id)
        verify_plan(self.service, body["plan"])
        metric_id = body["plan"]["ranking_metric"]
        rows, eligible = [], []
        for entry in body["candidates"]:
            answer = entry.get("result")
            values, reason = {}, None
            if entry["status"] != "succeeded" or not answer or answer["solution_status"] not in {"optimal", "feasible"}:
                reason = "no_completed_solution"
            elif answer.get("evaluation") is not None and answer["evaluation"]["status"] != "pass":
                reason = "checker_not_passed"
            if reason is None:
                for mid, metric in body["plan"]["metrics"].items():
                    try: value = at(answer["result"], metric["pointer"])
                    except PackageError: value = None
                    values[mid] = value
                if metric_id is not None and (type(values[metric_id]) not in (int, float) or not math.isfinite(values[metric_id])):
                    reason = "ranking_metric_unavailable"
            row = {"candidate": entry["id"], "job_id": entry["job_id"], "execution_status": entry["status"],
                   "solution_status": answer.get("solution_status") if answer else None,
                   "metrics": values, "excluded_reason": reason, "error": entry.get("error")}
            rows.append(row)
            if reason is None and metric_id is not None:
                eligible.append(row)
        best = None
        if eligible:
            metric = body["plan"]["metrics"][metric_id]
            sign = 1 if metric["direction"] == "minimize" else -1
            best = min(eligible, key=lambda r: sign * r["metrics"][metric_id])["candidate"]
        return {"analysis_id": analysis_id, "status": body["status"], "rows": rows,
                "ranking_metric": metric_id, "metric_definitions": body["plan"]["metrics"], "best_candidate": best,
                "conclusion_scope": "best_completed_eligible_candidate" if best is not None else "comparison_only",
                "global_optimality_proved": False, "attempts_started": body["attempts_started"],
                "unstarted": sum(e["status"] == "not_started" for e in body["candidates"])}
