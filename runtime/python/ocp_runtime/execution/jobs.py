"""Optional job binding built on the public pinned native worker and runner."""
from copy import deepcopy
from dataclasses import dataclass
import math
import time

from ocp_runtime._worker_contract.jobs.memory import MemoryJobStore
from ocp_runtime._worker_contract.jobs.worker import Worker
from ocp_runtime._worker_contract.runners import ProcessSolveRunner, SolveCancelled, SolveFailed
from .service import ExecutionError
from ocp_candidate.fingerprint import fingerprint


@dataclass(frozen=True)
class Principal:
    """Supplied by a trusted binding, never copied from the request body."""
    tenant: str
    caller: str
    scopes: frozenset = frozenset({"read", "execute", "cancel"})


class BudgetRunner:
    def __init__(self, service, budget_seconds):
        self.service, self.budget = service, budget_seconds
        self.runner = ProcessSolveRunner(kill_after_seconds=1)

    def run(self, solve, problem, should_cancel, *, poll_seconds=0.05):
        started, expired = time.monotonic(), False

        def stop():
            nonlocal expired
            if should_cancel():
                return True
            expired = time.monotonic() - started >= self.budget
            return expired
        try:
            return self.runner.run(solve, problem, stop, poll_seconds=poll_seconds)
        except SolveCancelled:
            if not expired:
                raise
            if getattr(self.service.connector, "isolation", None) != "local_process":
                raise SolveFailed("EXECUTION_UNCERTAIN", "Deadline expired; reconcile the remote execution before retrying") from None
            # Local process termination is guaranteed by ProcessSolveRunner.
            # External connectors require their own cancellation/reconciliation
            # protocol; no HTTP operation is assumed cancelled here.
            return {"status": "succeeded", "result": self.service.unknown(problem)}


@dataclass
class SolveTask:
    # Do not pickle the job store, connections, locks or authenticated principal
    # into the solver process. Only installed service code and request data.
    service: object

    def __call__(self, problem):
        if problem["contract"] != self.service.contract_fingerprint:
            raise SolveFailed("CONTRACT_DRIFT", "Contract changed before execution")
        try:
            result = self.service.execute(deepcopy(problem["input"]), deepcopy(problem["configuration"]))
        except ExecutionError as error:
            raise SolveFailed(error.code, error.code, retryable=False, issues=error.issues) from None
        return {"status": "infeasible" if result["solution_status"] == "infeasible" else "succeeded", "result": result}


class JobService:
    def __init__(self, service, *, store=None, budget_seconds=30):
        if not isinstance(budget_seconds, (int, float)) or isinstance(budget_seconds, bool) or not math.isfinite(budget_seconds) or budget_seconds <= 0:
            raise ValueError("INVALID_TIME_BUDGET")
        self.service, self.store = service, store if store is not None else MemoryJobStore(max_attempts=1)
        self.problem_type = service.descriptor["id"] + "@" + service.descriptor["version"]
        self.budget = budget_seconds
        self.durability = getattr(self.store, "durability", "process_memory_no_restart")

    @staticmethod
    def _authorize(principal, scope):
        if not isinstance(principal, Principal) or not principal.tenant or not principal.caller:
            raise ExecutionError("AUTHENTICATION_REQUIRED")
        if scope not in principal.scopes:
            raise ExecutionError("SCOPE_REQUIRED")

    def submit(self, principal, input_value, configuration, *, idempotency_key):
        self._authorize(principal, "execute")
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
            raise ExecutionError("IDEMPOTENCY_KEY_REQUIRED")
        request = self.service.request(input_value, configuration)
        return self.store.submit(tenant=principal.tenant, caller=principal.caller, problem_type=self.problem_type,
                                 idempotency_key=idempotency_key, request_hash=fingerprint(request)["sha256"], problem=request)

    def get(self, principal, job_id):
        self._authorize(principal, "read")
        return self.store.get(tenant=principal.tenant, problem_type=self.problem_type, job_id=job_id)

    def cancel(self, principal, job_id):
        self._authorize(principal, "cancel")
        if getattr(self.service.connector, "isolation", None) != "local_process":
            raise ExecutionError("REMOTE_CANCELLATION_UNSUPPORTED")
        return self.store.request_cancel(tenant=principal.tenant, problem_type=self.problem_type, job_id=job_id)

    def worker(self, *, worker_id=None):
        return Worker(self.store, problem_type=self.problem_type, solve=SolveTask(self.service),
                      runner=BudgetRunner(self.service, self.budget), worker_id=worker_id,
                      lease_seconds=max(5, self.budget + 2), heartbeat_seconds=0.05)
