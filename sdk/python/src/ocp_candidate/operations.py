"""Private optional extension candidate, never executable metadata."""
from copy import deepcopy
from importlib.resources import files
import json
from jsonschema import Draft202012Validator
from .fingerprint import fingerprint
from .server_package import PackageError

EXTENSION = "ocp.operations"
VERSION = "0.1.0-draft.2"


def operations(document):
    extension = document["extensions"].get(EXTENSION)
    if extension is None:
        return []
    schema = json.loads(files("ocp_candidate").joinpath("schemas", "operations-0.1.schema.json").read_text())
    if not Draft202012Validator(schema).is_valid(extension):
        raise PackageError("OPERATIONS_EXTENSION_INVALID")
    values = extension["operations"]
    ids = [value["id"] for value in values]
    if len(ids) != len(set(ids)):
        raise PackageError("OPERATION_ID_DUPLICATE")
    for operation in values:
        format_ids = [f["id"] for f in operation.get("input_formats", [])]
        if len(format_ids) != len(set(format_ids)):
            raise PackageError("OPERATION_FORMAT_ID_DUPLICATE", operation["id"])
        for key in ("request_schema", "response_schema", "context_schema"):
            if key in operation and operation[key] not in document["schemas"]:
                raise PackageError("OPERATION_SCHEMA_MISSING", operation["id"] + "/" + key)
        kind, effect, binding = operation["kind"], operation["effects"], operation["binding"]
        if effect != ("optimization_context_write" if kind == "command" else "none"):
            raise PackageError("OPERATION_EFFECT_MISMATCH", operation["id"])
        if kind == "optimization":
            api = document["api"]
            if (operation["execution"] != "existing_optimization_api" or
                binding != {"api_id": api["id"], "api_version": api["version"]} or
                operation["request_schema"] != api["input_schema"] or
                operation["response_schema"] != api["result_schema"] or "context_schema" in operation):
                raise PackageError("OPTIMIZATION_BRIDGE_MISMATCH", operation["id"])
        elif operation["execution"] != "sync" or set(binding) != {"connector"}:
            raise PackageError("OPERATION_BINDING_INVALID", operation["id"])
    return deepcopy(values)


def reference(document, operation):
    """Digest includes all schemas/effects/context and the whole package contract."""
    return {"id": operation["id"], "version": operation["version"],
            "operation_digest": fingerprint({"operation": operation, "schemas": document["schemas"]}),
            "package_digest": fingerprint(document)}
