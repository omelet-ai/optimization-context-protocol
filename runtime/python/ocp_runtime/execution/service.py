"""A trusted connector supplies API metadata and executes canonical requests.

The connector is installed code, never selected by a request or remote metadata.
Domain payloads remain opaque to the runtime except for their declared schemas.
"""
from copy import deepcopy
from jsonschema import Draft202012Validator
from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.server_package import lint_package, validate_request, require_reference


class ExecutionError(ValueError):
    def __init__(self, code, *, retryable=False, issues=None):
        super().__init__(code)
        self.code, self.retryable = code, retryable
        self.issues = deepcopy(issues or [])


class ExecutionService:
    def __init__(self, descriptor, connector, *, checker=None, descriptor_schema=None):
        self.descriptor = deepcopy(descriptor)
        self.connector, self.checker = connector, checker
        lint_package(self.descriptor, descriptor_schema=descriptor_schema, api_contract=connector.describe(),
                     supported_extensions=("ocp.operations",))
        self.contract_fingerprint = fingerprint(self.descriptor)

    def validate(self, input_value, configuration):
        # Recheck the live contract before every execution: cached discovery is
        # not authority to execute against a changed API.
        if fingerprint(self.descriptor) != self.contract_fingerprint:
            raise ExecutionError("DESCRIPTOR_CHANGED_RELOAD_REQUIRED")
        authority = self.connector.describe()
        for key in ("api", "schemas", "capabilities"):
            require_reference(self.descriptor[key], authority.get(key))
        effective = validate_request(self.descriptor, input_value, configuration)
        validate = getattr(self.connector, "validate", None)
        if validate is not None:
            report = validate(deepcopy(input_value), deepcopy(effective))
            fingerprint(report)
            if not isinstance(report, dict) or type(report.get("valid")) is not bool or not isinstance(report.get("issues"), list):
                raise ExecutionError("API_VALIDATION_RESPONSE_INVALID")
            if not report["valid"]:
                raise ExecutionError("API_INPUT_INVALID", issues=report["issues"])
        return effective

    def request(self, input_value, configuration):
        effective = self.validate(input_value, configuration)
        body = {"input": deepcopy(input_value), "configuration": effective,
                "contract": deepcopy(self.contract_fingerprint)}
        return {**body, "request_fingerprint": fingerprint(body)}

    def execute(self, input_value, configuration):
        request = self.request(input_value, configuration)
        try:
            answer = self.connector.execute(deepcopy(request["input"]), deepcopy(request["configuration"]))
        except ExecutionError:
            raise
        except Exception as error:
            # No request, credential, URL or upstream response text is reflected.
            raise ExecutionError("API_EXECUTION_FAILED") from error
        return self.accept(request, answer)

    def accept(self, request, answer):
        fingerprint(answer)
        fields = {"solution_status", "termination_reason", "result", "effective_configuration", "proof"}
        if not isinstance(answer, dict) or not fields.issubset(answer) or set(answer) - fields - {"result_role"}:
            raise ExecutionError("OUTCOME_INVALID")
        explicit_role = answer.get("result_role")
        if "result_role" in answer:
            if self.descriptor["format_version"] != "0.1.0-draft.2" or explicit_role not in {"solution", "candidate", "diagnostics"} or answer["result"] is None:
                raise ExecutionError("RESULT_ROLE_INVALID")
        state, reason = answer["solution_status"], answer["termination_reason"]
        if state not in {"optimal", "feasible", "infeasible", "unknown"}:
            raise ExecutionError("SOLUTION_STATUS_INVALID")
        if reason not in {"completed", "time_limit", "iteration_limit", "no_solution_found"}:
            raise ExecutionError("TERMINATION_REASON_INVALID")
        if state in {"optimal", "infeasible"}:
            if reason != "completed" or not isinstance(answer["proof"], dict) or not answer["proof"].get("method"):
                raise ExecutionError("PROOF_REQUIRED")
        if state in {"feasible", "optimal"}:
            if answer["result"] is None:
                raise ExecutionError("SOLUTION_MISSING")
            if explicit_role not in {None, "solution"}:
                raise ExecutionError("RESULT_ROLE_INVALID")
        elif answer["result"] is not None:
            permitted = {"candidate", "diagnostics"} if state == "unknown" else {"diagnostics"}
            if explicit_role not in permitted:
                raise ExecutionError("NON_SOLUTION_RESULT")
        if answer["result"] is not None:
            schema = self.descriptor["schemas"][self.descriptor["api"]["result_schema"]]
            if not Draft202012Validator(schema).is_valid(answer["result"]):
                raise ExecutionError("RESULT_SCHEMA_INVALID")
        if answer["effective_configuration"] != request["configuration"]:
            raise ExecutionError("EFFECTIVE_CONFIGURATION_DRIFT")
        result = {**deepcopy(answer), "api": deepcopy(self.descriptor["api"]),
                  "contract": deepcopy(self.contract_fingerprint), "request_fingerprint": deepcopy(request["request_fingerprint"]),
                  "input_fingerprint": fingerprint(request["input"]),
                  "configuration_fingerprint": fingerprint(request["configuration"]),
                  "result_fingerprint": fingerprint(answer["result"]), "evaluation": None}
        if self.checker is not None and (state in {"optimal", "feasible"} or explicit_role == "candidate"):
            evaluation = self.checker.evaluate(deepcopy(request["input"]), deepcopy(request["configuration"]), deepcopy(answer["result"]))
            fingerprint(evaluation)
            if not isinstance(evaluation, dict) or evaluation.get("status") not in {"pass", "fail", "unknown"}:
                raise ExecutionError("CHECKER_RESPONSE_INVALID")
            result["evaluation"] = {**evaluation, "checker": deepcopy(self.checker.identity),
                                    "request_fingerprint": request["request_fingerprint"],
                                    "result_fingerprint": result["result_fingerprint"]}
        return result

    def unknown(self, request, reason="time_limit"):
        return self.accept(request, {"solution_status": "unknown", "termination_reason": reason,
                                   "result": None, "effective_configuration": request["configuration"], "proof": None})
