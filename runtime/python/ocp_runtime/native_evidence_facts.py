"""Arithmetic on checked requests/results; no solver or language interpretation."""
from ocp_candidate.native import NativeError

WORKER = {'id': 'worker.scheduling', 'version': '0.1.0'}


def request_schema():
    """Expose the packaged canonical request with its local references expanded."""
    from ocp_candidate.contract import schema
    document = schema('core')

    def expand(value):
        if isinstance(value, dict):
            if '$ref' in value:
                return expand(document['$defs'][value['$ref'].removeprefix('#/$defs/')])
            return {key: expand(child) for key, child in value.items()}
        if isinstance(value, list):
            return [expand(child) for child in value]
        return value

    return expand(document['$defs']['request'])


def mapping_facts(original, requirements, verification):
    facts = {
        'assignments_checked': verification['assignments_checked'],
        'feasible_assignments': verification['feasible_assignments'],
        'feasible_count_scope': 'ALL_ORIGINAL_CONSTRAINTS_AND_DECLARED_REQUIREMENTS',
        'requirement_only_count': None,
        'requirement_only_count_status': 'NOT_COMPUTED',
    }
    if not requirements:
        facts['feasible_count_scope'] = 'NOT_ENUMERATED_IDENTITY_MAPPING'
        return facts
    from conformance.planning import integral_numbers
    data, rule = integral_numbers(original['input']), integral_numbers(requirements[0])
    if rule['kind'] == 'fixed_breaks':
        facts['breaks'] = []
        for br in rule['breaks']:
            overlapping = [t for t in data['tasks']
                           if t['start'] < br['end'] and br['start'] < t['end']]
            facts['breaks'].append({**br,
                'overlapping_task_ids': [t['id'] for t in overlapping],
                'removed_eligible_task_ids': [t['id'] for t in overlapping
                                              if br['worker_id'] in t['eligible_workers']]})
    elif rule['kind'] == 'outside_availability_cost':
        workers = {w['id']: w for w in data['workers']}
        facts['cost_adjustments'] = []
        for task in data['tasks']:
            for wid, rate in rule['worker_rates'].items():
                if wid not in task['eligible_workers']:
                    continue
                # Count original minutes separately from the mapper's interval sum.
                outside = sum(not any(a['start'] <= m < a['end']
                                      for a in workers[wid]['availability'])
                              for m in range(task['start'], task['end']))
                base = task['costs'][wid]
                facts['cost_adjustments'].append({'task_id': task['id'], 'worker_id': wid,
                    'original_pair_cost': base, 'outside_original_availability_minutes': outside,
                    'rate_per_minute': rate, 'additional_cost': outside * rate,
                    'prepared_pair_cost': base + outside * rate})
    return facts


def worker_solution_facts(request, result, objective, preparation):
    """Caller must independently verify the transcript and any linked preparation."""
    if request['domain_profile'] != WORKER or result['solution'] is None:
        return None
    from conformance.planning import integral_numbers
    data, solution = integral_numbers(request['input']), integral_numbers(result['solution'])
    tasks = {t['id']: t for t in data['tasks']}
    adjustments = {(a['task_id'], a['worker_id']): a
                   for a in preparation.get('mapping_facts', {}).get('cost_adjustments', [])}
    assignments = []
    for a in solution['assignments']:
        task = tasks[a['task_id']]
        row = {**a, 'start': task['start'], 'end': task['end'],
               'duration_minutes': task['end'] - task['start'],
               'cost': task['costs'][a['worker_id']]}
        if (task['id'], a['worker_id']) in adjustments:
            adjustment = adjustments[task['id'], a['worker_id']]
            if adjustment['prepared_pair_cost'] != row['cost']:
                raise NativeError('EXPLANATION_FACTS_MISMATCH')
            row['cost_adjustment'] = adjustment
        assignments.append(row)
    total = sum(a['cost'] for a in assignments)
    if objective != total:
        raise NativeError('EXPLANATION_FACTS_MISMATCH')
    workloads = []
    for worker in data['workers']:
        rows = [a for a in assignments if a['worker_id'] == worker['id']]
        minutes = sum(a['duration_minutes'] for a in rows)
        workloads.append({'worker_id': worker['id'], 'task_ids': [a['task_id'] for a in rows],
                          'assigned_minutes': minutes, 'max_minutes': worker['max_minutes'],
                          'remaining_minutes': worker['max_minutes'] - minutes})
    return {'basis': 'STORED_REQUEST_AND_INDEPENDENTLY_VERIFIED_SOLUTION',
            'time_unit': data['time_unit'], 'cost_unit': data['cost_unit'],
            'assignments': assignments, 'workloads': workloads, 'total_cost': total}
def explanation_basis(current, baseline, comparison):
    """Bind explanation facts to the same stored inputs assessed by the checker."""
    def reference(answer):
        report = answer['verification']
        return {'job_id': answer['job_id'], 'request_sha256': report.get('request_sha256'),
                'response_sha256': report.get('response_sha256'), 'verification_status': report['status']}
    return {'current': reference(current), 'baseline': reference(baseline) if baseline is not None else None,
            'comparison_status': comparison['status'], 'comparison_reason': comparison['reason'],
            'additional_claims': 'NOT_CHECKED', 'source_text_interpretation': 'NOT_CHECKED'}
