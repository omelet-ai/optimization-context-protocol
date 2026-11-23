"""The worker that runs an API's jobs (Capability Contract v1).

A worker takes the oldest runnable job of its problem type, runs the API's solve through a runner,
renews its lease while the solve runs (and learns of cancellations there), and ends the job:

- ``{"status": "succeeded" | "infeasible", "result": {...}}`` from the solve: that status and result;
- SolveCancelled: cancelled, no result;
- SolveFailed or any other error: failed, with an error envelope (code, message, retryable false).

Workers run as threads in the API process (``WorkerPool``) or in a process of their own; several
workers on one database share the work, and a job whose worker died is taken again when its lease
runs out (attempt + 1).

With ``solve_with_job_id`` the solve also gets ``job_id=<the job's id>`` (a keyword argument), for an
API whose result names its job; a ProcessSolveRunner solve stays a module-level function.
"""

from __future__ import annotations

import functools
import logging
import os
import socket
import threading
import uuid
from collections.abc import Callable
from typing import Any

from ..runners import SolveCancelled, SolveFailed, SolveRunner
from .model import JobStatus, JobStore

__all__ = ["Worker", "WorkerPool"]

log = logging.getLogger("foundry_capability_contract.worker")


class Worker:
    def __init__(
        self,
        store: JobStore,
        *,
        problem_type: str,
        solve: Callable[..., dict[str, Any]],
        runner: SolveRunner,
        lease_seconds: float = 30.0,
        heartbeat_seconds: float = 5.0,
        worker_id: str | None = None,
        solve_with_job_id: bool = False,
    ) -> None:
        self.store = store
        self.problem_type = problem_type
        self.solve = solve
        self.solve_with_job_id = solve_with_job_id
        self.runner = runner
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    def run_once(self) -> bool:
        """Take and run one job; False when none was runnable."""
        job = self.store.claim(problem_type=self.problem_type, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
        if job is None:
            return False
        lost = threading.Event()

        def should_cancel() -> bool:
            answer = self.store.heartbeat(job_id=job.id, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
            if answer is None:  # another worker holds the job now
                lost.set()
                return True
            return answer

        log.info("job %s attempt %s started", job.id, job.attempt)
        try:
            solve = functools.partial(self.solve, job_id=job.id) if self.solve_with_job_id else self.solve
            outcome = self.runner.run(solve, job.problem, should_cancel, poll_seconds=self.heartbeat_seconds)
            status = JobStatus(outcome.get("status", "succeeded"))
            if status not in (JobStatus.SUCCEEDED, JobStatus.INFEASIBLE):
                raise SolveFailed("BAD_OUTCOME", f"a solve answers succeeded or infeasible, not {status.value}")
            finished = self.store.finish(job_id=job.id, worker_id=self.worker_id, status=status, result=outcome.get("result") or {})
        except SolveCancelled:
            finished = None if lost.is_set() else self.store.finish(job_id=job.id, worker_id=self.worker_id, status=JobStatus.CANCELLED)
        except SolveFailed as error:
            finished = self.store.finish(job_id=job.id, worker_id=self.worker_id, status=JobStatus.FAILED, error=_error(error.code, str(error), retryable=error.retryable, issues=error.issues))
        except Exception as error:  # noqa: BLE001 - the job fails, the worker goes on
            log.exception("job %s failed", job.id)
            finished = self.store.finish(job_id=job.id, worker_id=self.worker_id, status=JobStatus.FAILED, error=_error("SOLVE_FAILED", type(error).__name__))
        log.info("job %s ended %s", job.id, finished.status.value if finished else "elsewhere (lease lost)")
        return True


def _error(code: str, message: str, *, retryable: bool = False, issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "retryable": retryable, "issues": issues or []}


class WorkerPool:
    """``count`` workers as daemon threads, polling every ``idle_seconds`` when there is no job, and
    (with ``purge_store``) a housekeeper deleting expired job records every ``purge_seconds``."""

    def __init__(
        self,
        make_worker: Callable[[int], Worker],
        *,
        count: int = 1,
        idle_seconds: float = 0.5,
        purge_store: JobStore | None = None,
        purge_seconds: float = 600.0,
    ) -> None:
        self._make_worker = make_worker
        self._count = count
        self._idle = idle_seconds
        self._purge_store = purge_store
        self._purge_seconds = purge_seconds
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for index in range(self._count):
            worker = self._make_worker(index)
            thread = threading.Thread(target=self._loop, args=(worker,), name=f"capability-worker-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)
        if self._purge_store is not None:
            thread = threading.Thread(target=self._housekeep, args=(self._purge_store,), name="capability-housekeeper", daemon=True)
            thread.start()
            self._threads.append(thread)

    def _housekeep(self, store: JobStore) -> None:
        while not self._stop.wait(self._purge_seconds):
            try:
                purged = store.purge_expired()
                if purged:
                    log.info("purged %s expired job records", purged)
            except Exception:  # noqa: BLE001 - try again next round
                log.exception("purging expired job records failed")

    def _loop(self, worker: Worker) -> None:
        while not self._stop.is_set():
            try:
                if not worker.run_once():
                    self._stop.wait(self._idle)
            except Exception:  # noqa: BLE001 - a store hiccup must not end the worker
                log.exception("worker %s: taking a job failed", worker.worker_id)
                self._stop.wait(self._idle * 4)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout)
