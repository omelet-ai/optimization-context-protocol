"""Bind the local cutting algorithm and its independent checker to OCP."""
import json
from pathlib import Path

from .algorithm import pack
from .checker import Checker


class Connector:
    isolation = "local_process"

    def describe(self):
        doc = json.loads(Path(__file__).with_name("manifest.json").read_text())
        return {key: doc[key] for key in ("api", "schemas", "capabilities")}

    def execute(self, data, config):
        stock = data["stock_length_cm"]
        pieces = data["pieces_cm"]
        layout = pack(stock, pieces)
        if layout is None:
            return {"solution_status": "infeasible", "termination_reason": "completed", "result": None,
                    "effective_configuration": config, "proof": {"method": "oversize indivisible piece",
                    "largest_cm": max(pieces), "stock_length_cm": stock}}
        return {"solution_status": "optimal", "termination_reason": "completed",
                "result": {"stock_count": len(layout), "cuts_cm": layout}, "effective_configuration": config,
                "proof": {"method": "dynamic programming over all subsets and last pieces",
                          "subsets_considered": 1 << len(pieces)}}


def create_bundle(settings):
    return {"connector": Connector(), "checker": Checker()}
