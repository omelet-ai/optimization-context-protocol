"""The PostgreSQL job store of Capability Contract v1 (psycopg 3 with a connection pool).

- Idempotency is atomic: ``INSERT ... ON CONFLICT (tenant, problem_type, idempotency_key) DO
  NOTHING``, then the existing row decides between the same job and a conflict.
- Workers take jobs with ``FOR UPDATE SKIP LOCKED``: each runnable job goes to one worker, whatever
  the number of API processes.
- A running job's lease is renewed by its worker; when it runs out (the process died) another
  worker takes the job with ``attempt`` + 1, until ``max_attempts``; then the job fails.
- A cancelled job keeps no result, whether it was queued or running.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from ..migrations import apply_migrations, kit_migrations
from .model import IdempotencyConflict, Job, JobStatus

__all__ = ["PostgresJobStore"]

_COLUMNS = (
    "id::text AS id, tenant, problem_type, idempotency_key, request_hash, caller, status, attempt, max_attempts, cancel_requested, "
    "lease_owner, lease_until, problem, result, error, metadata, created_at, updated_at, started_at, finished_at, expires_at"
)
_EXHAUSTED = {"code": "ATTEMPTS_EXHAUSTED", "message": "no worker finished the job within its attempts", "retryable": False, "issues": []}


def _job(row: dict[str, Any] | None) -> Job | None:
    if row is None:
        return None
    return Job(**{**row, "status": JobStatus(row["status"])})


class PostgresJobStore:
    def __init__(self, dsn: str, *, retention: timedelta = timedelta(days=7), max_attempts: int = 2, min_size: int = 1, max_size: int = 8, migrate: bool = True) -> None:
        self._pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size, kwargs={"autocommit": True, "row_factory": dict_row}, open=True)
        self._retention_seconds = retention.total_seconds()
        self._max_attempts = max_attempts
        if migrate:
            self.migrate()

    def close(self) -> None:
        self._pool.close()

    def migrate(self) -> list[str]:
        with self._pool.connection() as conn:
            return apply_migrations(conn, kit_migrations())

    def ping(self) -> bool:
        with self._pool.connection() as conn:
            return conn.execute("SELECT 1 AS one").fetchone() is not None

    def submit(self, *, tenant: str, problem_type: str, idempotency_key: str, request_hash: str, caller: str, problem: dict[str, Any]) -> tuple[Job, bool]:
        with self._pool.connection() as conn:
            row = conn.execute(
                f"""INSERT INTO capability_jobs (id, tenant, problem_type, idempotency_key, request_hash, caller, status, problem, max_attempts, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'queued', %s::jsonb, %s, now() + %s * interval '1 second')
                    ON CONFLICT (tenant, problem_type, idempotency_key) DO NOTHING
                    RETURNING {_COLUMNS}""",
                (str(uuid.uuid4()), tenant, problem_type, idempotency_key, request_hash, caller, Jsonb(problem), self._max_attempts, self._retention_seconds),
            ).fetchone()
            if row is not None:
                return _job(row), True  # type: ignore[return-value]
            existing = conn.execute(
                f"SELECT {_COLUMNS} FROM capability_jobs WHERE tenant = %s AND problem_type = %s AND idempotency_key = %s",
                (tenant, problem_type, idempotency_key),
            ).fetchone()
            if existing is None:  # deleted between the two statements: try once more
                return self.submit(tenant=tenant, problem_type=problem_type, idempotency_key=idempotency_key, request_hash=request_hash, caller=caller, problem=problem)
            if existing["request_hash"] != request_hash:
                raise IdempotencyConflict(existing["id"])
            return _job(existing), False  # type: ignore[return-value]

    def get(self, *, tenant: str, problem_type: str, job_id: str) -> Job | None:
        if not _is_uuid(job_id):
            return None
        with self._pool.connection() as conn:
            return _job(conn.execute(f"SELECT {_COLUMNS} FROM capability_jobs WHERE id = %s AND tenant = %s AND problem_type = %s", (job_id, tenant, problem_type)).fetchone())

    def request_cancel(self, *, tenant: str, problem_type: str, job_id: str) -> Job | None:
        if not _is_uuid(job_id):
            return None
        with self._pool.connection() as conn:
            row = conn.execute(
                f"""UPDATE capability_jobs
                    SET cancel_requested = true,
                        status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                        finished_at = CASE WHEN status = 'queued' THEN now() ELSE finished_at END,
                        updated_at = now()
                    WHERE id = %s AND tenant = %s AND problem_type = %s AND status IN ('queued', 'running')
                    RETURNING {_COLUMNS}""",
                (job_id, tenant, problem_type),
            ).fetchone()
            if row is not None:
                return _job(row)
            return self.get(tenant=tenant, problem_type=problem_type, job_id=job_id)

    def claim(self, *, problem_type: str, worker_id: str, lease_seconds: float) -> Job | None:
        with self._pool.connection() as conn:
            with conn.transaction():
                # Running jobs whose lease ran out: cancelled if asked, failed when out of attempts.
                conn.execute(
                    """UPDATE capability_jobs
                       SET status = CASE WHEN cancel_requested THEN 'cancelled' ELSE 'failed' END,
                           error = CASE WHEN cancel_requested THEN NULL ELSE %s::jsonb END,
                           result = NULL, finished_at = now(), updated_at = now(), lease_owner = NULL, lease_until = NULL
                       WHERE problem_type = %s AND status = 'running' AND lease_until < now()
                         AND (cancel_requested OR attempt >= max_attempts)""",
                    (Jsonb(_EXHAUSTED), problem_type),
                )
                row = conn.execute(
                    f"""WITH next AS (
                          SELECT id FROM capability_jobs
                          WHERE problem_type = %s AND NOT cancel_requested AND attempt < max_attempts
                            AND (status = 'queued' OR (status = 'running' AND lease_until < now()))
                          ORDER BY created_at
                          FOR UPDATE SKIP LOCKED
                          LIMIT 1
                        )
                        UPDATE capability_jobs AS jobs
                        SET status = 'running', attempt = jobs.attempt + 1, lease_owner = %s,
                            lease_until = now() + %s * interval '1 second',
                            started_at = coalesce(jobs.started_at, now()), updated_at = now()
                        FROM next WHERE jobs.id = next.id
                        RETURNING {_COLUMNS.replace('id::text AS id', 'jobs.id::text AS id')}""",
                    (problem_type, worker_id, lease_seconds),
                ).fetchone()
                return _job(row)

    def heartbeat(self, *, job_id: str, worker_id: str, lease_seconds: float) -> bool | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                """UPDATE capability_jobs SET lease_until = now() + %s * interval '1 second', updated_at = now()
                   WHERE id = %s AND lease_owner = %s AND status = 'running' RETURNING cancel_requested""",
                (lease_seconds, job_id, worker_id),
            ).fetchone()
            return None if row is None else bool(row["cancel_requested"])

    def finish(self, *, job_id: str, worker_id: str, status: JobStatus, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> Job | None:
        keep_result = status in (JobStatus.SUCCEEDED, JobStatus.INFEASIBLE)
        with self._pool.connection() as conn:
            return _job(
                conn.execute(
                    f"""UPDATE capability_jobs
                        SET status = CASE WHEN cancel_requested THEN 'cancelled' ELSE %s::text END,
                            result = CASE WHEN cancel_requested THEN NULL ELSE %s::jsonb END,
                            error = CASE WHEN cancel_requested THEN NULL ELSE %s::jsonb END,
                            finished_at = now(), updated_at = now(), lease_owner = NULL, lease_until = NULL
                        WHERE id = %s AND lease_owner = %s AND status = 'running'
                        RETURNING {_COLUMNS}""",
                    (status.value, Jsonb(result) if keep_result and result is not None else None, Jsonb(error) if error is not None else None, job_id, worker_id),
                ).fetchone()
            )

    def purge_expired(self) -> int:
        with self._pool.connection() as conn:
            cursor = conn.execute("DELETE FROM capability_jobs WHERE expires_at < now() AND status IN ('succeeded', 'infeasible', 'failed', 'cancelled')")
            return cursor.rowcount


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
