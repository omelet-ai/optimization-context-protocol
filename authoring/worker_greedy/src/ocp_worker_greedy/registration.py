"""Only the generic native server and SDK are shared with other providers."""
from ocp_runtime.native_domain import ReferenceDomain, run_provider
from ocp_runtime.native_server import Registration
from .provider import WorkerProvider


def solve(problem):
    # Importable by the native process worker; no reference factory involved.
    return run_provider(WorkerProvider(), problem)


def registration():
    return Registration(ReferenceDomain(WorkerProvider(), problem_type='worker-scheduling'), solve)
