"""Strict JSON and packaged schema validation; no workspace or network lookup."""

from functools import lru_cache
from importlib.resources import files
import json
import math

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
        path = "/" + "/".join(str(x).replace("~", "~0").replace("/", "~1") for x in error.absolute_path)
        raise OCPError(code, path, "Value does not match " + name + " contract")


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
