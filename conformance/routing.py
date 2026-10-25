"""Independent routing checker and bounded exhaustive oracle, not a runtime solver."""

from collections import Counter
from itertools import permutations, product
import math

from jsonschema import Draft202012Validator
from .core_contract import ContractError, SCHEMAS, json_values, parse_json, validate_message


PROFILE = {"id": "routing.basic", "version": "0.1.0"}
EXECUTION = {"id": "execution.sync", "version": "0.1.0"}
CONFIGURATION = parse_json((SCHEMAS / "routing-configuration-0.1.schema.json").read_text())["const"]


def _schema(name, value, code):
    json_values(value)
    schema = parse_json((SCHEMAS / ("routing-" + name + "-0.1.schema.json")).read_text())
    Draft202012Validator.check_schema(schema)
    if not Draft202012Validator(schema).is_valid(value):
        raise ContractError(code)


def validate_problem(problem):
    _schema("input", problem, "INVALID_DATA")
    visits = [v["id"] for v in problem["visits"]]
    vehicles = [v["id"] for v in problem["vehicles"]]
    nodes = problem["matrix"]["node_ids"]
    if len(set(visits)) != len(visits) or len(set(vehicles)) != len(vehicles) or problem["depot"] in visits:
        raise ContractError("DUPLICATE_ID")
    if len(set(nodes)) != len(nodes) or set(nodes) != {problem["depot"], *visits}:
        raise ContractError("MATRIX_NODE_MISMATCH")
    values = problem["matrix"]["values"]
    if len(values) != len(nodes) or any(len(row) != len(nodes) for row in values):
        raise ContractError("MATRIX_SHAPE")
    if any(values[i][i] != 0 for i in range(len(nodes))):
        raise ContractError("MATRIX_DIAGONAL")
    return problem


def validate_request(request):
    validate_message(request)
    if request["kind"] != "request":
        raise ContractError("INVALID_REQUEST")
    if request["domain_profile"] != PROFILE:
        raise ContractError("VERSION_MISMATCH")
    if request["execution_profile"] != EXECUTION:
        raise ContractError("UNSUPPORTED_EXECUTION")
    _schema("configuration", request["configuration"], "UNSUPPORTED_CONFIGURATION")
    validate_problem(request["input"])
    return request


def evaluate(problem, solution):
    validate_problem(problem)
    _schema("solution", solution, "INVALID_SOLUTION")
    vehicles = {v["id"]: v["capacity"] for v in problem["vehicles"]}
    route_ids = [r["vehicle_id"] for r in solution["routes"]]
    if len(set(route_ids)) != len(route_ids) or set(route_ids) != set(vehicles):
        raise ContractError("SOLUTION_VEHICLES")
    demands = {v["id"]: v["demand"] for v in problem["visits"]}
    index = {node: i for i, node in enumerate(problem["matrix"]["node_ids"])}
    counts, loads, costs = Counter(), {}, {}
    for route in solution["routes"]:
        vehicle, visits = route["vehicle_id"], route["visits"]
        if any(visit not in demands for visit in visits):
            raise ContractError("UNKNOWN_VISIT")
        counts.update(visits)
        loads[vehicle] = sum(demands[visit] for visit in visits)
        path = [problem["depot"], *visits, problem["depot"]]
        costs[vehicle] = sum(problem["matrix"]["values"][index[a]][index[b]] for a, b in zip(path, path[1:]))
    capacity_violation = sum(max(0, loads[v] - vehicles[v]) for v in vehicles)
    visit_violation = sum(abs(counts[visit] - 1) for visit in demands)
    return {"feasible": capacity_violation == visit_violation == 0, "total_cost": sum(costs.values()),
            "route_costs": costs, "loads": loads,
            "violations": {"weight_capacity": capacity_violation, "all_visits_once": visit_violation}}


