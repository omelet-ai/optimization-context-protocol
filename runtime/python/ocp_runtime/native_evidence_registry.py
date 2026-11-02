"""Explicit host-selected evidence handlers; no automatic imports or discovery."""
from copy import deepcopy
from dataclasses import dataclass, replace
from importlib import import_module
import re

from jsonschema import Draft202012Validator
from conformance.assessment import digest
from conformance.core_contract import ContractError

FEATURE_VERSION = '0.5.0'
REGISTRY_API = '0.1.0'
IDENTITY_SCHEMA = {'type': 'array', 'maxItems': 0}


@dataclass(frozen=True)
class EvidenceHandler:
    profile: dict
    identity: dict
    requirements_schema: dict
    mapping_supported: bool
    validate: object
    prepare: object
    verify_preparation: object
    mapping_facts: object
    solution_facts: object
    verify_solution_facts: object

    def description(self):
        return {'api_version': REGISTRY_API, 'feature_version': FEATURE_VERSION,
                'profile': deepcopy(self.profile), 'handler': deepcopy(self.identity),
                'requirements_schema_sha256': digest(self.requirements_schema),
                'mapping_supported': self.mapping_supported}


class EvidenceRegistry:
    """Registrations are trusted installed code, not provider certification."""
    def __init__(self):
        self._handlers = {}
        self._frozen = False

    def register(self, profile, *, feature_version, identity, requirements_schema,
                 mapping_supported, validate, prepare, verify_preparation, mapping_facts,
                 solution_facts, verify_solution_facts):
        if self._frozen:
            raise ContractError('EVIDENCE_REGISTRY_FROZEN')
        if feature_version != FEATURE_VERSION:
            raise ContractError('EVIDENCE_VERSION_MISMATCH')
        for reference in (profile, identity):
            if (not isinstance(reference, dict) or set(reference) != {'id', 'version'} or
                    any(not isinstance(v, str) or not v for v in reference.values())):
                raise ContractError('INVALID_EVIDENCE_REGISTRATION')
        functions = (validate, prepare, verify_preparation, mapping_facts, solution_facts, verify_solution_facts)
        if type(mapping_supported) is not bool or not all(callable(f) for f in functions):
            raise ContractError('INVALID_EVIDENCE_REGISTRATION')
        # Reference-free requirement schemas are self-contained in MCP context.
        def check(value):
            if isinstance(value, dict):
                if '$ref' in value or '$dynamicRef' in value:
                    raise ContractError('EVIDENCE_SCHEMA_REFERENCE_UNSUPPORTED')
                for child in value.values(): check(child)
            elif isinstance(value, list):
                for child in value: check(child)
        try:
            check(requirements_schema)
            Draft202012Validator.check_schema(requirements_schema)
            if not isinstance(requirements_schema, dict) or requirements_schema.get('type') != 'array':
                raise ContractError('INVALID_EVIDENCE_SCHEMA')
            digest(requirements_schema)
        except ContractError:
            raise
        except Exception:
            raise ContractError('INVALID_EVIDENCE_SCHEMA') from None
        key = (profile['id'], profile['version'], feature_version)
        if key in self._handlers:
            raise ContractError('DUPLICATE_EVIDENCE_HANDLER')
        self._handlers[key] = EvidenceHandler(deepcopy(profile), deepcopy(identity),
            deepcopy(requirements_schema), mapping_supported, *functions)

    def resolve(self, profile):
        if (not isinstance(profile, dict) or
                any(not isinstance(profile.get(k), str) for k in ('id', 'version'))):
            return None
        entry = self._handlers.get((profile.get('id'), profile.get('version'), FEATURE_VERSION))
        if entry is None:
            return None
        return replace(entry, profile=deepcopy(entry.profile), identity=deepcopy(entry.identity),
                       requirements_schema=deepcopy(entry.requirements_schema))

    def snapshot(self):
        frozen = EvidenceRegistry()
        frozen._handlers = {key: self.resolve(entry.profile) for key, entry in self._handlers.items()}
        frozen._frozen = True
        return frozen


def invoke(function, *arguments):
    """Isolate callback data; reject mutation, non-JSON output and callback failure."""
    values = deepcopy(list(arguments))
    before = digest(values)
    try:
        result = function(*values)
        if digest(values) != before:
            raise ContractError('EVIDENCE_HANDLER_MUTATED_INPUT')
        # Prepare may return a pair, normalized to a JSON array for checking.
        digest(list(result) if isinstance(result, tuple) else result)
        return deepcopy(result)
    except ContractError:
        raise
    except Exception:
        raise ContractError('EVIDENCE_HANDLER_FAILED') from None


def check_preparation(proof, original, requirements, prepared):
    expected = {'original_request_sha256': digest(original), 'requirements_sha256': digest(requirements),
                'prepared_request_sha256': digest(prepared)}
    if (not isinstance(proof, dict) or proof.get('status') != 'PASS' or
            any(proof.get(key) != value for key, value in expected.items()) or
            not isinstance(proof.get('checker'), dict) or
            any(not isinstance(proof['checker'].get(k), str) or not proof['checker'][k] for k in ('id', 'version'))):
        raise ContractError('INVALID_PREPARATION_REPORT')


def builtin_evidence():
    from .native_evidence_worker import register
    registry = EvidenceRegistry()
    register(registry)
    return registry


def load_evidence_registry(factory=None):
    if factory is None:
        return builtin_evidence()
    if not isinstance(factory, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*', factory):
        raise ContractError('INVALID_EVIDENCE_FACTORY')
    module, function = factory.split(':')
    try:
        registry = getattr(import_module(module), function)()
    except Exception as error:
        raise ContractError('INVALID_EVIDENCE_FACTORY') from error
    if not isinstance(registry, EvidenceRegistry):
        raise ContractError('INVALID_EVIDENCE_FACTORY')
    return registry
