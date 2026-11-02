"""Prepare new participant questions and independent reviewer answers; no model calls."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {'routing-basic':'routing.basic', 'worker-scheduling':'worker.scheduling',
            'inventory-replenishment':'inventory.replenishment'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def oracle(domain, problem):
    # Independent exhaustive checkers; no runtime, provider or engine import.
    from conformance import routing, worker, inventory
    check = {'routing-basic':routing, 'worker-scheduling':worker, 'inventory-replenishment':inventory}[domain]
    check.validate_problem(problem)
    value = check.exhaustive_optimum(problem)
    if domain == 'routing-basic':
        value = value['optimal_cost']
    return {'feasible':value is not None, 'optimal_objective':value,
            'unit':'meter' if domain == 'routing-basic' else 'cost_unit',
            'objective_policy':'Accept a checked feasible result; do not claim optimality without its proof.'
                               if domain == 'routing-basic' else 'Check the finite optimality/infeasibility proof.'}


def prepare(source, output, hosts=('claude-code','chatgpt-desktop'), repeats=2):
    source, output = Path(source).resolve(), Path(output).resolve()
    if len(hosts) != 2 or len(set(hosts)) != 2 or any(h not in ('claude-code','chatgpt-desktop','codex-cli') for h in hosts):
        raise ValueError('SELECT_TWO_DISTINCT_HOSTS')
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError('INVALID_REPETITIONS')
    spec = json.loads(source.read_text()); cases = spec['cases']
    if spec['format'] != 'ocp-multidomain-evaluation/1' or len(cases) != 12 or len({c['id'] for c in cases}) != 12:
        raise ValueError('INVALID_CASE_SET')
    answers, participants = [], []
    for case in cases:
        identifier, domain, kind = case['id'], case['domain'], case['category']
        if not isinstance(identifier,str) or not identifier.startswith('G-') or not identifier.replace('-','').isalnum():
            raise ValueError('INVALID_CASE_ID')
        if domain not in PROFILES or kind not in ('solve','compare','missing','unsupported'):
            raise ValueError('INVALID_CASE')
        if set(case['inputs']) != ({'baseline','current'} if kind == 'compare' else {'current'}):
            raise ValueError('INVALID_SCENARIOS')
        answer = {'id':identifier,'domain':domain,'category':kind, 'review':deepcopy(case['review']),
                  'expected_action':'SOLVE_AND_CHECK' if kind in ('solve','compare') else 'ASK_WITHOUT_SUBMIT',
                  'input_sha256':{key:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                                  for key,value in case['inputs'].items()}}
        if kind in ('solve','compare'):
            answer['scenarios'] = {key:oracle(domain,value) for key,value in case['inputs'].items()}
            if kind == 'compare':
                a, b = [answer['scenarios'][key]['optimal_objective'] for key in ('current','baseline')]
                answer['current_minus_baseline'] = None if a is None or b is None else a-b
        else:
            from conformance.core_contract import ContractError
            try:
                oracle(domain,case['inputs']['current'])
            except ContractError as error:
                answer['independent_input_rejection'] = error.code
            else:
                raise ValueError('NEGATIVE_CASE_MUST_BE_INVALID')
        answers.append(answer)
        participants.append({key:deepcopy(case[key]) for key in ('id','domain','prompt','inputs')})
    # Validate the entire packet before writing; never overwrite an earlier run.
    output.mkdir(parents=True,exist_ok=False)
    for case in participants:
        write(output/'participant'/case['id']/'case.json',case)
        (output/'participant'/case['id']/'prompt.txt').write_text(case['prompt']+'\n')
    (output/'participant/README.txt').write_text(
        'Use one supplied case per fresh host session with the reviewed OCP evidence server. '
        'Read server context and its exact catalog. Only synthetic data is provided. '
        'Use the supplied input and preserve all required rules. Missing values require a question. '
        'For missing/unsupported cases, stop after asking; the facilitator supplies no guessed values. '
        'Explain checked results and their limits. Show current and baseline separately when both are supplied. '
        'Use only this participant folder; reviewer answers are not participant input.\n')
    write(output/'reviewer/answers.json',answers)
    runs = [{'host':host,'case_id':case['id'],'repetition':rep,'status':'NOT_RUN',
             'actual_surface':None,'host_version':None,'model':None,'runtime_manifest_sha256':None,
             'task_complete':None,'requirement_preserved':None,'final_claims_grounded':None,
             'explicit_validate_observed':None,'binding_input_validation':None,
             'critical_errors':None,'tool_trace':None,'final_answer':None,'assistance':None,
             'elapsed_seconds':None,'model_cost':None}
            for host in hosts for rep in range(1,repeats+1) for case in cases]
    write(output/'reviewer/runs.json',runs)
    totals={kind:sum(c['category'] in categories for c in cases)*repeats for kind,categories in
            [('normal',('solve','compare')),('missing',('missing',)),('unsupported',('unsupported',))]}
    write(output/'reviewer/criteria.json',{
        'normal_completion':{'minimum':math.ceil(.9*totals['normal']),'sessions_per_host':totals['normal']},
        'missing_data':{'minimum_correct_clarifications':totals['missing'],'sessions_per_host':totals['missing'],'submits_allowed':0},
        'unsupported':{'sessions_per_host':totals['unsupported'],'submits_allowed':0},
        'critical_errors':'Zero invented data, false optimality, timeout-as-infeasible or unsupported comparison claims in this packet.',
        'trace_review':'Check every submitted input against the supplied scenario, each independent verification and all final numerical/scope claims.',
        'input_validation':'Report explicit host validate separately from binding precheck; neither substitutes for task correctness.',
        'human_usefulness':'NOT_RUN: separate first-user exercises with their own input and assistance/time logs.',
        'sample_scope':'Diagnostic acceptance packet; not a population accuracy estimate or a 0.2/0.3 improvement comparison.'})
    manifest={'format':spec['format'],'status':'PREPARED','cases':len(cases),'hosts':list(hosts),
              'repetitions':repeats,'planned_sessions':len(runs),'model_calls':0,
              'actual_host_acceptance':'NOT_RUN','human_acceptance':'NOT_RUN',
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'files':{str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(output.rglob('*')) if p.is_file()}}
    write(output/'manifest.json',manifest)
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'cases/host-interface/multidomain-evaluation.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--second-host',choices=('chatgpt-desktop','codex-cli'),default='chatgpt-desktop')
    args=parser.parse_args()
    result=prepare(args.source,args.output,hosts=('claude-code',args.second_host))
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))
