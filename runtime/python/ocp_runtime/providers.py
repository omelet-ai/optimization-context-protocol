"""Explicit reference-provider selection; no guessed engine or profile fallback."""
from ocp_candidate.contract import OCPError

def routing():
    from ocp_routing import RoutingAdapter, ORToolsBackend
    return RoutingAdapter(ORToolsBackend())

def worker():
    from ocp_planning import worker_adapter
    return worker_adapter()

def inventory():
    from ocp_planning import inventory_adapter
    return inventory_adapter()

PROVIDERS={'routing.basic':routing,'worker.scheduling':worker,'inventory.replenishment':inventory}

def coordinates():
    from ocp_routing import ORToolsBackend
    from ocp_routing.coordinates import CoordinatesAdapter, CoordinateLibraryBackend
    return CoordinatesAdapter(CoordinateLibraryBackend(ORToolsBackend()))

# Preserve the legacy default catalog; opt in with --domain routing-coordinates.
OPTIONAL_PROVIDERS = {'routing.coordinates': coordinates}

def make_provider(profile='routing.basic'):
    providers = {**PROVIDERS, **OPTIONAL_PROVIDERS}
    if profile not in providers:raise OCPError('UNSUPPORTED_PROFILE')
    return providers[profile]()
