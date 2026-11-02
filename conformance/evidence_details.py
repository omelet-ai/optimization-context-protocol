"""Independent recomputation of built-in worker explanation rows; no mapper imports."""
from copy import deepcopy
from .assessment import digest
from .core_contract import ContractError
from .planning import integral_numbers


def detail_report(request, result, details, checker):
    return {'status': 'PASS', 'checker': checker, 'request_sha256': digest(request),
            'response_sha256': digest(result), 'details_sha256': digest(details)}


def verify_worker_details(request, result, objective, preparation, details):
    if result['solution'] is None:
        expected = None
    else:
        data, solution = integral_numbers(request['input']), integral_numbers(result['solution'])
        tasks = {task['id']: task for task in data['tasks']}
        changes = {(a['task_id'], a['worker_id']): a
                   for a in preparation.get('mapping_facts', {}).get('cost_adjustments', [])}
        assignments = []
        for row in solution['assignments']:
            task = tasks[row['task_id']]
            item = {**row, 'start': task['start'], 'end': task['end'],
                    'duration_minutes': task['end']-task['start'], 'cost': task['costs'][row['worker_id']]}
            key = (row['task_id'], row['worker_id'])
            if key in changes:
                if changes[key]['prepared_pair_cost'] != item['cost']:
                    raise ContractError('EXPLANATION_FACTS_MISMATCH')
                item['cost_adjustment'] = deepcopy(changes[key])
            assignments.append(item)
        total = sum(row['cost'] for row in assignments)
        if total != objective:
            raise ContractError('EXPLANATION_FACTS_MISMATCH')
        workloads = []
        for worker in data['workers']:
            assigned = [a for a in assignments if a['worker_id'] == worker['id']]
            minutes = sum(a['duration_minutes'] for a in assigned)
            workloads.append({'worker_id': worker['id'], 'task_ids': [a['task_id'] for a in assigned],
                'assigned_minutes': minutes, 'max_minutes': worker['max_minutes'],
                'remaining_minutes': worker['max_minutes']-minutes})
        expected = {'basis': 'STORED_REQUEST_AND_INDEPENDENTLY_VERIFIED_SOLUTION',
            'time_unit': data['time_unit'], 'cost_unit': data['cost_unit'],
            'assignments': assignments, 'workloads': workloads, 'total_cost': total}
    if digest(details) != digest(expected):
        raise ContractError('EXPLANATION_FACTS_MISMATCH')
    return detail_report(request, result, details, {'id': 'ocp-worker-detail-checker', 'version': '0.1.0'})
