"""Prepare separate participant inputs and reviewer answers; no model calls.

Run using an installed candidate/checker environment. Expected objective values
are independently enumerated, not copied from the engine to be evaluated.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def prepare(output, conversation_host='chatgpt-desktop'):
    from conformance.worker import exhaustive_optimum
    from conformance.assessment import digest
    source = ROOT / 'cases/host-interface/worker-evaluation.json'
    spec = json.loads(source.read_text())
    cases = spec['cases']
    if (spec['format'] != 'ocp-host-evaluation/1'
            or Counter(c['group'] for c in cases) != {'normal':10, 'missing':5, 'unsupported':5}
            or len({c['id'] for c in cases}) != 20):
        raise ValueError('INVALID_CASE_SET')
    inspection = runpy.run_path(str(ROOT / 'examples/native/inspection.py'))
    base, csv_hashes = inspection['problem'](*(ROOT / 'examples/native' / ('inspection-'+name+'.csv')
                                             for name in ('workers','tasks','costs')))
    if exhaustive_optimum(base) != 16:
        raise ValueError('BASELINE_CHANGED')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    answers = []
    for case in cases:
        data = deepcopy(base)
        missing = []
        for change in case['changes']:
            parent = data
            for part in change['path'][:-1]:
                parent = parent[part]
            key = change['path'][-1]
            if change['op'] == 'remove':
                missing.append({'path':change['path'], 'clarification':parent.pop(key)})
            elif change['op'] == 'set':
                parent[key] = deepcopy(change['value'])
            else:
                raise ValueError('UNKNOWN_CHANGE')
        participant = output / 'participant' / case['id']
        write(participant / 'input.json', data)
        for lang in ('ko','en'):
            (participant / ('prompt.'+lang+'.txt')).write_text(case['prompt_'+lang]+'\n')
        answer = {'id':case['id'], 'group':case['group'], 'input_sha256':digest(data),
                  'initial_solver_calls':1 if case['group']=='normal' else 0,
                  'must_ask':missing, 'objective_value':None, 'result_status':None}
        if case['group'] == 'normal':
            value = exhaustive_optimum(data)
            answer.update(objective_value=value, result_status='infeasible' if value is None else 'optimal')
        answers.append(answer)
    values = {a['id']:a['objective_value'] for a in answers}
    if [values[n] for n in ('N01','N02','N03','N04','N05','N10')] != [16,19,25,None,0,32]:
        raise ValueError('KNOWN_EXPECTATION_CHANGED')
    (output/'participant/README.txt').write_text(
        'Synthetic fixed-time inspection tasks. Time values share the same local day origin 00:00; '
        'the case input specifies their unit. Costs are per whole task assignment, not hourly wages. Only listed eligible workers '
        'may perform each task. An explicitly empty eligibility list means nobody is qualified. '
        'For a field missing from a case, ask the facilitator; do not copy it from another case. '
        'Use one case per fresh host session. Reviewer files are not participant material.\n')
    write(output/'reviewer/answers.json', answers)
    rows = [{'host':host,'case_id':c['id'],'repetition':repeat,'status':'NOT_RUN',
             'host_version':None,'model':None,'model_version':None,'started_at':None,'ended_at':None,
             'outcome':None,'asked_required_data':None,'critical_errors':[],
             'tool_calls_file':None,'conversation_file':None,'support_interventions':[],
             'model_cost':None}
            for host in ('claude-code',conversation_host) for c in cases for repeat in range(1,4)]
    write(output/'reviewer/runs.json', rows)
    manifest = {'format':spec['format'], 'status':'PREPARED','cases':len(cases),
                'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'csv_sha256':csv_hashes,
                'profile':spec['profile'],'domain':spec['domain'],'conversation_host':conversation_host,'model_calls':0,
                'actual_host_acceptance':'NOT_RUN','human_acceptance':'NOT_RUN',
                'files':{str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(output.rglob('*')) if p.is_file()}}
    write(output/'manifest.json', manifest)
    return {'status':'PREPARED','directory':str(output),'cases':20,'planned_sessions':len(rows),
            'model_calls':0,'actual_host_acceptance':'NOT_RUN','human_acceptance':'NOT_RUN'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--conversation-host',choices=('chatgpt-desktop','chatgpt-web'),default='chatgpt-desktop')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output,args.conversation_host)))
