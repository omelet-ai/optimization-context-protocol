"""Strict JSON and packaged schema validation; no workspace or network lookup."""

from functools import lru_cache
from importlib.resources import files
import json
import math
import re

from jsonschema import Draft202012Validator


class OCPError(ValueError):
    def __init__(self, code, path="", message="Request cannot be processed", retryable=False):
        super().__init__(message)
        self.code, self.path, self.message, self.retryable = code, path, message, retryable


def strict_json(value):
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise OCPError("INVALID_REQUEST", message="Object keys must be strings")
        for child in value.values():
            strict_json(child)
    elif type(value) is list:
        for child in value:
            strict_json(child)
    elif type(value) is int:
        if abs(value) > 9007199254740991:
            raise OCPError("INVALID_REQUEST", message="Integer exceeds safe interchange range")
    elif type(value) is float:
        if not math.isfinite(value) or (value.is_integer() and abs(value) > 9007199254740991):
            raise OCPError("INVALID_REQUEST", message="Non-finite JSON number")
    elif value is not None and type(value) not in (bool, str):
        raise OCPError("INVALID_REQUEST", message="Non-JSON value")


def parse_json(text):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise OCPError("INVALID_REQUEST", message="Duplicate JSON key")
            output[key] = value
        return output
    def invalid(value):
        raise OCPError("INVALID_REQUEST", message="Non-finite JSON number")
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, OCPError):
            raise
        raise OCPError("INVALID_REQUEST", message="Invalid JSON") from exc
    strict_json(value)
    return value


@lru_cache(maxsize=16)
def schema(name):
    return parse_json(files("ocp_candidate").joinpath("schemas", name + "-0.1.schema.json").read_text())


@lru_cache(maxsize=16)
def validator(name):
    data = schema(name)
    Draft202012Validator.check_schema(data)
    return Draft202012Validator(data)


def validate(name, value, code="INVALID_REQUEST"):
    strict_json(value)
    error = next(validator(name).iter_errors(value), None)
    if error is not None:
        # Core is a tagged union. Report the declared kind's failure, not
        # unrelated required fields from other envelope kinds.
        if name == "core" and error.validator == "oneOf" and isinstance(value, dict):
            document = schema(name)
            for index, branch in enumerate(document['oneOf']):
                target = document['$defs'][branch['$ref'].removeprefix('#/$defs/')]
                if target.get('properties', {}).get('kind', {}).get('const') == value.get('kind'):
                    error = next((child for child in error.context
                                  if list(child.absolute_schema_path)[:2] == ['oneOf', index]), error)
                    break
        parts = list(error.absolute_path)
        message = "Value does not match " + name + " contract"
        # Identify the field without echoing user-supplied values in messages.
        # Keep the existing error code and envelope for existing consumers.
        if error.validator == "required" and isinstance(error.instance, dict):
            missing = next(key for key in error.validator_value if key not in error.instance)
            parts.append(missing)
            message = "Required field is missing; request its value before solving"
        elif error.validator == "additionalProperties" and error.validator_value is False:
            properties = error.schema.get("properties", {})
            patterns = error.schema.get("patternProperties", {})
            extra = sorted(key for key in error.instance
                           if key not in properties and not any(re.search(pattern, key) for pattern in patterns))
            if extra:
                parts.append(extra[0])
                message = "Field is not supported by this contract; preserve the requirement and select a supporting profile"
        elif error.validator == "type":
            message = "Value has the wrong type; consult the declared field schema"
        elif error.validator in ("const", "enum"):
            message = "Value is not one of the declared choices; consult the field schema"
        elif error.validator in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
            message = "Value is outside the declared numeric bounds"
        elif error.validator in ("minItems", "maxItems"):
            message = "Item count is outside the declared profile limits"
        path = "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1") for x in parts)
        raise OCPError(code, path, message)


def envelope(value):
    validate("core", value)
    for field in ("metrics", "constraints", "objectives"):
        entries=value.get(field, [])
        if entries and all(isinstance(item,dict) and "id" in item for item in entries):
            ids=[item["id"] for item in entries]
            if len(ids)!=len(set(ids)):
                raise OCPError("INVALID_RESPONSE", "/"+field, "Duplicate identity")
    seen = set()
    for ext in value.get("extensions", []):
        if ext["id"] in seen:
            raise OCPError("INVALID_REQUEST", "/extensions", "Duplicate extension ID")
        seen.add(ext["id"])
        if ext["required"]:
            raise OCPError("UNSUPPORTED_EXTENSION", "/extensions", "Required extension is not supported")
    configuration = value.get("configuration", value.get("effective_configuration", value.get("defaults")))
    if configuration:
        ids = [x["id"] for x in configuration["objectives"]]
        if len(ids) != len(set(ids)):
            raise OCPError("INVALID_REQUEST", "/configuration/objectives", "Duplicate objective ID")
    if value["kind"] == "result" and value["request_id"] != value["provenance"]["request_id"]:
        raise OCPError("INVALID_RESPONSE", "/provenance/request_id", "Response identity mismatch")


def failure(request_id, error):
    if not isinstance(request_id,str) or not 0 < len(request_id) <= 128:
        request_id=None
    return {"core_version":"0.1.0","kind":"failure","request_id":request_id,
            "error":{"code":error.code,"message":error.message,"retryable":error.retryable,
                     "issues":[{"code":error.code,"path":error.path,"message":error.message}]}}
