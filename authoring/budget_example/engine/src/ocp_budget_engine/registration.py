from ocp_candidate.profiles import ProfileRegistry
from ocp_budget_profile import REFERENCE, SEMANTICS, schema
from ocp_runtime.native_domain import ReferenceDomain, run_provider
from ocp_runtime.native_server import Registration
from ocp_runtime.native_extension import Extension, EXTENSION_API
from . import Provider


def profiles():
    registry = ProfileRegistry()
    registry.register(REFERENCE, schema('input'), schema('solution'), SEMANTICS)
    return registry


def solve(problem):
    return run_provider(Provider(), problem, registry=profiles())


def extension():
    return Extension(EXTENSION_API, (Registration(ReferenceDomain(Provider(), problem_type='budget-selection', registry=profiles()), solve),))
