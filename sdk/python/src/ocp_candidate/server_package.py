"""Domain-neutral server package descriptor, draft 0.1.

Only local JSON Schema references are supported by this portable descriptor.
Connectors and domain code are installed separately; metadata cannot import code.
"""
from copy import deepcopy
from importlib.resources import files
import re

from jsonschema import Draft202012Validator
from .fingerprint import fingerprint

VERSION = "0.1.0-draft.2"


class PackageError(ValueError):
    def __init__(self, code, path=""):
        super().__init__(code + (": " + path if path else ""))
        self.code, self.path = code, path


def _check(schema, value, path):
    error = next(Draft202012Validator(schema).iter_errors(value), None)
    if error is not None:
        raise PackageError("SCHEMA_INVALID", path + "/" + "/".join(map(str, error.absolute_path)))


def tokens(pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")) or re.search(r"~(?![01])", pointer):
        raise PackageError("POINTER_INVALID", str(pointer))
    return [] if not pointer else [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]


def at(document, pointer):
    value = document
    try:
        for token in tokens(pointer):
            if isinstance(value, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", token):
                    raise KeyError(token)
                value = value[int(token)]
            else:
                value = value[token]
        return value
    except (KeyError, IndexError, TypeError):
        raise PackageError("POINTER_MISSING", pointer) from None


def schema_at(schema, pointer):
    parts = tokens(pointer)

    def resolve(value, position, seen):
        seen = set(seen)
        while isinstance(value, dict) and "$ref" in value:
            ref = value["$ref"]
            marker = (ref, position)
            if marker in seen:
                raise PackageError("SCHEMA_REFERENCE_CYCLE", pointer)
            if not isinstance(ref, str) or not ref.startswith('#/'):
                raise PackageError("EXTERNAL_SCHEMA_REFERENCE_UNSUPPORTED", pointer)
            seen.add(marker)
            value = at(schema, ref[1:])
        return value, seen

    def descend(value, position, seen):
        value, seen = resolve(value, position, seen)
        if position == len(parts):
            return value
        if not isinstance(value, dict):
            raise PackageError("POINTER_MISSING", pointer)
        token = parts[position]
        if token in value.get("properties", {}):
            return descend(value['properties'][token], position + 1, seen)
        elif value.get("type") == "array" and re.fullmatch(r"0|[1-9][0-9]*", token):
            index = int(token)
            prefixes = value.get('prefixItems', [])
            child = prefixes[index] if index < len(prefixes) else value.get('items', {})
            return descend(child, position + 1, seen)
        # A pointer may exist only in a successful result branch. This is a
        # structural lookup, not a claim that every value has that field: the
        # complete input schema is still validated and metric reads may be null.
        alternatives = value.get('oneOf', value.get('anyOf', []))
        found = []
        for branch in alternatives:
            try:
                field = descend(branch, position, seen)
            except PackageError as error:
                if error.code != 'POINTER_MISSING':
                    raise
            else:
                if not any(fingerprint(field) == fingerprint(existing) for existing in found):
                    found.append(field)
        if not found:
            raise PackageError('POINTER_MISSING', pointer)
        if len(found) == 1:
            return found[0]
        result = {'anyOf': found}
        common_type = found[0].get('type') if isinstance(found[0], dict) else None
        if common_type and all(isinstance(f, dict) and f.get('type') == common_type for f in found):
            result['type'] = common_type
        return result

    return descend(schema, 0, set())


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def require_reference(expected, actual):
    """Never equate different version or digest encoding namespaces."""
    if expected != actual:
        raise PackageError("REFERENCE_MISMATCH")


def _local_schema(schema, name):
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise PackageError("SCHEMA_DEFINITION_INVALID", name) from error
    for node in _walk(schema):
        if "$id" in node and node is not schema:
            raise PackageError("NESTED_SCHEMA_ID_UNSUPPORTED", name)
        for key in ("$ref", "$dynamicRef"):
            if key in node and (not isinstance(node[key], str) or not node[key].startswith("#/")):
                raise PackageError("EXTERNAL_SCHEMA_REFERENCE_UNSUPPORTED", name)
            if key in node:
                at(schema, node[key][1:])


def lint_package(document, *, descriptor_schema=None, api_contract=None, supported_extensions=()):
    fingerprint(document)  # bounded JSON, finite portable numbers and valid Unicode
    if descriptor_schema is None:
        import json
        descriptor_schema = json.loads(files("ocp_candidate").joinpath("schemas", "server-package-0.1.schema.json").read_text())
    _check(descriptor_schema, document, "")
    if set(document["required_extensions"]) - set(supported_extensions):
        raise PackageError("REQUIRED_EXTENSION_UNSUPPORTED")
    if not set(document["required_extensions"]).issubset(document["extensions"]):
        raise PackageError("REQUIRED_EXTENSION_MISSING")
    if document["default_locale"] not in document["localizations"]:
        raise PackageError("DEFAULT_LOCALE_MISSING")
    schemas = document["schemas"]
    api = document["api"]
    for kind in ("input", "configuration", "result"):
        if api[kind + "_schema"] not in schemas:
            raise PackageError("SCHEMA_REFERENCE_MISSING", kind)
    for name, schema in schemas.items():
        _local_schema(schema, name)
    # Only compiled-in validators are executed. Unknown optional extensions stay
    # opaque, and naming a supported extension never imports metadata paths.
    if "ocp.operations" in document["extensions"]:
        from .operations import operations
        operations(document)
    for collection in ("bindings", "metrics", "input_formats", "playbooks"):
        ids = [item["id"] for item in document[collection]]
        if len(set(ids)) != len(ids):
            raise PackageError("DUPLICATE_ID", collection)
    for collection in ("objectives", "constraints"):
        ids = [item["id"] for item in document["capabilities"][collection]]
        if len(set(ids)) != len(ids):
            raise PackageError("DUPLICATE_ID", collection)
    config_schema = schemas[api["configuration_schema"]]
    # Defaults may be partial. Validate each provided value, not missing required choices.
    partial = deepcopy(config_schema)
    if isinstance(partial, dict):
        partial.pop("required", None)
    _check(partial, document["configuration_defaults"], "/configuration_defaults")
    units = document["units"]
    semantic_items = document["metrics"] + document["capabilities"]["objectives"] + document["capabilities"]["constraints"]
    for item in semantic_items:
        if item.get("unit") is not None and item["unit"] not in units:
            raise PackageError("UNIT_UNDECLARED", item["id"])
    bindings = {b["id"]: b for b in document["bindings"]}
    for binding in bindings.values():
        source = schemas[api[binding["target"] + "_schema"]]
        field = schema_at(source, binding["pointer"])
        if binding["operation"] == "select_by_id" and (not isinstance(field, dict) or field.get("type") != "array"):
            raise PackageError("SELECTION_REQUIRES_ARRAY", binding["id"])
        _local_schema(binding["value_schema"], "binding/" + binding["id"])
    for metric in document["metrics"]:
        schema_at(schemas[api["result_schema"]], metric["pointer"])
    for rule in document["configuration_rules"]:
        schema_at(config_schema, rule["pointer"])
    for item in document["capabilities"]["objectives"]:
        if item.get("weight_binding") is not None and item["weight_binding"] not in bindings:
            raise PackageError("BINDING_MISSING", item["id"])
    metrics = {m["id"] for m in document["metrics"]}
    for playbook in document["playbooks"]:
        if set(playbook["binding_ids"]) - set(bindings) or set(playbook["metric_ids"]) - metrics:
            raise PackageError("PLAYBOOK_REFERENCE_MISSING", playbook["id"])
        for preserved in playbook["preserve"]:
            schema_at(schemas[api[preserved["target"] + "_schema"]], preserved["pointer"])
    if api_contract is not None:
        for key, expected in (("api", api), ("schemas", schemas), ("capabilities", document["capabilities"])):
            require_reference(expected, api_contract.get(key))
    return {"status": "PASS", "scope": "descriptor_structure_and_semantics",
            "api_agreement_checked": api_contract is not None, "fingerprint": fingerprint(document)}


def validate_request(document, input_value, configuration):
    fingerprint(input_value); fingerprint(configuration)
    if not isinstance(configuration, dict):
        raise PackageError("SCHEMA_INVALID", "/configuration")
    api, schemas = document["api"], document["schemas"]
    effective = deepcopy(document["configuration_defaults"])
    # Top-level explicit values replace defaults; no hidden recursive merging.
    effective.update(deepcopy(configuration))
    _check(schemas[api["input_schema"]], input_value, "/input")
    _check(schemas[api["configuration_schema"]], effective, "/configuration")
    for rule in document["configuration_rules"]:
        value = at(effective, rule["pointer"])
        if rule["kind"] == "allowed_set":
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value) or len(set(value)) != len(value) or not any(set(value) == set(v) for v in rule["values"]):
                raise PackageError("CONFIGURATION_COMBINATION_UNSUPPORTED", rule["pointer"])
    return effective
