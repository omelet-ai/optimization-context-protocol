"""Five Core operations implemented against the canonical worker profile.

This provider shares only the public SDK/schema, not the reference planning
adapter, its solver, or the independent conformance checker.
"""
from copy import deepcopy
from itertools import combinations
import time

from ocp_candidate.contract import OCPError, envelope, failure, schema, validate
from .engine import solve

PROFILE = {'id': 'worker.scheduling', 'version': '0.1.0'}
CAPABILITY = {'id': 'worker.scheduling.greedy-example', 'version': '0.1.0'}
SYNC = {'id': 'execution.sync', 'version': '0.1.0'}
LIMITATIONS = [
    'Example heuristic: 1-8 fixed-time tasks and 1-4 workers; integer minute intervals and additive cost_unit.',
    'Greedy time order and cheapest eligible worker; no backtracking or optimality guarantee.',
    'Failure to find a complete assignment is unknown, never a proof of infeasibility.',
    'No shifts, breaks, fairness, overtime, travel or automatic constraint relaxation.',
    'Provider evaluation is not independent; use the separately installed conformance checker.',
]


def configuration():
    return deepcopy(schema('worker-scheduling-configuration')['const'])


def check_problem(problem):
    validate('worker-scheduling-input', problem)
    workers = problem['workers']
    tasks = problem['tasks']
    if len({w['id'] for w in workers}) != len(workers) or len({t['id'] for t in tasks}) != len(tasks):
        raise OCPError('DUPLICATE_ID')
    for index, worker in enumerate(workers):
        intervals = sorted((a['start'], a['end']) for a in worker['availability'])
        if any(start >= end for start, end in intervals) or any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
            raise OCPError('INVALID_AVAILABILITY', f'/input/workers/{index}/availability')
    worker_ids = {w['id'] for w in workers}
    for index, task in enumerate(tasks):
        if task['start'] >= task['end']:
            raise OCPError('INVALID_INTERVAL', f'/input/tasks/{index}')
        if not set(task['eligible_workers']).issubset(worker_ids) or set(task['costs']) != set(task['eligible_workers']):
            raise OCPError('INVALID_ELIGIBILITY', f'/input/tasks/{index}/eligible_workers')


def measure(problem, solution):
    """Provider-side report only. The external checker reimplements these checks."""
    validate('worker-scheduling-solution', solution, 'INVALID_SOLUTION')
    tasks = {t['id']: t for t in problem['tasks']}
    workers = {w['id']: w for w in problem['workers']}
    assigned = {wid: [] for wid in workers}
    counts = dict.fromkeys(tasks, 0)
    violations = dict.fromkeys(configuration()['constraints'], 0)
    cost = 0
    for assignment in solution['assignments']:
        tid, wid = assignment['task_id'], assignment['worker_id']
        if tid not in tasks or wid not in workers:
            raise OCPError('UNKNOWN_ASSIGNMENT')
        task = tasks[tid]
        if wid not in task['eligible_workers']:
            raise OCPError('INELIGIBLE_ASSIGNMENT')  # No invented cost for a missing pair.
        counts[tid] += 1
        assigned[wid].append(task)
        cost += task['costs'][wid]
        if not any(a['start'] <= task['start'] and task['end'] <= a['end'] for a in workers[wid]['availability']):
            violations['availability'] += 1
    violations['task_coverage'] = sum(abs(count - 1) for count in counts.values())
    for wid, group in assigned.items():
        violations['workload'] += int(sum(t['end'] - t['start'] for t in group) > workers[wid]['max_minutes'])
        violations['no_overlap'] += sum(a['start'] < b['end'] and b['start'] < a['end'] for a, b in combinations(group, 2))
    metrics = [{'id': 'total_cost', 'role': 'optimized', 'definition': 'worker.scheduling.total_cost.v1',
                'unit': 'cost_unit', 'source': 'engine', 'status': 'evaluated', 'value': cost, 'reason': None}]
    constraints = [{'id': cid, 'role': 'enforced', 'definition': 'worker.scheduling.' + cid + '.v1',
                    'unit': 'count', 'source': 'engine', 'status': 'evaluated', 'violation': value,
                    'satisfied': value == 0, 'reason': None} for cid, value in violations.items()]
    return metrics, constraints


