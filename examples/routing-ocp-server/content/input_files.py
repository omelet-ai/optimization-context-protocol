"""Versioned official-table converters; no customer-specific column guessing."""
from copy import deepcopy
from ocp_runtime.inputs import InputConverter, InputError
from .engine import spherical_matrix, validate_problem


def _convert(value, model):
    nodes = [value["depot"]["id"], *[v["id"] for v in value["visits"]]]
    if len(nodes) != len(set(nodes)):
        raise InputError("DEPOT_AND_VISIT_IDS_MUST_BE_UNIQUE", pointer="/visits")
    derivations = [{"pointer": "/depot_id", "source_pointers": ["/depot/id"], "operation": "declared depot ID"},
                   {"pointer": "/distance_matrix/node_ids", "source_pointers": ["/depot/id", "/visits"], "operation": "depot then visit order"}]
    locations = None
    if model == "matrix":
        edges = {}
        for index, edge in enumerate(value["distances"]):
            key = (edge["from_id"], edge["to_id"])
            if key in edges or set(key) - set(nodes):
                raise InputError("DUPLICATE_OR_UNKNOWN_MATRIX_EDGE", pointer="/distances/" + str(index))
            edges[key] = (edge["distance_m"], index)
        if set(edges) != {(a, b) for a in nodes for b in nodes}:
            raise InputError("COMPLETE_DIRECTED_MATRIX_REQUIRED", pointer="/distances")
        matrix = [[edges[a, b][0] for b in nodes] for a in nodes]
        for i, a in enumerate(nodes):
            for j, b in enumerate(nodes):
                derivations.append({"pointer": f"/distance_matrix/distances_m/{i}/{j}",
                    "source_pointers": [f"/distances/{edges[a,b][1]}/distance_m"], "operation": "copy explicit integer metres"})
        distance_model = "supplied_matrix"
        model_sources = ["/distances"]
    else:
        source = {v["id"]: (index, v) for index, v in enumerate(value["locations"])}
        if len(source) != len(value["locations"]) or set(source) != set(nodes):
            raise InputError("COORDINATES_MUST_COVER_EXACT_NODE_SET", pointer="/locations")
        for index, location in enumerate(value["locations"]):
            if not -90 <= location["latitude"] <= 90 or not -180 <= location["longitude"] <= 180:
                raise InputError("COORDINATE_RANGE_INVALID", pointer="/locations/" + str(index))
        locations = [deepcopy(source[n][1]) for n in nodes]
        matrix = spherical_matrix(locations)
        for i, a in enumerate(nodes):
            for j, b in enumerate(nodes):
                derivations.append({"pointer": f"/distance_matrix/distances_m/{i}/{j}",
                    "source_pointers": [f"/locations/{source[n][0]}/{field}" for n in (a, b) for field in ("latitude", "longitude")],
                    "operation": "haversine sphere R=6371008.8m; round half up to integer metre; not road distance"})
        distance_model = "haversine_sphere_6371008.8m_half_up"
        model_sources = ["/locations"]
    derivations.extend([
        {"pointer": "/distance_model", "source_pointers": model_sources, "operation": "declared input format distance model"},
        {"pointer": "/source_coordinates", "source_pointers": model_sources, "operation": "retain source coordinates in canonical node order, or null for supplied matrix"}])
    canonical = {"depot_id": value["depot"]["id"], "visits": deepcopy(value["visits"]), "vehicles": deepcopy(value["vehicles"]),
                 "distance_matrix": {"node_ids": nodes, "distances_m": matrix}, "distance_model": distance_model, "source_coordinates": locations}
    checked = validate_problem(canonical)
    if not checked["valid"]:
        first = checked["issues"][0]
        raise InputError(first["code"], pointer=first["pointer"])
    return {"input": canonical, "derivations": derivations}


def matrix(value): return _convert(value, "matrix")
def coordinates(value): return _convert(value, "coordinates")


def converters():
    return {"routing/matrix": InputConverter("routing/matrix", "1.0.0", matrix),
            "routing/coordinates": InputConverter("routing/coordinates", "1.0.0", coordinates)}
