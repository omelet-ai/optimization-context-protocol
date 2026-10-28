"""Versioned spherical coordinates profile. No provider-specific meaning is implicit."""
from copy import deepcopy
import math

from ocp_candidate.contract import OCPError, envelope, validate, schema
from . import profile as matrix_profile
from .adapter import RoutingAdapter

DOMAIN = {"id": "routing.coordinates", "version": "0.1.0"}
SYNC = matrix_profile.SYNC
configuration = matrix_profile.configuration


def check_input(data):
    validate("routing-coordinates-input", data, "INVALID_DATA")
    visits = [v["id"] for v in data["visits"]]
    vehicles = [v["id"] for v in data["vehicles"]]
    if len(set(visits)) != len(visits) or len(set(vehicles)) != len(vehicles) or data["depot"]["id"] in visits:
        raise OCPError("INVALID_DATA", message="Duplicate coordinates profile identity")


def check_request(request, capability):
    envelope(request)
    if request["kind"] != "request": raise OCPError("INVALID_REQUEST")
    if request["capability"] != capability or request["domain_profile"] != DOMAIN: raise OCPError("VERSION_MISMATCH")
    if request["execution_profile"] != SYNC: raise OCPError("UNSUPPORTED_EXECUTION")
    configuration(request["configuration"])
    check_input(request["input"])
    if not 1000 <= request["budget"]["time_limit_ms"] <= 5000:
        raise OCPError("LIMIT_EXCEEDED", "/budget/time_limit_ms", "Coordinates candidate supports 1000-5000 ms solver budgets")


def to_matrix(problem):
    check_input(problem)
    points = [problem["depot"], *problem["visits"]]
    values = []
    for a in points:
        row = []
        for b in points:
            x, y = a["location"], b["location"]
            lat1, lat2 = math.radians(x["latitude"]), math.radians(y["latitude"])
            dl = math.radians(x["longitude"]) - math.radians(y["longitude"])
            h = math.sin((lat1-lat2)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2
            h = max(0.0, min(1.0, h))
            row.append(math.ceil(6371000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1-h))))
        values.append(row)
    return {"depot": problem["depot"]["id"], "load_unit": "kg", "vehicles": deepcopy(problem["vehicles"]),
            "visits": [{"id":v["id"], "demand":v["demand"]} for v in problem["visits"]],
            "matrix": {"node_ids":[p["id"] for p in points], "values":values,
                       "unit":"meter", "model":"explicit_matrix", "rounding":"none"}}


def evaluation_fields(problem, solution, source="engine"):
    metrics, constraints = matrix_profile.evaluation_fields(to_matrix(problem), solution, source)
    for item in metrics + constraints:
        item["definition"] = item["definition"].replace("routing.basic.", "routing.coordinates.")
    return metrics, constraints


class CoordinateLibraryBackend:
    """Turn explicit coordinates into the declared matrix for any compatible local library."""
    def __init__(self, library):
        self.library = library
        self.name, self.version = library.name, library.version

    def solve(self, problem, time_limit_ms):
        return self.library.solve(to_matrix(problem), time_limit_ms)


class CoordinatesAdapter(RoutingAdapter):
    def __init__(self, backend, identity=None):
        super().__init__(backend)
        # Module object supplies the same profile operations as the matrix adapter.
        import sys
        self.profile = sys.modules[__name__]
        self.identity = identity or {"id":"routing.coordinates.reference", "version":"0.1.0"}

    def describe(self):
        value = super().describe()
        value["input_schema_id"] = schema("routing-coordinates-input")["$id"]
        for item in value["objectives"] + value["constraints"]:
            item["definition"] = item["definition"].replace("routing.basic.", "routing.coordinates.")
        value["limitations"] = ["Spherical Haversine R=6371000 m; ceil each edge; no road routing",
                                "2-16 vehicles, 1-64 visits, integer kg; solver budget 1000-5000 ms",
                                "Total distance only; fixed/time costs zero; all visits once; depot round trip",
                                "Independent feasible result checking; no general optimality certificate"]
        return value

    def requirements(self, selected):
        value = super().requirements(selected)
        if value["kind"] == "requirements":
            value["input_schema_id"] = schema("routing-coordinates-input")["$id"]
            value["required_fields"] = [{"path":p,"reason":r,"unit":u} for p,r,u in [
                ("/depot/location","Shared origin and return location","degree"),
                ("/visits","Mandatory locations and integer demands","kg"),
                ("/vehicles","Vehicle identities and integer capacities","kg"),
                ("/distance","Explicit spherical distance and rounding definition","meter"),
                ("/load_unit","Shared mass unit","kg")]]
        return value
