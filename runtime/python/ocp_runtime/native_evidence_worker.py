"""Built-in worker evidence registration; independent checks live in conformance."""
from copy import deepcopy
from conformance.preparation import WORKER, REQUIREMENTS_SCHEMA, validate_requirements, verify_preparation
from .native_evidence_registry import FEATURE_VERSION as EVIDENCE_VERSION
from .native_evidence_facts import mapping_facts, worker_solution_facts

def prepare(original, requirements):
    prepared = deepcopy(original)
    if not requirements:
        return prepared, {'id': 'identity', 'version': EVIDENCE_VERSION}
    rule = requirements[0]
    data = prepared['input']
    if rule['kind'] == 'fixed_breaks':
        for task in data['tasks']:
            blocked = {br['worker_id'] for br in rule['breaks']
                       if task['start'] < br['end'] and br['start'] < task['end']}
            task['eligible_workers'] = [w for w in task['eligible_workers'] if w not in blocked]
            task['costs'] = {w: c for w, c in task['costs'].items() if w not in blocked}
        mapping = 'worker.fixed-breaks-to-eligibility'
    else:
        rates = rule['worker_rates']
        for w in data['workers']:
            if w['id'] not in rates:
                continue
            for task in data['tasks']:
                if w['id'] not in task['costs']:
                    continue
                covered = sum(max(0, min(task['end'], a['end']) - max(task['start'], a['start']))
                              for a in w['availability'])
                outside = task['end'] - task['start'] - covered
                task['costs'][w['id']] += outside * rates[w['id']]
            w['availability'] = [{'start': 0, 'end': 10080}]
        mapping = 'worker.outside-availability-to-pair-cost'
    return prepared, {'id': mapping, 'version': EVIDENCE_VERSION}



def solution_facts(request, result, objective, preparation):
    return worker_solution_facts(request, result, objective, preparation)


def register(registry):
    from conformance.evidence_details import verify_worker_details
    registry.register(WORKER, feature_version=EVIDENCE_VERSION,
        identity={'id': 'ocp.worker-evidence', 'version': '0.1.0'},
        requirements_schema=REQUIREMENTS_SCHEMA, mapping_supported=True,
        validate=validate_requirements, prepare=prepare, verify_preparation=verify_preparation,
        mapping_facts=mapping_facts, solution_facts=solution_facts,
        verify_solution_facts=verify_worker_details)
