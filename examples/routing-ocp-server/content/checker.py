"""Independent route verification. Does not import the solver implementation."""
from collections import Counter
from ocp_candidate.fingerprint import fingerprint


class RoutingChecker:
    identity = {"id": "routing.matrix.independent-checker", "version": "1.0.0"}

    def evaluate(self, data, config, result):
        checks = []
        def check(cid, okay): checks.append({"id": cid, "status": "pass" if okay else "fail"})
        visits = {v["id"]: v["demand_kg"] for v in data["visits"]}
        vehicles = {v["id"]: v["capacity_kg"] for v in data["vehicles"]}
        nodes = {name: i for i, name in enumerate(data["distance_matrix"]["node_ids"])}
        matrix = data["distance_matrix"]["distances_m"]
        routes = result.get("routes")
        check("request_identity", result.get("input_fingerprint") == fingerprint(data))
        if not isinstance(routes, list):
            check("route_shape", False)
        else:
            used, served, recomputed_distance, structure = [], [], 0, True
            for index, route in enumerate(routes):
                if not isinstance(route, dict) or not isinstance(route.get("visits"), list) or not route["visits"] or route.get("vehicle_id") not in vehicles or any(type(v) is not str or v not in visits for v in route["visits"]):
                    check(f"route_{index}_shape", False); structure = False; continue
                used.append(route["vehicle_id"]); served.extend(route["visits"])
                load = sum(visits[v] for v in route["visits"])
                sequence = [data["depot_id"], *route["visits"], data["depot_id"]]
                distance = sum(matrix[nodes[a]][nodes[b]] for a, b in zip(sequence, sequence[1:]))
                recomputed_distance += distance
                check(f"route_{index}_capacity", load <= vehicles[route["vehicle_id"]])
                check(f"route_{index}_load", type(route.get("load_kg")) is int and route["load_kg"] == load)
                check(f"route_{index}_distance", type(route.get("distance_m")) is int and route["distance_m"] == distance)
            check("visit_once", structure and Counter(served) == Counter(visits.keys()))
            check("available_fleet", structure and len(set(used)) == len(used))
            metrics = result.get("metrics", {})
            check("total_distance", structure and type(metrics.get("total_distance_m")) is int and metrics["total_distance_m"] == recomputed_distance)
            check("vehicles_used", structure and type(metrics.get("vehicles_used")) is int and metrics["vehicles_used"] == len(routes))
            score = recomputed_distance * config["distance_weight"] + len(routes) * config["vehicle_weight"]
            check("weighted_cost", structure and type(metrics.get("weighted_cost")) is int and metrics["weighted_cost"] == score)
        return {"status": "pass" if all(c["status"] == "pass" for c in checks) else "fail", "checks": checks,
                "verified_scope": ["request identity", "visit coverage", "declared fleet", "capacity", "matrix route distance including depot return", "weighted objective arithmetic"],
                "unverified": ["global optimality", "infeasibility proof", "business requirements omitted from the input", "supplied matrix road realism", "natural language interpretation"]}
