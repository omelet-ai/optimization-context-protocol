"""Installed operation registry with transport principal and durable uncertainty.

Metadata never selects URLs/imports. A registered connector is trusted code; its
declared effects are checked, but a malicious connector is not sandboxed here.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
from jsonschema import Draft202012Validator
from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.operations import EXTENSION, operations, reference
from ocp_candidate.server_package import lint_package
from ocp_runtime.execution.jobs import JobService


class OperationError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OperationConnector:
    describe: object
    invoke: object
    authorize: object


@dataclass(frozen=True)
class OperationAnswer:
    data: object
    effect: str = "none"
    # Optional trusted synchronous completion observation, not a write receipt.
    # None deliberately retains the legacy effect-derived status.
    completion: str | None = None


class OperationService:
    def __init__(self, descriptor, registry, *, journal=None, optimization=None):
        lint_package(descriptor, supported_extensions=(EXTENSION,))
        self.descriptor = deepcopy(descriptor)
        self.digest = fingerprint(self.descriptor)
        self.operations = {op["id"]: op for op in operations(self.descriptor)}
        self.operations_digest = fingerprint(self.operations)
        self.registry = dict(registry)
        self.optimization = optimization
        for op in self.operations.values():
            self._authority(op)
        self.journal = Path(journal) if journal is not None else None
        if self.journal is not None:
            self.journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self._database() as database:
                database.execute("CREATE TABLE IF NOT EXISTS operations (tenant TEXT, caller TEXT, server TEXT, operation TEXT, request_id TEXT, digest TEXT, result TEXT, PRIMARY KEY(tenant,caller,server,operation,request_id))")
                columns = database.execute("PRAGMA table_info(operations)").fetchall()
                if [(row[1], row[5]) for row in columns] != [(name, index + 1 if index < 5 else 0) for index, name in enumerate(("tenant", "caller", "server", "operation", "request_id", "digest", "result"))]:
                    raise OperationError("OPERATION_JOURNAL_SCHEMA_UNSUPPORTED")
            self.journal.chmod(0o600)

    def _database(self):
        if self.journal is None: raise OperationError("COMMAND_JOURNAL_REQUIRED")
        return sqlite3.connect(self.journal, timeout=5)

    def _current(self):
        if fingerprint(self.descriptor) != self.digest or fingerprint(self.operations) != self.operations_digest:
            raise OperationError("OPERATION_PACKAGE_CHANGED")

    def _authority(self, operation):
        if operation["kind"] == "optimization":
            if self.optimization is None or self.optimization.descriptor != self.descriptor:
                raise OperationError("OPTIMIZATION_SERVICE_MISSING_OR_DIFFERENT")
            return None
        connector = self.registry.get(operation["binding"]["connector"])
        if not isinstance(connector, OperationConnector) or not all(callable(v) for v in (connector.describe, connector.invoke, connector.authorize)):
            raise OperationError("OPERATION_CONNECTOR_UNREGISTERED")
        if connector.describe() != operation:
            raise OperationError("OPERATION_CONNECTOR_CONTRACT_CHANGED")
        return connector

    def advertised(self):
        self._current()
        values = []
        for operation in self.operations.values():
            self._authority(operation)
            values.append({**deepcopy(operation), "reference": reference(self.descriptor, operation)})
        return values

    def invoke(self, principal, operation_id, request, *, expected, request_id, context=None, configuration=None, kind):
        JobService._authorize(principal, "read" if kind == "query" else "execute")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", request_id):
            raise OperationError("OPERATION_REQUEST_ID_INVALID")
        self._current()
        operation = self.operations.get(operation_id)
        if operation is None:
            raise OperationError("OPERATION_UNKNOWN")
        if kind != operation["kind"]:
            raise OperationError("OPERATION_KIND_MISMATCH")
        if expected != reference(self.descriptor, operation):
            raise OperationError("OPERATION_REFERENCE_CHANGED")
        connector = self._authority(operation)
        fingerprint({"request": request, "context": context, "configuration": configuration})
        if not Draft202012Validator(self.descriptor["schemas"][operation["request_schema"]]).is_valid(request):
            raise OperationError("OPERATION_REQUEST_INVALID")
        context_ref = operation.get("context_schema")
        if context_ref:
            if context is None or not Draft202012Validator(self.descriptor["schemas"][context_ref]).is_valid(context):
                raise OperationError("OPERATION_CONTEXT_REQUIRED_OR_INVALID")
        elif context is not None:
            raise OperationError("OPERATION_CONTEXT_UNSUPPORTED")
        if kind != "optimization" and configuration is not None:
            raise OperationError("OPERATION_CONFIGURATION_UNSUPPORTED")
        if connector is not None and connector.authorize(principal, deepcopy(context), deepcopy(request)) is not True:
            raise OperationError("OPERATION_SCOPE_FORBIDDEN")
        if kind == "optimization":
            # Retain the existing optimizer's proof, timeout, result-role and
            # evaluation handling. MCP uses its existing asynchronous job tools.
            return self.optimization.execute(deepcopy(request), deepcopy({} if configuration is None else configuration))
        body = {"request": request, "context": context, "reference": expected,
                "principal": {"tenant": principal.tenant, "caller": principal.caller}}
        digest = fingerprint(body)["sha256"]
        key = (principal.tenant, principal.caller, self.descriptor["id"], operation_id, request_id)
        if kind == "command":
            with self._database() as database:
                database.execute("BEGIN IMMEDIATE")
                prior = database.execute("SELECT digest,result FROM operations WHERE tenant=? AND caller=? AND server=? AND operation=? AND request_id=?", key).fetchone()
                if prior is not None:
                    if prior[0] != digest:
                        raise OperationError("OPERATION_REQUEST_ID_CONFLICT")
                    if prior[1] is not None:
                        return {**json.loads(prior[1]), "replayed_observation": True}
                    return self._report(expected, request_id, digest, "uncertain", None, "unknown", "PRIOR_COMMAND_UNRESOLVED")
                database.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,NULL)", (*key, digest))
        try:
            answer = connector.invoke(deepcopy(request), deepcopy(context), principal, request_id)
            if not isinstance(answer, OperationAnswer):
                raise OperationError("OPERATION_RESPONSE_INVALID")
            if answer.completion is not None and (type(answer.completion) is not str or answer.completion != "acknowledged"):
                raise OperationError("OPERATION_COMPLETION_REPORT_INVALID")
            fingerprint(answer.data)
            if answer.effect not in ({"none"} if kind == "query" else {"none", "applied", "partial", "unknown"}):
                raise OperationError("OPERATION_EFFECT_REPORT_INVALID")
            if not Draft202012Validator(self.descriptor["schemas"][operation["response_schema"]]).is_valid(answer.data):
                raise OperationError("OPERATION_RESPONSE_SCHEMA_INVALID")
            # An explicit, schema-validated synchronous ACK distinguishes known
            # completion from unknown mutation detail. It is never inferred from
            # data presence, and does not upgrade a reported partial application.
            status = ("partial" if answer.effect == "partial" else "completed"
                      if answer.completion == "acknowledged" else "uncertain"
                      if answer.effect == "unknown" else "completed")
            result = self._report(expected, request_id, digest, status, answer.data, answer.effect, None)
            if answer.completion is not None:
                result["completion"] = answer.completion
        except Exception as error:
            result = self._report(expected, request_id, digest, "uncertain" if kind == "command" else "failed", None,
                                  "unknown", error.code if isinstance(error, OperationError) else "OPERATION_CONNECTOR_FAILED")
        if kind == "command":
            # A lost final journal write leaves the durable pending row. It can
            # never trigger an automatic second invocation, including restart.
            try:
                with self._database() as database:
                    database.execute("UPDATE operations SET result=? WHERE tenant=? AND caller=? AND server=? AND operation=? AND request_id=?", (json.dumps(result, allow_nan=False), *key))
            except Exception:
                return self._report(expected, request_id, digest, "uncertain", None, "unknown", "COMMAND_JOURNAL_ACK_LOST")
        return result

    @staticmethod
    def _report(reference_value, request_id, digest, status, data, effect, code):
        return {"operation": deepcopy(reference_value), "request_id": request_id, "request_digest": digest,
                "status": status, "data": deepcopy(data), "effect": effect, "code": code,
                "retryable": False, "automatic_retry": False}
