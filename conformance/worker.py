"""Independent worker checker and Cartesian-product oracle, no branch-and-bound code."""
from collections import Counter
from itertools import product
import sys
from .planning import shape, verify, integral_numbers
from .core_contract import ContractError
ID='worker.scheduling'
STEM='worker-scheduling'
PROOF='bounded-assignment-enumeration'

def validate_problem(p):
    shape(STEM,'input',p)
    ws=[w['id'] for w in p['workers']];ts=[t['id'] for t in p['tasks']]
    if len(set(ws))!=len(ws) or len(set(ts))!=len(ts):raise ContractError('DUPLICATE_ID')
    for w in p['workers']:
        intervals=sorted((a['start'],a['end']) for a in w['availability'])
        if any(a>=b for a,b in intervals) or any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):raise ContractError('INVALID_AVAILABILITY')
    for t in p['tasks']:
        if t['start']>=t['end'] or set(t['costs'])!=set(t['eligible_workers']) or set(t['eligible_workers'])-set(ws):raise ContractError('INVALID_TASK')

def _measure(p,pairs):
    ts={t['id']:t for t in p['tasks']};ws={w['id']:w for w in p['workers']};counts=Counter(t for t,w in pairs)
    if any(t not in ts or w not in ws for t,w in pairs):raise ContractError('UNKNOWN_ASSIGNMENT')
    cost=0;v={'task_coverage':sum(abs(counts[t]-1) for t in ts),'eligibility':0,'availability':0,'no_overlap':0,'workload':0}
    for tid,wid in pairs:
        t,w=ts[tid],ws[wid]
        if wid not in t['costs']:raise ContractError('INELIGIBLE_ASSIGNMENT')
        cost+=t['costs'][wid]
        if all(t['start']<a['start'] or t['end']>a['end'] for a in w['availability']):v['availability']+=1
    for wid,w in ws.items():
        spans=[(ts[t]['start'],ts[t]['end']) for t,owner in pairs if owner==wid]
        if sum(b-a for a,b in spans)>w['max_minutes']:v['workload']+=1
        for i,(a,b) in enumerate(spans):
            v['no_overlap']+=sum(not (b<=c or d<=a) for c,d in spans[i+1:])
    return {'feasible':not any(v.values()),'total_cost':cost,'violations':v}

def evaluate(p,s):
    validate_problem(p);shape(STEM,'solution',s);p=integral_numbers(p);s=integral_numbers(s)
    return _measure(p,[(a['task_id'],a['worker_id']) for a in s['assignments']])

def exhaustive_optimum(p):
    validate_problem(p);p=integral_numbers(p);best=None
    for owners in product(*[t['eligible_workers'] for t in p['tasks']]):
        m=_measure(p,list(zip([t['id'] for t in p['tasks']],owners)))
        if m['feasible'] and (best is None or m['total_cost']<best):best=m['total_cost']
    return best

def verify_result(request,result):return verify(sys.modules[__name__],request,result)
