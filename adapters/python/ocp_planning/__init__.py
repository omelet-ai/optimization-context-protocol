"""Bounded no-key planning reference adapters; independent of Foundry."""
from .adapter import PlanningAdapter
from . import worker

def worker_adapter():
    return PlanningAdapter(worker)

def inventory_adapter():
    from . import inventory
    return PlanningAdapter(inventory)
