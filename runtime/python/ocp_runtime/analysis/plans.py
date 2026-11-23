"""Plan compiler: explicit bindings only, no code evaluation or inferred edits."""
from copy import deepcopy
import itertools
from jsonschema import Draft202012Validator
from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.server_package import at, tokens, PackageError


class AnalysisError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _replace(value, pointer, replacement):
    parts = tokens(pointer)
    if not parts:
        return deepcopy(replacement)
    parent = value
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
    # Existence has already been checked by at(); this cannot create fields.
    parent[key] = deepcopy(replacement)
    return value


def apply_binding(candidate, binding, value):
    if not Draft202012Validator(binding["value_schema"]).is_valid(value):
        raise AnalysisError("BINDING_VALUE_INVALID")
    target, pointer = binding["target"], binding["pointer"]
    current = at(candidate[target], pointer)
    if binding["operation"] == "select_by_id":
        if not isinstance(value, list) or any(type(v) is not str for v in value) or len(set(value)) != len(value):
            raise AnalysisError("SELECTION_IDS_INVALID")
        if not isinstance(current, list) or any(not isinstance(v, dict) or type(v.get(binding["id_field"])) is not str for v in current):
            raise AnalysisError("SELECTION_SOURCE_INVALID")
        ids = [v[binding["id_field"]] for v in current]
        if len(set(ids)) != len(ids) or set(value) - set(ids):
            raise AnalysisError("SELECTION_ID_UNKNOWN_OR_DUPLICATE")
        selected = set(value)
        value = [v for v in current if v[binding["id_field"]] in selected]
    elif binding["operation"] != "replace":
        raise AnalysisError("BINDING_OPERATION_UNSUPPORTED")
    candidate[target] = _replace(candidate[target], pointer, value)


def build_plan(service, playbook_id, input_value, configuration, *, variables=None, budget=None, ranking_metric=None):
    d = service.descriptor
    recipe = next((p for p in d["playbooks"] if p["id"] == playbook_id), None)
    if recipe is None or recipe["status"] != "executable" or "recipe" not in recipe or "budget" not in recipe:
        raise AnalysisError("PLAYBOOK_NOT_EXECUTABLE")
    baseline = service.request(input_value, configuration)
    bindings = {b["id"]: b for b in d["bindings"]}
    variables = deepcopy(recipe["recipe"]["variables"] if variables is None else variables)
    allowed_variables = {v["binding"] for v in recipe["recipe"]["variables"]}
    if not isinstance(variables, list) or not variables:
        raise AnalysisError("VARIABLES_REQUIRED")
    seen = set()
    for v in variables:
        if not isinstance(v, dict) or set(v) != {"binding", "values"} or v["binding"] not in allowed_variables or v["binding"] not in recipe["binding_ids"] or v["binding"] in seen:
            raise AnalysisError("VARIABLE_NOT_ALLOWED")
        if not isinstance(v["values"], list) or not 1 <= len(v["values"]) <= 100:
            raise AnalysisError("VARIABLE_VALUES_INVALID")
        seen.add(v["binding"])
    effective_budget = deepcopy(recipe["budget"])
    if budget is not None:
        if not isinstance(budget, dict) or set(budget) - set(effective_budget):
            raise AnalysisError("BUDGET_INVALID")
        effective_budget.update(budget)
    for name in ("max_calls", "timeout_seconds", "concurrency"):
        amount = effective_budget[name]
        if type(amount) not in (int, float) or not 0 < amount <= recipe["budget"][name]:
            raise AnalysisError("BUDGET_EXCEEDS_DECLARATION")
        if name != "timeout_seconds" and type(amount) is not int:
            raise AnalysisError("BUDGET_INVALID")
    if effective_budget["max_calls"] > 100 or effective_budget["concurrency"] > 8 or effective_budget["timeout_seconds"] > 3600:
        raise AnalysisError("RUNTIME_BUDGET_LIMIT")
    metrics = {m["id"]: m for m in d["metrics"] if m["id"] in recipe["metric_ids"]}
    if ranking_metric is not None and (ranking_metric not in metrics or metrics[ranking_metric]["direction"] == "none"):
        raise AnalysisError("RANKING_CRITERION_UNSUPPORTED")
    groups = [[(v["binding"], item) for item in v["values"]] for v in variables]
    kind = recipe["recipe"]["kind"]
    if kind == "grid":
        count = 1
        for group in groups: count *= len(group)
        if count > 100:
            raise AnalysisError("TOO_MANY_CANDIDATES")
        choices = list(itertools.product(*groups))
    elif kind == "independent_variations":
        if sum(map(len, groups)) > 100:
            raise AnalysisError("TOO_MANY_CANDIDATES")
        choices = [[item] for group in groups for item in group]
    else:
        raise AnalysisError("RECIPE_KIND_UNSUPPORTED")
    candidates, unique = [], set()
    for edits in [[], *choices]:
        candidate = {"input": deepcopy(baseline["input"]), "configuration": deepcopy(baseline["configuration"])}
        for binding_id, value in edits:
            apply_binding(candidate, bindings[binding_id], value)
        for preserve in recipe["preserve"]:
            if at(candidate[preserve["target"]], preserve["pointer"]) != at(baseline[preserve["target"]], preserve["pointer"]):
                raise AnalysisError("PRESERVED_INPUT_CHANGED")
        request = service.request(candidate["input"], candidate["configuration"])
        digest = request["request_fingerprint"]["sha256"]
        if digest not in unique:
            unique.add(digest)
            candidates.append({"id": str(len(candidates)), "edits": [{"binding": k, "value": deepcopy(v)} for k, v in edits], "request": request})
    if len(candidates) > effective_budget["max_calls"]:
        raise AnalysisError("CALL_BUDGET_TOO_SMALL")
    # Field defaults are conservative: a metric must explicitly promise
    # invariant semantics to rank settings with different configuration.
    configs = {fingerprint(c["request"]["configuration"])["sha256"] for c in candidates}
    weighted_bindings = {v.get("weight_binding") for v in d["capabilities"]["objectives"]}
    changed_weights = any(edit["binding"] in weighted_bindings for c in candidates for edit in c["edits"])
    if ranking_metric is not None and (len(configs) > 1 or changed_weights) and metrics[ranking_metric].get("comparison_basis", "same_configuration") != "invariant":
        raise AnalysisError("METRIC_NOT_COMPARABLE_ACROSS_CONFIGURATION")
    result = {"version": "0.1.0-draft.1", "descriptor": deepcopy(service.contract_fingerprint),
              "playbook": {"id": recipe["id"], "version": recipe["version"], "fingerprint": fingerprint(recipe)},
              "baseline": baseline, "variables": variables, "budget": effective_budget,
              "metrics": deepcopy(metrics), "ranking_metric": ranking_metric, "candidates": candidates}
    return {**result, "plan_fingerprint": fingerprint(result)}


def verify_plan(service, plan):
    new = build_plan(service, plan["playbook"]["id"], plan["baseline"]["input"], plan["baseline"]["configuration"],
                     variables=plan["variables"], budget=plan["budget"], ranking_metric=plan["ranking_metric"])
    if new != plan:
        raise AnalysisError("PLAN_STALE_OR_CHANGED")
