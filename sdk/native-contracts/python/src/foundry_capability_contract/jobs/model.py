"""Jobs of Capability Contract v1: states, the record, and the store every API uses.

A job moves ``queued -> running -> succeeded | infeasible | failed | cancelled`` (the HTTP answer
to the submission is ``202 accepted``). It belongs to one tenant and one problem type; its
idempotency key is unique within ``(tenant, problem type)``. A worker holds a running job under a
lease it renews; a job whose lease runs out is taken again (``attempt`` + 1) until ``max_attempts``.
A cancelled job keeps no result. Records expire (``expires_at``): the API keeps computation
records, never business state (P5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

__all__ = ["Job", "JobStatus", "JobStore", "IdempotencyConflict", "TERMINAL"]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INFEASIBLE = "infeasible"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = frozenset({JobStatus.SUCCEEDED, JobStatus.INFEASIBLE, JobStatus.FAILED, JobStatus.CANCELLED})


class IdempotencyConflict(Exception):
    """The tenant's idempotency key already names a job for a different request."""

    def __init__(self, job_id: str) -> None:
        super().__init__(job_id)
        self.job_id = job_id


@dataclass
class Job:
    id: str
    tenant: str
    problem_type: str
    idempotency_key: str
    request_hash: str
    caller: str
    status: JobStatus
    problem: dict[str, Any]
    attempt: int = 0
    max_attempts: int = 2
    cancel_requested: bool = False
    lease_owner: str | None = None
    lease_until: datetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        """What GET /jobs/{id} answers: the state, never the problem or the result."""
        stamp = lambda value: value.isoformat() if value else None  # noqa: E731
        body: dict[str, Any] = {
            "jobId": self.id,
            "problemType": self.problem_type,
            "status": self.status.value,
            "attempt": self.attempt,
            "cancelRequested": self.cancel_requested,
            "createdAt": stamp(self.created_at),
            "updatedAt": stamp(self.updated_at),
            "startedAt": stamp(self.started_at),
            "finishedAt": stamp(self.finished_at),
            "expiresAt": stamp(self.expires_at),
        }
        if self.error is not None:
            body["error"] = self.error
        return body


class JobStore(Protocol):
    """Where an API keeps its jobs (MemoryJobStore for tests, PostgresJobStore otherwise)."""

    def submit(
        self, *, tenant: str, problem_type: str, idempotency_key: str, request_hash: str, caller: str, problem: dict[str, Any]
    ) -> tuple[Job, bool]:
        """The job for this key: a new queued one (True) or the existing one for the same request
        (False). Another request under the key raises IdempotencyConflict."""
        ...

    def get(self, *, tenant: str, problem_type: str, job_id: str) -> Job | None:
        """The tenant's job, or None (another tenant's job is not found)."""
        ...

    def request_cancel(self, *, tenant: str, problem_type: str, job_id: str) -> Job | None:
        """Cancel the tenant's job: a queued one at once, a running one when its worker sees it."""
        ...

    def claim(self, *, problem_type: str, worker_id: str, lease_seconds: float) -> Job | None:
        """The oldest runnable job (queued, or running with its lease run out), now running under
        this worker's lease with attempt + 1; jobs out of attempts are failed."""
        ...

    def heartbeat(self, *, job_id: str, worker_id: str, lease_seconds: float) -> bool | None:
        """Renew the lease: None when the worker no longer holds the job, else cancel_requested."""
        ...

    def finish(
        self, *, job_id: str, worker_id: str, status: JobStatus, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None
    ) -> Job | None:
        """End the worker's job (cancelled, without a result, if cancellation was requested)."""
        ...

    def purge_expired(self) -> int:
        """Delete expired records; answers how many."""
        ...
