"""Second-domain fixture evaluation. This module is not an execution engine."""

from jsonschema import Draft202012Validator
from .core_contract import ContractError, SCHEMAS, parse_json, validate_message

PROFILE = {"id":"assignment.fixture", "version":"0.1.0"}
CONFIG = {"objectives":[{"id":"cost","weight":1}],"constraints":["unique_assignment"],"parameters":{}}


def verify_result(request, result):
    validate_message(request); validate_message(result)
    if request["kind"] != "request" or result["kind"] != "result":
        raise ContractError("INVALID_RESULT")
    if request["domain_profile"] != PROFILE or request["execution_profile"] != {"id":"execution.sync","version":"0.1.0"}:
        raise ContractError("VERSION_MISMATCH")
    for field in ("request_id", "capability", "domain_profile", "execution_profile"):
        if request[field] != result[field]: raise ContractError("RESULT_MISMATCH")
    if request["configuration"] != CONFIG or result["effective_configuration"] != CONFIG:
        raise ContractError("UNSUPPORTED_CONFIGURATION")
    data = request["input"]
    definition = parse_json((SCHEMAS / "assignment-fixture-input-0.1.schema.json").read_text())
    if not Draft202012Validator(definition).is_valid(data): raise ContractError("INVALID_DATA")
    items, workers, costs = data["items"], data["workers"], data["costs"]
    if len(items) != len(set(items)) or len(workers) != len(set(workers)) or len(costs) != len(items) or any(len(row)!=len(workers) for row in costs):
        raise ContractError("INVALID_DATA")
    # The fixture suite certifies feasible witnesses only, never solver/proof claims.
    if result["status"] != "feasible": raise ContractError("UNTESTED_PROOF_CLAIM")
    solution = result["solution"]
    definition = parse_json((SCHEMAS / "assignment-fixture-solution-0.1.schema.json").read_text())
    if not Draft202012Validator(definition).is_valid(solution): raise ContractError("INVALID_SOLUTION")
    pairs = solution["assignments"]
    if sorted(pair[0] for pair in pairs) != sorted(items) or len({pair[1] for pair in pairs}) != len(pairs) or any(pair[1] not in workers for pair in pairs):
        raise ContractError("INVALID_SOLUTION")
    value = sum(costs[items.index(item)][workers.index(worker)] for item,worker in pairs)
    metrics, constraints = result["metrics"], result["constraints"]
    if len(metrics)!=1 or any(metrics[0][k]!=v for k,v in {"id":"cost","role":"optimized","definition":"sum of assigned costs","unit":"cost_unit","status":"evaluated","value":value}.items()):
        raise ContractError("EVALUATION_MISMATCH")
    if len(constraints)!=1 or any(constraints[0][k]!=v for k,v in {"id":"unique_assignment","role":"enforced","definition":"each item assigned once","unit":"count","status":"evaluated","violation":0,"satisfied":True}.items()):
        raise ContractError("EVALUATION_MISMATCH")
    return {"feasible":True,"total_cost":value}
