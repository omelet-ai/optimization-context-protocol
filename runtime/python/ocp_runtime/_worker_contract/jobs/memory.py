"""An in-process job store with PostgresJobStore's semantics, for tests and local runs."""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .model import TERMINAL, IdempotencyConflict, Job, JobStatus

__all__ = ["MemoryJobStore"]


class MemoryJobStore:
    def __init__(self, *, retention: timedelta = timedelta(days=7), max_attempts: int = 2, clock=None) -> None:  # type: ignore[no-untyped-def]
        self._jobs: dict[str, Job] = {}
        self._keys: dict[tuple[str, str, str], str] = {}
        self._lock = threading.Lock()
        self._retention = retention
        self._max_attempts = max_attempts
        self._now = clock or (lambda: datetime.now(UTC))

    def submit(self, *, tenant: str, problem_type: str, idempotency_key: str, request_hash: str, caller: str, problem: dict[str, Any]) -> tuple[Job, bool]:
        with self._lock:
            key = (tenant, problem_type, idempotency_key)
            existing_id = self._keys.get(key)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(existing.id)
                return copy.deepcopy(existing), False
            now = self._now()
            job = Job(
                id=str(uuid.uuid4()),
                tenant=tenant,
                problem_type=problem_type,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                caller=caller,
                status=JobStatus.QUEUED,
                problem=problem,
                max_attempts=self._max_attempts,
                created_at=now,
                updated_at=now,
                expires_at=now + self._retention,
            )
            self._jobs[job.id] = job
            self._keys[key] = job.id
            return copy.deepcopy(job), True

    def get(self, *, tenant: str, problem_type: str, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job is not None and job.tenant == tenant and job.problem_type == problem_type else None

    def request_cancel(self, *, tenant: str, problem_type: str, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.tenant != tenant or job.problem_type != problem_type:
                return None
            if job.status in TERMINAL:
                return copy.deepcopy(job)
            now = self._now()
            job.cancel_requested = True
            job.updated_at = now
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                job.finished_at = now
            return copy.deepcopy(job)

    def claim(self, *, problem_type: str, worker_id: str, lease_seconds: float) -> Job | None:
        with self._lock:
            now = self._now()
            self._expire_leases(now)
            runnable = sorted(
                (
                    job
                    for job in self._jobs.values()
                    if job.problem_type == problem_type
                    and not job.cancel_requested
                    and job.attempt < job.max_attempts
                    and (job.status == JobStatus.QUEUED or (job.status == JobStatus.RUNNING and job.lease_until is not None and job.lease_until < now))
                ),
                key=lambda job: job.created_at or now,
            )
            if not runnable:
                return None
            job = runnable[0]
            job.status = JobStatus.RUNNING
            job.attempt += 1
            job.lease_owner = worker_id
            job.lease_until = now + timedelta(seconds=lease_seconds)
            job.started_at = job.started_at or now
            job.updated_at = now
            return copy.deepcopy(job)

    def _expire_leases(self, now: datetime) -> None:
        # A running job whose lease ran out: cancelled if that was asked for, failed when out of attempts.
        for job in self._jobs.values():
            if job.status != JobStatus.RUNNING or job.lease_until is None or job.lease_until >= now:
                continue
            if job.cancel_requested:
                job.status, job.result, job.finished_at = JobStatus.CANCELLED, None, now
            elif job.attempt >= job.max_attempts:
                job.status, job.finished_at = JobStatus.FAILED, now
                job.error = {"code": "ATTEMPTS_EXHAUSTED", "message": f"no worker finished the job in {job.attempt} attempts", "retryable": False, "issues": []}
            else:
                continue
            job.lease_owner = job.lease_until = None
            job.updated_at = now

    def heartbeat(self, *, job_id: str, worker_id: str, lease_seconds: float) -> bool | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
                return None
            now = self._now()
            job.lease_until = now + timedelta(seconds=lease_seconds)
            job.updated_at = now
            return job.cancel_requested

    def finish(self, *, job_id: str, worker_id: str, status: JobStatus, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
                return None
            now = self._now()
            if job.cancel_requested:
                status, result, error = JobStatus.CANCELLED, None, None
            job.status = status
            job.result = result if status in (JobStatus.SUCCEEDED, JobStatus.INFEASIBLE) else None
            job.error = error
            job.finished_at = now
            job.updated_at = now
            job.lease_owner = job.lease_until = None
            return copy.deepcopy(job)

    def purge_expired(self) -> int:
        with self._lock:
            now = self._now()
            expired = [job for job in self._jobs.values() if job.expires_at is not None and job.expires_at < now and job.status in TERMINAL]
            for job in expired:
                del self._jobs[job.id]
                self._keys.pop((job.tenant, job.problem_type, job.idempotency_key), None)
            return len(expired)