class WorkerProvider:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock

    def describe(self):
        return {'core_version': '0.1.0', 'kind': 'capability', 'capability': deepcopy(CAPABILITY),
                'domain_profile': deepcopy(PROFILE), 'execution_profiles': [deepcopy(SYNC)],
                'bindings': [{'id': 'binding.in_process', 'version': '0.1.0'}],
                'environments': [{'id': 'environment.local', 'version': '0.1.0'}],
                'objectives': [{'id': 'total_cost', 'direction': 'minimize', 'role': 'optimized',
                                'definition': 'worker.scheduling.total_cost.v1', 'unit': 'cost_unit'}],
                'constraints': [{'id': cid, 'kind': 'hard', 'role': 'enforced', 'unit': 'count',
                                 'definition': 'worker.scheduling.' + cid + '.v1'} for cid in configuration()['constraints']],
                'configuration_schema': deepcopy(schema('worker-scheduling-configuration')),
                'input_schema_id': schema('worker-scheduling-input')['$id'],
                'solution_schema_id': schema('worker-scheduling-solution')['$id'],
                'defaults': configuration(), 'limitations': list(LIMITATIONS)}

    def requirements(self, selected):
        try:
            validate('worker-scheduling-configuration', selected, 'UNSUPPORTED_CONFIGURATION')
            return {'core_version': '0.1.0', 'kind': 'requirements', 'capability': deepcopy(CAPABILITY),
                    'domain_profile': deepcopy(PROFILE), 'effective_configuration': configuration(),
                    'input_schema_id': schema('worker-scheduling-input')['$id'],
                    'required_fields': [
                        {'path': '/workers', 'reason': 'Availability and total work limits', 'unit': 'minute'},
                        {'path': '/tasks', 'reason': 'Fixed intervals, eligible IDs and exact pair costs', 'unit': 'minute'},
                        {'path': '/time_unit', 'reason': 'Common time origin and half-open intervals', 'unit': 'minute'},
                        {'path': '/cost_unit', 'reason': 'Explicit additive cost unit', 'unit': 'cost_unit'}]}
        except OCPError as error:
            return failure(None, error)

    def _check(self, request):
        envelope(request)
        if request['kind'] != 'request':
            raise OCPError('INVALID_REQUEST')
        if request['capability'] != CAPABILITY or request['domain_profile'] != PROFILE or request['execution_profile'] != SYNC:
            raise OCPError('VERSION_MISMATCH')
        validate('worker-scheduling-configuration', request['configuration'], 'UNSUPPORTED_CONFIGURATION')
        if not 1 <= request['budget']['time_limit_ms'] <= 5000:
            raise OCPError('LIMIT_EXCEEDED', '/budget/time_limit_ms')
        check_problem(request['input'])

    def validate(self, request):
        rid = request.get('request_id') if isinstance(request, dict) else None
        if not isinstance(rid, str) or not 1 <= len(rid) <= 128:
            rid = 'invalid-request'
        issues = []
        try:
            self._check(request)
        except OCPError as error:
            issues.append({'code': error.code, 'path': error.path, 'message': error.message})
        return {'core_version': '0.1.0', 'kind': 'validation', 'request_id': rid, 'valid': not issues, 'issues': issues}

    def execute(self, request):
        rid = request.get('request_id') if isinstance(request, dict) else None
        try:
            self._check(request)
            request = deepcopy(request)
            outcome = solve(request['input'], self.clock() + request['budget']['time_limit_ms'] / 1000, self.clock)
            metrics, constraints = measure(request['input'], outcome.solution) if outcome.solution is not None else ([], [])
            if any(not c['satisfied'] for c in constraints):
                raise OCPError('INVALID_ENGINE_RESULT')
            result = {'core_version': '0.1.0', 'kind': 'result', 'request_id': rid,
                      'capability': deepcopy(CAPABILITY), 'domain_profile': deepcopy(PROFILE), 'execution_profile': deepcopy(SYNC),
                      'effective_configuration': request['configuration'], 'status': 'feasible' if outcome.solution is not None else 'unknown',
                      'termination': outcome.termination, 'solution': outcome.solution, 'proof': None,
                      'metrics': metrics, 'constraints': constraints,
                      'provenance': {'implementation': {'id': 'ocp-worker-greedy-example', 'version': '0.1.0'},
                                     'engine': {'id': 'ocp.worker-greedy-example', 'version': '0.1.0'},
                                     'request_id': rid, 'limitations': list(LIMITATIONS)}}
            envelope(result)
            return result
        except OCPError as error:
            return failure(rid, error)
        except Exception:
            return failure(rid, OCPError('EXECUTION_ERROR', message='Greedy worker example failed'))

    def evaluate(self, request, solution):
        rid = request.get('request_id') if isinstance(request, dict) else None
        try:
            self._check(request)
            metrics, constraints = measure(request['input'], solution)
            result = {'core_version': '0.1.0', 'kind': 'evaluation', 'request_id': rid, 'capability': deepcopy(CAPABILITY),
                      'domain_profile': deepcopy(PROFILE), 'metrics': metrics, 'constraints': constraints,
                      'evaluator': {'id': 'ocp-worker-greedy-example.evaluator', 'version': '0.1.0'},
                      'limitations': ['Provider evaluation; not independent verification or an optimality proof.']}
            envelope(result)
            return result
        except OCPError as error:
            return failure(rid, error)
