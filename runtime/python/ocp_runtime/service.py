"""Provider-neutral synchronous operation dispatch."""

from copy import deepcopy
from ocp_candidate.contract import OCPError, envelope, failure


class Service:
    def __init__(self, adapter):
        self.adapter = adapter

    def dispatch(self, operation, payload=None, binding="binding.http", **context):
        request_id = "invalid-request"
        try:
            if isinstance(payload, dict):
                candidate = payload.get("request_id")
                if isinstance(candidate, str) and 0 < len(candidate) <= 128: request_id = candidate
            if operation == "describe":
                response = deepcopy(self.adapter.describe())
                response["bindings"] = [{"id":binding,"version":"0.1.0"}]
            elif operation == "requirements":
                if not isinstance(payload,dict) or set(payload)!={"configuration"}: raise OCPError("INVALID_REQUEST")
                response = self.adapter.requirements(payload["configuration"])
            elif operation in {"validate","execute"}:
                response = getattr(self.adapter, operation)(payload)
            elif operation == "evaluate":
                if not isinstance(payload,dict) or set(payload)!={"request","solution"}: raise OCPError("INVALID_REQUEST")
                response = self.adapter.evaluate(payload["request"],payload["solution"])
            else:
                raise OCPError("UNSUPPORTED_OPERATION",message="Operation is not supported")
            envelope(response)
            return response
        except OCPError as error:
            return failure(request_id,error)
        except Exception:
            return failure(request_id,OCPError("EXECUTION_ERROR",message="Provider failed; response unavailable"))