def exhaustive_optimum(problem):
    """Assign visits to vehicles, then enumerate each route; capped to tiny fixtures."""
    validate_problem(problem)
    visits, vehicles = problem["visits"], problem["vehicles"]
    if len(visits) > 7 or len(vehicles) > 3:
        raise ContractError("ORACLE_SCOPE_EXCEEDED")
    index = {node: i for i, node in enumerate(problem["matrix"]["node_ids"])}
    matrix, depot = problem["matrix"]["values"], index[problem["depot"]]
    best, checked = math.inf, 0
    for assignment in product(range(len(vehicles)), repeat=len(visits)):
        groups = [[v for v, owner in zip(visits, assignment) if owner == i] for i in range(len(vehicles))]
        if any(sum(v["demand"] for v in group) > vehicle["capacity"] for group, vehicle in zip(groups, vehicles)):
            continue
        route_minima = []
        for group in groups:
            minimum = math.inf
            for order in permutations(group):
                nodes = [depot] + [index[v["id"]] for v in order] + [depot]
                cost = 0
                for pos in range(len(nodes) - 1):
                    cost += matrix[nodes[pos]][nodes[pos + 1]]
                minimum = min(minimum, cost)
                checked += 1
            route_minima.append(minimum)
        best = min(best, sum(route_minima))
    return {"feasible": best != math.inf, "optimal_cost": None if best == math.inf else best,
            "route_orders_checked": checked, "scope": "all partitions and route permutations within oracle limit"}


def verify_result(request, result):
    validate_request(request)
    validate_message(result)
    if result["kind"] != "result":
        raise ContractError("INVALID_RESULT")
    for field in ("request_id", "capability", "domain_profile", "execution_profile"):
        if request[field] != result[field]:
            raise ContractError("RESULT_MISMATCH", "/" + field)
    if request["configuration"] != result["effective_configuration"]:
        raise ContractError("RESULT_MISMATCH", "/effective_configuration")
    problem = request["input"]
    if result["status"] in {"feasible", "optimal"}:
        measured = evaluate(problem, result["solution"])
        if not measured["feasible"]:
            raise ContractError("INFEASIBLE_SOLUTION")
        metrics = {m["id"]: m for m in result["metrics"]}
        if set(metrics) != {"minimize_total_route_cost"}:
            raise ContractError("EVALUATION_MISMATCH")
        metric = metrics.get("minimize_total_route_cost")
        if metric is None or metric["role"] != "optimized" or metric["unit"] != "meter" or metric["status"] != "evaluated" or metric["value"] != measured["total_cost"] or metric["definition"] != "routing.basic.total_distance.v1":
            raise ContractError("EVALUATION_MISMATCH")
        constraints = {c["id"]: c for c in result["constraints"]}
        if set(constraints) != {"weight_capacity", "all_visits_once"}:
            raise ContractError("EVALUATION_MISMATCH")
        for cid, unit in (("weight_capacity", "kg"), ("all_visits_once", "count")):
            value = constraints.get(cid)
            if value is None or value["role"] != "enforced" or value["status"] != "evaluated" or value["unit"] != unit or value["violation"] != measured["violations"][cid] or value["definition"] != "routing.basic." + cid + ".v1":
                raise ContractError("EVALUATION_MISMATCH")
        if result["status"] == "optimal":
            if result["proof"]["method"] != "exhaustive-enumeration" or exhaustive_optimum(problem)["optimal_cost"] != measured["total_cost"]:
                raise ContractError("UNVERIFIED_PROOF")
        return measured
    if any(m["status"] == "evaluated" for m in result["metrics"] + result["constraints"]):
        raise ContractError("EVALUATION_WITHOUT_SOLUTION")
    if result["status"] == "infeasible":
        method = result["proof"]["method"]
        proven = (method == "total-demand-exceeds-total-capacity" and sum(v["demand"] for v in problem["visits"]) > sum(v["capacity"] for v in problem["vehicles"]))
        proven = proven or (method == "individual-demand-exceeds-all-capacities" and max(v["demand"] for v in problem["visits"]) > max(v["capacity"] for v in problem["vehicles"]))
        proven = proven or (method == "exhaustive-enumeration" and not exhaustive_optimum(problem)["feasible"])
        if not proven:
            raise ContractError("UNVERIFIED_PROOF")
    return None
