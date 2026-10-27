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

def make_provider(profile='routing.basic'):
    if profile not in PROVIDERS:raise OCPError('UNSUPPORTED_PROFILE')
    return PROVIDERS[profile]()
