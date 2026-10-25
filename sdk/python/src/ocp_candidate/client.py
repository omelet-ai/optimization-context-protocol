"""Generic client: explicit requests and response integrity, no domain branching."""

from copy import deepcopy
import uuid

from .contract import OCPError, envelope, failure
from .port import Adapter


class Client:
    def __init__(self, adapter: Adapter):
        self.adapter = adapter
        self.capability = deepcopy(adapter.describe())
        envelope(self.capability)
        if self.capability["kind"] != "capability":
            raise OCPError("INVALID_RESPONSE", message="Expected capability")

    def describe(self):
        return deepcopy(self.capability)

    def requirements(self, configuration=None):
        selected = deepcopy(self.capability["defaults"] if configuration is None else configuration)
        response = deepcopy(self.adapter.requirements(selected))
        envelope(response)
        if response["kind"] == "failure":
            return response
        if response["kind"] != "requirements" or response["capability"] != self.capability["capability"] or response["domain_profile"] != self.capability["domain_profile"] or response["effective_configuration"] != selected:
            raise OCPError("INVALID_RESPONSE", message="Requirements changed identity or selection")
        return response

    def request(self, problem, configuration=None, time_limit_ms=1000, request_id=None):
        return {"core_version":"0.1.0","kind":"request","request_id":str(uuid.uuid4()) if request_id is None else request_id,
                "capability":deepcopy(self.capability["capability"]),"domain_profile":deepcopy(self.capability["domain_profile"]),
                "execution_profile":{"id":"execution.sync","version":"0.1.0"},
                "configuration":deepcopy(self.capability["defaults"] if configuration is None else configuration),
                "input":deepcopy(problem),"budget":{"time_limit_ms":time_limit_ms}}

    def execute(self, problem, configuration=None, time_limit_ms=1000, request_id=None):
        request = self.request(problem, configuration, time_limit_ms, request_id)
        try:
            envelope(request)
            checked = self.adapter.validate(deepcopy(request))
            envelope(checked)
            if checked["kind"] != "validation" or checked["request_id"] != request["request_id"]:
                raise OCPError("INVALID_RESPONSE", message="Invalid validation response")
            if not checked["valid"]:
                issue = checked["issues"][0]
                return failure(request["request_id"], OCPError(issue["code"], issue["path"], issue["message"]))
            response = deepcopy(self.adapter.execute(deepcopy(request)))
            envelope(response)
            if response["kind"] not in {"result", "failure"} or response["request_id"] != request["request_id"]:
                raise OCPError("INVALID_RESPONSE", message="Execution response identity mismatch")
            if response["kind"] == "result":
                for field in ("capability", "domain_profile", "execution_profile"):
                    if response[field] != request[field]:
                        raise OCPError("INVALID_RESPONSE", message="Execution reference changed")
                if response["effective_configuration"] != request["configuration"]:
                    raise OCPError("INVALID_RESPONSE", message="Execution configuration changed")
            return response
        except OCPError as exc:
            return failure(request["request_id"] if isinstance(request["request_id"], str) and request["request_id"] else None, exc)
        except Exception:
            return failure(request["request_id"], OCPError("EXECUTION_ERROR", message="Adapter execution failed"))
