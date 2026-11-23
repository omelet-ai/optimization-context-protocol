"""Running one solve so that a cancellation stops it (Capability Contract v1).

- ThreadSolveRunner: for solvers that stop when asked (CP-SAT ``stop_search``). The solve runs in a
  thread with a ``threading.Event`` it watches.
- ProcessSolveRunner: for solvers that cannot be interrupted (ALNS, PyVRP, scipy). The solve runs in
  a spawned process; cancelling terminates it. The solve function must be importable by name.

Both call ``should_cancel()`` every ``poll_seconds`` while the solve runs (the worker renews its
lease there) and raise SolveCancelled when it answers True.

A solve that fails on purpose raises ``SolveFailed(code, message)``: the code and message go to the
job's error, which the caller sees. Any other exception is a fault: the job's error names only the
exception type, and the traceback goes to the log.
"""

from __future__ import annotations

import logging
import multiprocessing
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any

__all__ = ["ProcessSolveRunner", "SolveCancelled", "SolveFailed", "SolveRunner", "ThreadSolveRunner"]

log = logging.getLogger("foundry_capability_contract.runners")

SolveFn = Callable[..., dict[str, Any]]


class SolveCancelled(Exception):
    """The solve stopped because its job was cancelled."""


class SolveFailed(Exception):
    """The solve failed; ``code``, the message, ``retryable`` and ``issues`` go to the job's error."""

    def __init__(self, code: str, message: str, *, retryable: bool = False, issues: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.issues = issues or []


class SolveRunner:
    def run(self, solve: SolveFn, problem: dict[str, Any], should_cancel: Callable[[], bool], *, poll_seconds: float = 1.0) -> dict[str, Any]:
        raise NotImplementedError


class ThreadSolveRunner(SolveRunner):
    """``solve(problem, cancel_event) -> outcome`` in a thread; cancellation sets the event.

    A solve that has not returned ``stop_grace_seconds`` after the event was set is abandoned (its
    daemon thread runs on) so that the worker can take the next job.
    """

    def __init__(self, *, stop_grace_seconds: float = 30.0) -> None:
        self._grace = stop_grace_seconds

    def run(self, solve: SolveFn, problem: dict[str, Any], should_cancel: Callable[[], bool], *, poll_seconds: float = 1.0) -> dict[str, Any]:
        cancel = threading.Event()
        box: dict[str, Any] = {}

        def target() -> None:
            try:
                box["outcome"] = solve(problem, cancel)
            except BaseException as error:  # noqa: BLE001 - reported below
                box["error"] = error

        thread = threading.Thread(target=target, name="capability-solve", daemon=True)
        thread.start()
        cancelled_at: float | None = None
        while thread.is_alive():
            thread.join(poll_seconds)
            if not thread.is_alive():
                break
            if cancelled_at is None and should_cancel():
                cancel.set()
                cancelled_at = time.monotonic()
            elif cancelled_at is not None and time.monotonic() - cancelled_at > self._grace:
                log.error("the solve did not stop %.0f s after its job was cancelled; abandoning its thread", self._grace)
                break
        if cancel.is_set():
            raise SolveCancelled()
        if "error" in box:
            error = box["error"]
            if isinstance(error, (SolveFailed, SolveCancelled)):
                raise error
            log.error("the solve failed", exc_info=error)
            raise SolveFailed("SOLVE_FAILED", type(error).__name__) from error
        return box["outcome"]


def _process_target(solve: SolveFn, problem: dict[str, Any], connection: Any) -> None:
    try:
        connection.send(("ok", solve(problem)))
    except SolveFailed as error:
        connection.send(("error", error.code, str(error), None, error.retryable, error.issues))
    except BaseException as error:  # noqa: BLE001 - sent to the parent, which logs it
        connection.send(("error", "SOLVE_FAILED", type(error).__name__, traceback.format_exc(limit=8), False, []))
    finally:
        connection.close()


class ProcessSolveRunner(SolveRunner):
    """``solve(problem) -> outcome`` in a spawned process; cancellation terminates it."""

    def __init__(self, *, start_method: str = "spawn", kill_after_seconds: float = 5.0) -> None:
        self._context = multiprocessing.get_context(start_method)
        self._kill_after = kill_after_seconds

    def run(self, solve: SolveFn, problem: dict[str, Any], should_cancel: Callable[[], bool], *, poll_seconds: float = 1.0) -> dict[str, Any]:
        receiver, sender = self._context.Pipe(duplex=False)
        process = self._context.Process(target=_process_target, args=(solve, problem, sender), name="capability-solve", daemon=True)
        process.start()
        sender.close()
        try:
            while True:
                if receiver.poll(poll_seconds):
                    try:
                        message = receiver.recv()
                    except EOFError:
                        process.join(self._kill_after)
                        raise SolveFailed("SOLVER_CRASHED", f"the solver process exited with {process.exitcode} before answering") from None
                    process.join(self._kill_after)
                    if message[0] == "ok":
                        return message[1]
                    if message[3]:
                        log.error("the solve failed in its process:\n%s", message[3])
                    raise SolveFailed(message[1], message[2], retryable=message[4], issues=message[5])
                if not process.is_alive():
                    raise SolveFailed("SOLVER_CRASHED", f"the solver process exited with {process.exitcode} before answering")
                if should_cancel():
                    raise SolveCancelled()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(self._kill_after)
                if process.is_alive():
                    process.kill()
                    process.join()
            receiver.close()
