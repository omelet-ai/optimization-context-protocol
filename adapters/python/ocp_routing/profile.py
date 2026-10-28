"""Runtime routing semantics, separate from the independent conformance oracle."""

from copy import deepcopy
from ocp_candidate.contract import OCPError, envelope, schema, validate


DOMAIN = {"id":"routing.basic","version":"0.1.0"}
SYNC = {"id":"execution.sync","version":"0.1.0"}


def configuration(value=None):
    selected = deepcopy(schema("routing-configuration")["const"] if value is None else value)
    validate("routing-configuration", selected, "UNSUPPORTED_CONFIGURATION")
    return selected


def check_input(data):
    validate("routing-input", data, "INVALID_DATA")
    visit_ids = [v["id"] for v in data["visits"]]
    vehicle_ids = [v["id"] for v in data["vehicles"]]
    node_ids = data["matrix"]["node_ids"]
    if len(set(visit_ids)) != len(visit_ids) or len(set(vehicle_ids)) != len(vehicle_ids) or data["depot"] in visit_ids:
        raise OCPError("INVALID_DATA", message="IDs must be unique within each entity collection")
    expected = set(visit_ids) | {data["depot"]}
    if len(set(node_ids)) != len(node_ids) or set(node_ids) != expected:
        raise OCPError("INVALID_DATA", "/matrix/node_ids", "Matrix identities differ from input")
    matrix = data["matrix"]["values"]
    if len(matrix) != len(node_ids) or any(len(row) != len(node_ids) for row in matrix):
        raise OCPError("INVALID_DATA", "/matrix/values", "Matrix must be square")
    if any(row[i] != 0 for i,row in enumerate(matrix)):
        raise OCPError("INVALID_DATA", "/matrix/values", "Diagonal distances must be zero")


def check_request(request, capability):
    envelope(request)
    if request["kind"] != "request":
        raise OCPError("INVALID_REQUEST", message="Expected execution request")
    if request["capability"] != capability or request["domain_profile"] != DOMAIN:
        raise OCPError("VERSION_MISMATCH", message="Capability or domain version is unsupported")
    if request["execution_profile"] != SYNC:
        raise OCPError("UNSUPPORTED_EXECUTION", message="Provider supports local synchronous execution")
    configuration(request["configuration"])
    check_input(request["input"])
    if request["budget"]["time_limit_ms"] > 5000:
        raise OCPError("LIMIT_EXCEEDED", "/budget/time_limit_ms", "Reference solver budget must be at most 5000 ms")


def measurements(problem, solution):
    check_input(problem)
    validate("routing-solution", solution, "INVALID_SOLUTION")
    demands = {v["id"]:int(v["demand"]) for v in problem["visits"]}
    capacities = {v["id"]:int(v["capacity"]) for v in problem["vehicles"]}
    routes = solution["routes"]
    if len(routes) != len(capacities) or {r["vehicle_id"] for r in routes} != set(capacities):
        raise OCPError("INVALID_SOLUTION", message="Exactly one route per vehicle is required")
    positions = {node:i for i,node in enumerate(problem["matrix"]["node_ids"])}
    matrix = problem["matrix"]["values"]
    assigned = {visit:0 for visit in demands}
    total, overload = 0, 0
    for route in routes:
        last = problem["depot"]
        load = 0
        for visit in route["visits"]:
            if visit not in demands:
                raise OCPError("INVALID_SOLUTION", message="Unknown visit in route")
            assigned[visit] += 1
            load += demands[visit]
            total += int(matrix[positions[last]][positions[visit]])
            last = visit
        total += int(matrix[positions[last]][positions[problem["depot"]]])
        overload += max(0,load-capacities[route["vehicle_id"]])
    wrong_visits = sum(abs(count-1) for count in assigned.values())
    return total, overload, wrong_visits


def evaluation_fields(problem, solution, source="engine"):
    total, overload, visits = measurements(problem,solution)
    metrics=[{"id":"minimize_total_route_cost","role":"optimized","definition":"routing.basic.total_distance.v1",
              "unit":"meter","source":source,"status":"evaluated","value":total,"reason":None}]
    constraints=[{"id":cid,"role":"enforced","definition":"routing.basic."+cid+".v1","unit":unit,
                  "source":source,"status":"evaluated","violation":amount,"satisfied":amount==0,"reason":None}
                 for cid,unit,amount in [("weight_capacity","kg",overload),("all_visits_once","count",visits)]]
    return metrics,constraints
