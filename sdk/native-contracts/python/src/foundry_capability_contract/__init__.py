"""foundry-capability-contract: Capability Contract v1 for OI Foundry Optimization APIs.

An Optimization API (one per problem type) builds its FastAPI app from this kit:

    settings = Settings.from_env()          # class Settings(ApiSettings): env_prefix = "NURSE_API"
    store, trust = settings.job_store(), settings.trust
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(ops_router(service="nurse-scheduling-optimization-api", versions=..., checks=[...]))
    app.include_router(capability_router(adapter, store, trust, base_path="/v2"))
    WorkerPool(lambda i: Worker(store, problem_type=..., solve=..., runner=ThreadSolveRunner())).start()

The contract itself (endpoints, states, errors, digests) is in ``shared/ocp-contracts/capability-contract/README.md``.
"""

from .canonical import canonical_digest, canonical_json, capability_digest, js_number
from .errors import CapabilityError, error_body, install_error_handlers, request_id_of
from .jobs.memory import MemoryJobStore
from .jobs.model import TERMINAL, IdempotencyConflict, Job, JobStatus, JobStore
from .jobs.worker import Worker, WorkerPool
from .ops import ReadinessCheck, ops_router
from .router import CONTRACT_VERSION, CapabilityAdapter, capability_document, capability_router
from .runners import ProcessSolveRunner, SolveCancelled, SolveFailed, SolveRunner, ThreadSolveRunner
from .settings import ApiSettings
from .trust import TENANT_HEADER, ServiceTrust, parse_service_tokens, require_tenant

__all__ = [
    "CONTRACT_VERSION",
    "TENANT_HEADER",
    "TERMINAL",
    "ApiSettings",
    "CapabilityAdapter",
    "CapabilityError",
    "IdempotencyConflict",
    "Job",
    "JobStatus",
    "JobStore",
    "MemoryJobStore",
    "ProcessSolveRunner",
    "ReadinessCheck",
    "ServiceTrust",
    "SolveCancelled",
    "SolveFailed",
    "SolveRunner",
    "ThreadSolveRunner",
    "Worker",
    "WorkerPool",
    "canonical_digest",
    "canonical_json",
    "capability_digest",
    "capability_document",
    "capability_router",
    "error_body",
    "install_error_handlers",
    "js_number",
    "ops_router",
    "parse_service_tokens",
    "request_id_of",
    "require_tenant",
]
