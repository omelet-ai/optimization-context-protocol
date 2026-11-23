"""Durable, single-host JobStore implementing the pinned native contract port.

Each operation is one SQLite transaction. A lease fences late worker writes.
No automatic retry after a lost worker: its external side effect is uncertain.
Use a network database implementation for multi-host deployments.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
import uuid

from ocp_runtime._worker_contract.jobs.model import Job, JobStatus, TERMINAL, IdempotencyConflict

_DATES = {"created_at", "updated_at", "started_at", "finished_at", "expires_at", "lease_until"}


def _encode(job):
    body = asdict(job)
    for key in _DATES:
        body[key] = body[key].isoformat() if body[key] else None
    return json.dumps(body, allow_nan=False, separators=(",", ":"))


def _decode(raw):
    body = json.loads(raw)
    for key in _DATES:
        body[key] = datetime.fromisoformat(body[key]) if body[key] else None
    body["status"] = JobStatus(body["status"])
    return Job(**body)


class SQLiteJobStore:
    durability = "sqlite_single_host"

    def __init__(self, path, *, retention=timedelta(days=7), clock=None):
        self.path = str(Path(path).resolve())
        self.retention, self.now = retention, clock or (lambda: datetime.now(UTC))
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, problem_type TEXT NOT NULL, idem TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(tenant,problem_type,idem))")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _save(db, job):
        db.execute("UPDATE jobs SET body=? WHERE id=?", (_encode(job), job.id))

    @staticmethod
    def _find(db, job_id):
        row = db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _decode(row[0]) if row else None

    def submit(self, *, tenant, problem_type, idempotency_key, request_hash, caller, problem):
        with self._transaction() as db:
            row = db.execute("SELECT body FROM jobs WHERE tenant=? AND problem_type=? AND idem=?", (tenant, problem_type, idempotency_key)).fetchone()
            if row:
                job = _decode(row[0])
                if job.request_hash != request_hash:
                    raise IdempotencyConflict(job.id)
                return job, False
            now = self.now()
            job = Job(str(uuid.uuid4()), tenant, problem_type, idempotency_key, request_hash, caller,
                      JobStatus.QUEUED, problem, max_attempts=1, created_at=now, updated_at=now, expires_at=now + self.retention)
            raw = _encode(job)
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (job.id, tenant, problem_type, idempotency_key, raw))
            return _decode(raw), True

    def get(self, *, tenant, problem_type, job_id):
        with self._transaction() as db:
            job = self._find(db, job_id)
            return job if job and (job.tenant, job.problem_type) == (tenant, problem_type) else None

    def request_cancel(self, *, tenant, problem_type, job_id):
        with self._transaction() as db:
            job = self._find(db, job_id)
            if not job or (job.tenant, job.problem_type) != (tenant, problem_type):
                return None
            if job.status not in TERMINAL:
                job.cancel_requested, job.updated_at = True, self.now()
                if job.status == JobStatus.QUEUED:
                    job.status, job.finished_at = JobStatus.CANCELLED, job.updated_at
                self._save(db, job)
            return job

    def claim(self, *, problem_type, worker_id, lease_seconds):
        if lease_seconds <= 0:
            raise ValueError("INVALID_LEASE")
        with self._transaction() as db:
            now = self.now()
            jobs = [_decode(row[0]) for row in db.execute("SELECT body FROM jobs WHERE problem_type=?", (problem_type,))]
            for job in jobs:
                if job.status == JobStatus.RUNNING and job.lease_until and job.lease_until <= now:
                    # A lease timeout cannot prove a remote solve stopped. Retain
                    # uncertainty even when cancellation had been requested.
                    job.status, job.finished_at, job.updated_at = JobStatus.FAILED, now, now
                    job.error = {"code": "EXECUTION_UNCERTAIN", "message": "Worker lease expired; execution must be reconciled before a new attempt.", "retryable": False, "issues": []}
                    job.result, job.lease_owner, job.lease_until = None, None, None
                    self._save(db, job)
            queued = [j for j in jobs if j.status == JobStatus.QUEUED and not j.cancel_requested and j.expires_at > now]
            if not queued:
                return None
            job = min(queued, key=lambda j: (j.created_at, j.id))
            job.status, job.attempt, job.lease_owner = JobStatus.RUNNING, 1, worker_id
            job.lease_until = now + timedelta(seconds=lease_seconds)
            job.started_at, job.updated_at = now, now
            self._save(db, job)
            return job

    def _owned(self, job, worker_id):
        return bool(job and job.status == JobStatus.RUNNING and job.lease_owner == worker_id and job.lease_until > self.now())

    def heartbeat(self, *, job_id, worker_id, lease_seconds):
        if lease_seconds <= 0:
            raise ValueError("INVALID_LEASE")
        with self._transaction() as db:
            job = self._find(db, job_id)
            if not self._owned(job, worker_id):
                return None
            job.updated_at = self.now()
            job.lease_until = job.updated_at + timedelta(seconds=lease_seconds)
            self._save(db, job)
            return job.cancel_requested

    def finish(self, *, job_id, worker_id, status, result=None, error=None):
        if status not in TERMINAL:
            raise ValueError("TERMINAL_STATUS_REQUIRED")
        with self._transaction() as db:
            job = self._find(db, job_id)
            if not self._owned(job, worker_id):
                return None
            if job.cancel_requested:
                status, result, error = JobStatus.CANCELLED, None, None
            job.status, job.error = status, error
            job.result = result if status in {JobStatus.SUCCEEDED, JobStatus.INFEASIBLE} else None
            job.finished_at = job.updated_at = self.now()
            job.lease_owner = job.lease_until = None
            self._save(db, job)
            return job

    def purge_expired(self):
        with self._transaction() as db:
            ids = [job.id for (raw,) in db.execute("SELECT body FROM jobs")
                   if (job := _decode(raw)).expires_at <= self.now() and job.status != JobStatus.RUNNING]
            db.executemany("DELETE FROM jobs WHERE id=?", ((i,) for i in ids))
            return len(ids)
