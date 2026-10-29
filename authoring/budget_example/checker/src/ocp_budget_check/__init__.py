"""Independent subset enumeration, importing only schemas and conformance APIs."""
from itertools import combinations
from jsonschema import Draft202012Validator
from ocp_budget_profile import REFERENCE, schema
from conformance.assessment import builtin_checkers
from conformance.core_contract import ContractError, validate_message


def shape(kind, value):
    if not Draft202012Validator(schema(kind)).is_valid(value): raise ContractError('INVALID_' + kind.upper())


def optimum(problem):
    best = 0
    for size in range(len(problem['items']) + 1):
        for items in combinations(problem['items'], size):
            if sum(i['cost'] for i in items) <= problem['capacity']:
                best = max(best, sum(i['benefit'] for i in items))
    return best


def verify(request, response):
    validate_message(request); validate_message(response)
    if request['kind'] != 'request' or response['kind'] != 'result': raise ContractError('INVALID_TRANSCRIPT')
    if request['domain_profile'] != REFERENCE or request['execution_profile'] != {'id': 'execution.sync', 'version': '0.1.0'}:
        raise ContractError('VERSION_MISMATCH')
    for key in ['request_id', 'capability', 'domain_profile', 'execution_profile']:
        if request[key] != response[key]: raise ContractError('RESULT_MISMATCH')
    shape('configuration', request['configuration'])
    if request['configuration'] != response['effective_configuration']: raise ContractError('RESULT_MISMATCH')
    if not 1 <= request['budget']['time_limit_ms'] <= 5000: raise ContractError('BUDGET_OUT_OF_SCOPE')
    problem = request['input']; shape('input', problem)
    ids = [i['id'] for i in problem['items']]
    if len(set(ids)) != len(ids): raise ContractError('DUPLICATE_ID')
    measured = None
    if response['solution'] is not None:
        shape('solution', response['solution'])
        selected = response['solution']['selected']
        if set(selected) - set(ids): raise ContractError('UNKNOWN_ITEM')
        picked = [i for i in problem['items'] if i['id'] in selected]
        used = sum(i['cost'] for i in picked)
        benefit = sum(i['benefit'] for i in picked)
        if used > problem['capacity']: raise ContractError('CAPACITY_VIOLATION')
        measured = {'feasible': True, 'benefit': benefit, 'used_capacity': used}
        if len(response['metrics']) != 1 or len(response['constraints']) != 2: raise ContractError('EVALUATION_MISMATCH')
        metric = response['metrics'][0]
        expected = {'id': 'total_benefit', 'role': 'optimized', 'definition': REFERENCE['id'] + '.total_benefit.v1',
                    'unit': 'benefit_unit', 'status': 'evaluated', 'value': benefit, 'reason': None}
        if any(metric[k] != v for k, v in expected.items()): raise ContractError('EVALUATION_MISMATCH')
        if {c['id'] for c in response['constraints']} != {'capacity', 'unique_selection'}: raise ContractError('EVALUATION_MISMATCH')
        for constraint in response['constraints']:
            expected = {'role': 'enforced', 'definition': REFERENCE['id'] + '.' + constraint['id'] + '.v1',
                        'unit': 'credit' if constraint['id'] == 'capacity' else 'count',
                        'status': 'evaluated', 'violation': 0, 'satisfied': True, 'reason': None}
            if any(constraint[k] != v for k, v in expected.items()): raise ContractError('EVALUATION_MISMATCH')
    elif response['metrics'] or response['constraints']: raise ContractError('EVALUATION_WITHOUT_SOLUTION')
    if response['status'] == 'infeasible':
        raise ContractError('UNVERIFIED_PROOF')  # Empty subset is always a witness.
    if response['status'] == 'optimal':
        best = optimum(problem)
        expected = {'claim': 'optimal', 'method': 'bounded-knapsack-dp', 'scope': REFERENCE['id'] + ':0.1.0', 'evidence': {'objective': best}}
        evidence = response['proof']['evidence']
        if (not isinstance(evidence, dict) or type(evidence.get('objective')) not in (int, float)
                or response['proof'] != expected or measured is None or measured['benefit'] != best):
            raise ContractError('UNVERIFIED_PROOF')
    return measured


def registry():
    registered = builtin_checkers()
    registered.register(REFERENCE, verify, scope={
        'solution': 'At most 12 optional items; unique known IDs, integer credit capacity and benefit recomputation.',
        'proof': 'Independent enumeration of every subset within the declared 12-item limit.'},
        metric_id='total_benefit', value_key='benefit', identity={'id': 'ocp-budget-checker-example', 'version': '0.1.0'})
    return registered
