"""Actual bounded OR-Tools CVRP with explicitly weighted fleet costs."""
from copy import deepcopy
import json
import math
from pathlib import Path
from ocp_candidate.fingerprint import fingerprint
from ocp_runtime.execution import ExecutionError


def descriptor():
    return json.loads(Path(__file__).with_name("manifest.json").read_text())


def spherical_matrix(locations):
    def distance(a, b):
        p, q = math.radians(a["latitude"]), math.radians(b["latitude"])
        delta = math.radians(b["longitude"] - a["longitude"])
        h = math.sin((q - p) / 2) ** 2 + math.cos(p) * math.cos(q) * math.sin(delta / 2) ** 2
        return math.floor(2 * 6371008.8 * math.asin(min(1.0, math.sqrt(max(0.0, h)))) + 0.5)
    return [[distance(a, b) for b in locations] for a in locations]


def validate_problem(data):
    issues = []
    def issue(code, pointer): issues.append({"code": code, "pointer": pointer})
    nodes = data["distance_matrix"]["node_ids"]
    matrix = data["distance_matrix"]["distances_m"]
    visits, vehicles = data["visits"], data["vehicles"]
    if len(set(nodes)) != len(nodes): issue("DUPLICATE_NODE_ID", "/distance_matrix/node_ids")
    if len(matrix) != len(nodes) or any(len(row) != len(nodes) for row in matrix):
        issue("MATRIX_DIMENSION_MISMATCH", "/distance_matrix/distances_m")
    elif any(matrix[i][i] != 0 for i in range(len(nodes))):
        issue("MATRIX_DIAGONAL_MUST_BE_ZERO", "/distance_matrix/distances_m")
    visit_ids = [v["id"] for v in visits]
    if len(set(visit_ids)) != len(visits): issue("DUPLICATE_VISIT_ID", "/visits")
    if len({v["id"] for v in vehicles}) != len(vehicles): issue("DUPLICATE_VEHICLE_ID", "/vehicles")
    if data["depot_id"] in visit_ids or set(nodes) != {data["depot_id"], *visit_ids}:
        issue("NODE_SET_MUST_MATCH_DEPOT_AND_VISITS", "/distance_matrix/node_ids")
    locations = data["source_coordinates"]
    if data["distance_model"] == "supplied_matrix":
        if locations is not None: issue("UNUSED_COORDINATES", "/source_coordinates")
    else:
        if locations is None or len(locations) != len(nodes) or [v["id"] for v in locations] != nodes:
            issue("COORDINATES_MUST_MATCH_NODE_ORDER", "/source_coordinates")
        elif spherical_matrix(locations) != matrix:
            issue("DECLARED_DISTANCE_MODEL_MISMATCH", "/distance_matrix/distances_m")
    return {"valid": not issues, "issues": issues}


class LibraryConnector:
    isolation = "local_process"

    def describe(self):
        d = descriptor()
        return {k: d[k] for k in ("api", "schemas", "capabilities")}

    def validate(self, input_value, configuration):
        return validate_problem(input_value)

    def execute(self, data, config):
        checked = validate_problem(data)
        if not checked["valid"]:
            raise ExecutionError("API_INPUT_INVALID", issues=checked["issues"])
        visits, vehicles = data["visits"], data["vehicles"]
        def outcome(state, result=None, reason="completed", proof=None):
            return {"solution_status": state, "termination_reason": reason, "result": result,
                    "effective_configuration": deepcopy(config), "proof": proof}
        if sum(v["demand_kg"] for v in visits) > sum(v["capacity_kg"] for v in vehicles):
            return outcome("infeasible", proof={"method": "total demand exceeds total fleet capacity"})
        if any(v["demand_kg"] > max(vh["capacity_kg"] for vh in vehicles) for v in visits):
            return outcome("infeasible", proof={"method": "an indivisible visit exceeds every vehicle capacity"})
        if not visits:
            return outcome("optimal", {"routes": [], "metrics": {"total_distance_m": 0, "vehicles_used": 0, "weighted_cost": 0}, "input_fingerprint": fingerprint(data)}, proof={"method": "empty visit set and nonnegative costs"})
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        nodes, matrix = data["distance_matrix"]["node_ids"], data["distance_matrix"]["distances_m"]
        depot = nodes.index(data["depot_id"])
        manager = pywrapcp.RoutingIndexManager(len(nodes), len(vehicles), depot)
        routing = pywrapcp.RoutingModel(manager)
        cost = routing.RegisterTransitCallback(lambda a, b: matrix[manager.IndexToNode(a)][manager.IndexToNode(b)] * config["distance_weight"])
        routing.SetArcCostEvaluatorOfAllVehicles(cost)
        routing.SetFixedCostOfAllVehicles(config["vehicle_weight"])
        demands = {v["id"]: v["demand_kg"] for v in visits}
        demand_index = routing.RegisterUnaryTransitCallback(lambda i: demands.get(nodes[manager.IndexToNode(i)], 0))
        routing.AddDimensionWithVehicleCapacity(demand_index, 0, [v["capacity_kg"] for v in vehicles], True, "CapacityKg")
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        params.time_limit.FromMilliseconds(max(1, int(config["time_limit_seconds"] * 1000)))
        answer = routing.SolveWithParameters(params)
        status = routing.status()
        if answer is None:
            if status == 5: raise ExecutionError("SOLVER_MODEL_REJECTED")
            return outcome("unknown", reason="time_limit" if status == 4 else "no_solution_found")
        routes = []
        for index, vehicle in enumerate(vehicles):
            current, served, length = routing.Start(index), [], 0
            while not routing.IsEnd(current):
                nxt = answer.Value(routing.NextVar(current))
                a, b = manager.IndexToNode(current), manager.IndexToNode(nxt)
                length += matrix[a][b]
                if a != depot: served.append(nodes[a])
                current = nxt
            if served:
                routes.append({"vehicle_id": vehicle["id"], "visits": served, "distance_m": length,
                               "load_kg": sum(demands[v] for v in served)})
        distance = sum(r["distance_m"] for r in routes)
        score = distance * config["distance_weight"] + len(routes) * config["vehicle_weight"]
        if score != int(answer.ObjectiveValue()): raise ExecutionError("SOLVER_OBJECTIVE_MISMATCH")
        result = {"routes": routes, "metrics": {"total_distance_m": distance, "vehicles_used": len(routes), "weighted_cost": score}, "input_fingerprint": fingerprint(data)}
        return outcome("feasible", result, reason="time_limit" if status == 2 else "completed")
