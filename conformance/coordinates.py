"""Independent coordinates evaluator: no adapter or engine imports."""
from copy import deepcopy
import math
from jsonschema import Draft202012Validator
from .core_contract import ContractError, SCHEMAS, json_values, parse_json, validate_message
from . import routing

PROFILE = {"id":"routing.coordinates", "version":"0.1.0"}


def to_matrix(problem):
    json_values(problem)
    model = parse_json((SCHEMAS / "routing-coordinates-input-0.1.schema.json").read_text())
    if not Draft202012Validator(model).is_valid(problem): raise ContractError("INVALID_DATA")
    locations = [problem["depot"], *problem["visits"]]
    edges = []
    # Separate scalar implementation using asin; fixed expected fixtures check rounding.
    for origin in locations:
        line = []
        for dest in locations:
            a,b = origin["location"],dest["location"]
            rad = math.pi / 180
            p,q = a["latitude"] * rad,b["latitude"] * rad
            hav = math.sin((p-q)/2)**2 + math.cos(p)*math.cos(q)*math.sin((a["longitude"]-b["longitude"])*rad/2)**2
            line.append(math.ceil(12742000 * math.asin(math.sqrt(min(1,max(0,hav))))))
        edges.append(line)
    output = {"depot":problem["depot"]["id"],"load_unit":"kg","vehicles":deepcopy(problem["vehicles"]),
              "visits":[{"id":v["id"],"demand":v["demand"]} for v in problem["visits"]],
              "matrix":{"node_ids":[p["id"] for p in locations],"values":edges,
                        "model":"explicit_matrix","rounding":"none","unit":"meter"}}
    routing.validate_problem(output)
    return output


def evaluate(problem, solution): return routing.evaluate(to_matrix(problem),solution)
def exhaustive_optimum(problem): return routing.exhaustive_optimum(to_matrix(problem))


def verify_result(request, result):
    validate_message(request); validate_message(result)
    if request["domain_profile"] != PROFILE or result.get("domain_profile") != PROFILE:
        raise ContractError("VERSION_MISMATCH")
    if not 1000 <= request["budget"]["time_limit_ms"] <= 5000: raise ContractError("LIMIT_EXCEEDED")
    req,res = deepcopy(request),deepcopy(result)
    req["input"] = to_matrix(request["input"])
    req["domain_profile"] = res["domain_profile"] = routing.PROFILE
    for item in res.get("metrics",[]) + res.get("constraints",[]):
        if not item["definition"].startswith("routing.coordinates."): raise ContractError("EVALUATION_MISMATCH")
        item["definition"] = item["definition"].replace("routing.coordinates.","routing.basic.",1)
    return routing.verify_result(req,res)
