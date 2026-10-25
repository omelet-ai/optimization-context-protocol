"""Candidate Core structural checks; no engine execution or network access."""

import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = Path(__file__).resolve().parent / "schemas"
if not SCHEMAS.is_dir():
    SCHEMAS = ROOT / "spec/schemas"
SCHEMA_PATH = SCHEMAS / "core-0.1.schema.json"


class ContractError(ValueError):
    def __init__(self, code, path=""):
        super().__init__(code + (" at " + path if path else ""))
        self.code, self.path = code, path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def parse_json(text):
    def reject_constant(value):
        raise ContractError("NONFINITE_NUMBER")
    try:
        result = json.loads(text, object_pairs_hook=_pairs, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise ContractError("INVALID_JSON") from exc
    json_values(result)
    return result


def json_values(value):
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ContractError("INVALID_JSON_KEY")
        for child in value.values():
            json_values(child)
    elif isinstance(value, list):
        for child in value:
            json_values(child)
    elif type(value) in (int, float):
        if (type(value) is int or (type(value) is float and value.is_integer())) and abs(value) > 9007199254740991:
            raise ContractError("INTEGER_OUT_OF_RANGE")
        if not math.isfinite(value):
            raise ContractError("NONFINITE_NUMBER")
    elif value is not None and type(value) not in (str, bool):
        raise ContractError("INVALID_JSON_VALUE")


def _unique(items, key, path):
    values = [item[key] for item in items]
    if len(set(values)) != len(values):
        raise ContractError("DUPLICATE_ID", path)


def validate_message(message, supported_extensions=()):
    json_values(message)
    schema = parse_json(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    if not Draft202012Validator(schema).is_valid(message):
        raise ContractError("SCHEMA_INVALID")
    extensions = message.get("extensions", [])
    _unique(extensions, "id", "/extensions")
    for extension in extensions:
        if extension["required"] and (extension["id"], extension["version"]) not in supported_extensions:
            raise ContractError("UNSUPPORTED_EXTENSION", "/extensions")
    configuration = message.get("configuration", message.get("effective_configuration", message.get("defaults")))
    if configuration is not None:
        _unique(configuration["objectives"], "id", "/configuration/objectives")
    for field in ("metrics", "constraints", "objectives"):
        items = message.get(field, [])
        if items:
            _unique(items, "id", "/" + field)
    if message["kind"] == "result" and message["request_id"] != message["provenance"]["request_id"]:
        raise ContractError("REQUEST_MISMATCH", "/provenance/request_id")
    if message["kind"] == "capability":
        def local_refs(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"$ref", "$dynamicRef"} and (not isinstance(child, str) or not child.startswith("#")):
                        raise ContractError("EXTERNAL_SCHEMA_REFERENCE")
                    local_refs(child)
            elif isinstance(value, list):
                for child in value:
                    local_refs(child)
        local_refs(message["configuration_schema"])
        Draft202012Validator.check_schema(message["configuration_schema"])
        if not Draft202012Validator(message["configuration_schema"]).is_valid(message["defaults"]):
            raise ContractError("INVALID_DEFAULT_CONFIGURATION", "/defaults")
    return message
