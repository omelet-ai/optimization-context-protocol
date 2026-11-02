"""Finite input equivalence checks; no mapper, provider or solver imports."""
from copy import deepcopy
from itertools import product

from jsonschema import Draft202012Validator

from .assessment import digest
from .core_contract import ContractError, validate_message
from .planning import integral_numbers, shape
from . import worker

VERSION = '0.1.0'
WORKER = {'id': 'worker.scheduling', 'version': '0.1.0'}
IDENTIFIER = {'type': 'string', 'minLength': 1, 'maxLength': 64}
BREAK_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['worker_id', 'start', 'end'],
    'properties': {'worker_id': IDENTIFIER, 'start': {'type': 'integer', 'minimum': 0, 'maximum': 10080},
                   'end': {'type': 'integer', 'minimum': 1, 'maximum': 10080}}}
REQUIREMENTS_SCHEMA = {'type': 'array', 'maxItems': 1, 'items': {'oneOf': [
    {'type': 'object', 'additionalProperties': False,
     'required': ['id', 'kind', 'enforcement', 'breaks'],
     'properties': {'id': IDENTIFIER, 'kind': {'const': 'fixed_breaks'},
                    'enforcement': {'const': 'hard'},
                    'breaks': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': BREAK_SCHEMA}}},
    {'type': 'object', 'additionalProperties': False,
     'required': ['id', 'kind', 'enforcement', 'worker_rates', 'unit'],
     'properties': {'id': IDENTIFIER, 'kind': {'const': 'outside_availability_cost'},
                    'enforcement': {'const': 'soft'}, 'unit': {'const': 'cost_unit_per_minute'},
                    'worker_rates': {'type': 'object', 'minProperties': 1, 'maxProperties': 4,
                                     'propertyNames': IDENTIFIER,
                                     'additionalProperties': {'type': 'integer', 'minimum': 0, 'maximum': 100000}}}}
]}}


def validate_requirements(original, requirements):
    if isinstance(requirements, list) and len(requirements) > 1:
        raise ContractError('UNSUPPORTED_REQUIREMENT_COMBINATION')
    if isinstance(requirements, list) and requirements and isinstance(requirements[0], dict):
        if requirements[0].get('kind') not in ('fixed_breaks', 'outside_availability_cost'):
            raise ContractError('UNSUPPORTED_REQUIREMENT')
    if not Draft202012Validator(REQUIREMENTS_SCHEMA).is_valid(requirements):
        raise ContractError('INVALID_REQUIREMENT')
    validate_message(original)
    if original['kind'] != 'request':
        raise ContractError('INVALID_REQUEST')
    if not requirements:
        return
    if original['domain_profile'] != WORKER:
        raise ContractError('UNSUPPORTED_MAPPING_PROFILE')
    worker.validate_problem(original['input'])
    shape(worker.STEM, 'configuration', original['configuration'])
    ids = {w['id'] for w in original['input']['workers']}
    requirement = requirements[0]
    if requirement['kind'] == 'fixed_breaks':
        for interval in requirement['breaks']:
            if interval['worker_id'] not in ids or interval['start'] >= interval['end']:
                raise ContractError('INVALID_BREAK')
    elif set(requirement['worker_rates']) - ids:
        raise ContractError('UNKNOWN_WORKER')


def _original_value(problem, requirement, owners, outside_costs):
    """Direct interpretation of the declared requirement, without transforming it."""
    workers = {w['id']: w for w in problem['workers']}
    spans = {w: [] for w in workers}
    cost = 0
    rates = requirement.get('worker_rates', {})
    for task, owner in zip(problem['tasks'], owners):
        w = workers[owner]
        a, b = task['start'], task['end']
        if owner not in task['eligible_workers']:
            return None
        if any(a < end and start < b for start, end in spans[owner]):
            return None
        spans[owner].append((a, b))
        cost += task['costs'][owner]
        if owner in rates:
            cost += outside_costs[task['id'], owner]
        elif not any(x['start'] <= a and b <= x['end'] for x in w['availability']):
            return None
        if any(br['worker_id'] == owner and a < br['end'] and br['start'] < b
               for br in requirement.get('breaks', [])):
            return None
    if any(sum(b-a for a, b in spans[wid]) > w['max_minutes'] for wid, w in workers.items()):
        return None
    return cost


def verify_preparation(original, requirements, prepared):
    """Raise on mismatch; compare every possible assignment for this input.

    Identity mappings do not establish completeness of captured requirements.
    A mathematical check does not interpret the host's natural-language text.
    """
    validate_requirements(original, requirements)
    validate_message(prepared)
    if not requirements:
        if digest(original) != digest(prepared):
            raise ContractError('PREPARATION_MISMATCH')
        count, feasible, method = 0, None, 'identity'
    else:
        left, right = deepcopy(original), deepcopy(prepared)
        before, after = left.pop('input'), right.pop('input')
        if digest(left) != digest(right):
            raise ContractError('PREPARATION_MISMATCH')
        worker.validate_problem(after)
        # Preserve entity identity and order. Eligibility/cost/availability
        # transformations are checked by their observable finite semantics.
        for entity in ('tasks', 'workers'):
            if [x['id'] for x in before[entity]] != [x['id'] for x in after[entity]]:
                raise ContractError('PREPARATION_MISMATCH')
        kind = requirements[0]['kind']
        for field in ('time_unit', 'cost_unit'):
            if before[field] != after[field]:
                raise ContractError('PREPARATION_MISMATCH')
        for entity, allowed in [('tasks', {'eligible_workers', 'costs'} if kind == 'fixed_breaks' else {'costs'}),
                                ('workers', set() if kind == 'fixed_breaks' else {'availability'})]:
            for a, b in zip(before[entity], after[entity]):
                if {k: v for k, v in a.items() if k not in allowed} != {k: v for k, v in b.items() if k not in allowed}:
                    raise ContractError('PREPARATION_MISMATCH')
        before, after, req = integral_numbers(before), integral_numbers(after), integral_numbers(requirements[0])
        # Count original minutes once per pair, independently of the mapper's
        # interval-intersection arithmetic, rather than once per assignment.
        outside_costs = {(t['id'], w['id']): rate * sum(
            not any(x['start'] <= minute < x['end'] for x in w['availability'])
            for minute in range(t['start'], t['end']))
            for t in before['tasks'] for w in before['workers']
            for rate in [req.get('worker_rates', {}).get(w['id'])] if rate is not None}
        count = feasible = 0
        for owners in product([w['id'] for w in before['workers']], repeat=len(before['tasks'])):
            count += 1
            expected = _original_value(before, req, owners, outside_costs)
            try:
                measured = worker._measure(after, [(t['id'], w) for t, w in zip(after['tasks'], owners)])
                actual = measured['total_cost'] if measured['feasible'] else None
            except ContractError as error:
                if error.code != 'INELIGIBLE_ASSIGNMENT':
                    raise
                actual = None
            if expected != actual:
                raise ContractError('PREPARATION_MISMATCH')
            feasible += expected is not None
        method = 'all-worker-assignments'
    return {'status': 'PASS', 'checker': {'id': 'ocp-preparation-checker', 'version': VERSION},
            'method': method, 'assignments_checked': count, 'feasible_assignments': feasible,
            'original_request_sha256': digest(original), 'requirements_sha256': digest(requirements),
            'prepared_request_sha256': digest(prepared),
            'scope': 'Declared structured requirements for this finite input only; source text interpretation is NOT_CHECKED.'}
