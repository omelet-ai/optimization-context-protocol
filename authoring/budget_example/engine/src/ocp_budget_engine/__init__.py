"""An independently installed maximization domain using the five Core ports."""
from copy import deepcopy
import time
from jsonschema import Draft202012Validator
from ocp_candidate.contract import OCPError, envelope, failure
from ocp_budget_profile import REFERENCE, SEMANTICS, schema
from .solver import solve

CAPABILITY = {'id': 'example.budget-selection.dp', 'version': '0.1.0'}
SYNC = {'id': 'execution.sync', 'version': '0.1.0'}


def shape(kind, value):
    if not Draft202012Validator(schema(kind)).is_valid(value):
        raise OCPError('UNSUPPORTED_CONFIGURATION' if kind == 'configuration' else 'INVALID_' + kind.upper())


def configuration():
    return schema('configuration')['const']


def measurements(problem, solution):
    shape('solution', solution)
    items = {v['id']: v for v in problem['items']}
    if set(solution['selected']) - items.keys(): raise OCPError('UNKNOWN_ITEM')
    cost = sum(items[k]['cost'] for k in solution['selected'])
    benefit = sum(items[k]['benefit'] for k in solution['selected'])
    metrics = [{'id': 'total_benefit', 'role': 'optimized', 'definition': REFERENCE['id'] + '.total_benefit.v1',
                'unit': 'benefit_unit', 'source': 'engine', 'status': 'evaluated', 'value': benefit, 'reason': None}]
    violations = {'capacity': max(0, cost - problem['capacity']), 'unique_selection': 0}
    constraints = [{'id': key, 'role': 'enforced', 'definition': REFERENCE['id'] + '.' + key + '.v1',
                    'unit': 'credit' if key == 'capacity' else 'count', 'source': 'engine', 'status': 'evaluated',
                    'violation': value, 'satisfied': value == 0, 'reason': None} for key, value in violations.items()]
    return metrics, constraints


class Provider:
    def __init__(self, *, clock=time.monotonic): self.clock = clock

    def describe(self):
        return {'core_version': '0.1.0', 'kind': 'capability', 'capability': deepcopy(CAPABILITY), 'domain_profile': deepcopy(REFERENCE),
                'execution_profiles': [deepcopy(SYNC)], 'bindings': [{'id': 'binding.in_process', 'version': '0.1.0'}],
                'environments': [{'id': 'environment.local', 'version': '0.1.0'}],
                'objectives': [{'id': 'total_benefit', 'direction': 'maximize', 'role': 'optimized',
                                'definition': REFERENCE['id'] + '.total_benefit.v1', 'unit': 'benefit_unit'}],
                'constraints': [{'id': cid, 'kind': 'hard', 'role': 'enforced', 'definition': REFERENCE['id'] + '.' + cid + '.v1',
                                 'unit': 'credit' if cid == 'capacity' else 'count'} for cid in configuration()['constraints']],
                'configuration_schema': schema('configuration'), 'input_schema_id': schema('input')['$id'],
                'solution_schema_id': schema('solution')['$id'], 'defaults': configuration(), 'limitations': list(SEMANTICS)}

    def requirements(self, selected):
        try:
            shape('configuration', selected)
            return {'core_version': '0.1.0', 'kind': 'requirements', 'capability': deepcopy(CAPABILITY), 'domain_profile': deepcopy(REFERENCE),
                    'effective_configuration': configuration(), 'input_schema_id': schema('input')['$id'],
                    'required_fields': [{'path': '/items/*/cost', 'reason': 'Cost of selecting each item; * means every array item', 'unit': 'credit'},
                                        {'path': '/items/*/benefit', 'reason': 'Benefit of selecting each item; * means every array item', 'unit': 'benefit_unit'},
                                        {'path': '/capacity', 'reason': 'Total available budget', 'unit': 'credit'}]}
        except OCPError as error: return failure(None, error)

    def _check(self, request):
        envelope(request)
        if request['kind'] != 'request': raise OCPError('INVALID_REQUEST')
        if request['domain_profile'] != REFERENCE or request['capability'] != CAPABILITY or request['execution_profile'] != SYNC:
            raise OCPError('VERSION_MISMATCH')
        shape('configuration', request['configuration']); shape('input', request['input'])
        if not 1 <= request['budget']['time_limit_ms'] <= 5000: raise OCPError('LIMIT_EXCEEDED')
        ids = [i['id'] for i in request['input']['items']]
        if len(set(ids)) != len(ids): raise OCPError('DUPLICATE_ID', '/input/items')

    def validate(self, request):
        rid = request.get('request_id') if isinstance(request, dict) else None
        if not isinstance(rid, str) or not 1 <= len(rid) <= 128: rid = 'invalid-request'
        issues = []
        try: self._check(request)
        except OCPError as error: issues.append({'code': error.code, 'path': error.path, 'message': error.message})
        return {'core_version': '0.1.0', 'kind': 'validation', 'request_id': rid, 'valid': not issues, 'issues': issues}

    def execute(self, request):
        rid = request.get('request_id') if isinstance(request, dict) else None
        try:
            self._check(request)
            solution, complete = solve(request['input'], self.clock() + request['budget']['time_limit_ms'] / 1000, self.clock)
            metrics, constraints = measurements(request['input'], solution)
            if any(not c['satisfied'] for c in constraints): raise OCPError('INVALID_ENGINE_RESULT')
            status = 'optimal' if complete else 'feasible'
            proof = {'claim': 'optimal', 'method': 'bounded-knapsack-dp', 'scope': REFERENCE['id'] + ':0.1.0',
                     'evidence': {'objective': metrics[0]['value']}} if complete else None
            result = {'core_version': '0.1.0', 'kind': 'result', 'request_id': rid, 'capability': deepcopy(CAPABILITY),
                      'domain_profile': deepcopy(REFERENCE), 'execution_profile': deepcopy(SYNC), 'effective_configuration': configuration(),
                      'status': status, 'termination': 'completed' if complete else 'time_limit', 'solution': solution, 'proof': proof,
                      'metrics': metrics, 'constraints': constraints, 'provenance': {
                          'implementation': {'id': 'ocp-budget-engine-example', 'version': '0.1.0'},
                          'engine': {'id': 'example.budget-dp', 'version': '0.1.0'}, 'request_id': rid, 'limitations': list(SEMANTICS)}}
            envelope(result); return result
        except OCPError as error: return failure(rid, error)

    def evaluate(self, request, solution):
        rid = request.get('request_id') if isinstance(request, dict) else None
        try:
            self._check(request); metrics, constraints = measurements(request['input'], solution)
            return {'core_version': '0.1.0', 'kind': 'evaluation', 'request_id': rid, 'capability': deepcopy(CAPABILITY),
                    'domain_profile': deepcopy(REFERENCE), 'metrics': metrics, 'constraints': constraints,
                    'evaluator': {'id': 'example.budget-provider-evaluation', 'version': '0.1.0'},
                    'limitations': ['Provider evaluation reuses provider logic. Use the independent checker for verification.']}
        except OCPError as error: return failure(rid, error)
