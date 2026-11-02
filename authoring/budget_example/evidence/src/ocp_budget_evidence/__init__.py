"""Explicit example registration; no engine imports, discovery or execution."""
from copy import deepcopy
from ocp_budget_profile import REFERENCE
from conformance.core_contract import ContractError
from conformance.preparation import validate_requirements, verify_preparation
from ocp_runtime.native_evidence_registry import IDENTITY_SCHEMA, builtin_evidence
from .verify import verify_details

FEATURE_VERSION = '0.5.0'  # The version this extension was implemented and checked against.


def validate(request, requirements):
    if request.get('domain_profile') != REFERENCE:
        raise ContractError('UNSUPPORTED_MAPPING_PROFILE')
    if requirements:
        raise ContractError('UNSUPPORTED_REQUIREMENT')
    validate_requirements(request, requirements)


def prepare(request, requirements):
    validate(request, requirements)
    return deepcopy(request), {'id': 'identity', 'version': FEATURE_VERSION}


def mapping_facts(request, requirements, proof):
    return {'method': 'identity', 'request_preserved': True, 'requirements_count': len(requirements)}


def solution_facts(request, result, objective, preparation):
    if result['solution'] is None:
        return None
    data = request['input']
    selected = set(result['solution']['selected'])
    items = [deepcopy(item) for item in data['items'] if item['id'] in selected]
    used = sum(item['cost'] for item in items)
    return {'items': items, 'used_capacity': used, 'remaining_capacity': data['capacity']-used,
            'total_benefit': sum(item['benefit'] for item in items),
            'cost_unit': data['cost_unit'], 'benefit_unit': data['benefit_unit']}


def registry():
    registered = builtin_evidence()
    registered.register(REFERENCE, feature_version=FEATURE_VERSION,
        identity={'id': 'ocp-budget-evidence-example', 'version': '0.1.0'},
        requirements_schema=IDENTITY_SCHEMA, mapping_supported=False,
        validate=validate, prepare=prepare, verify_preparation=verify_preparation,
        mapping_facts=mapping_facts, solution_facts=solution_facts, verify_solution_facts=verify_details)
    return registered
