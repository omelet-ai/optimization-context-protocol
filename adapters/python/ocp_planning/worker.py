"""Fixed-time worker assignment by bounded depth-first branch and bound."""
from ocp_candidate.contract import OCPError
ID='worker.scheduling'
STEM='worker-scheduling'
ENGINE='ocp.worker-branch-and-bound'
PROOF='bounded-assignment-enumeration'
LIMITATIONS=['1-8 fixed-time tasks, 1-4 workers; half-open integer minute intervals; one worker per task',
             'No shift generation, overtime, breaks, travel, fairness or automatic constraint relaxation',
             'Budget 1-5000 ms; optimal/infeasible proof requires independent bounded enumeration']
REQUIREMENTS=[{'path':'/'+p,'reason':r,'unit':u} for p,r,u in [
 ('tasks','Fixed intervals, explicit eligibility and exact pair costs','minute'),('workers','Availability and total workload limit','minute'),
 ('time_unit','Shared relative time origin; adjacent tasks do not overlap','minute'),('cost_unit','Single explicit additive cost unit','cost_unit')]]

def validate_problem(p):
    workers=p['workers'];tasks=p['tasks'];ids={w['id'] for w in workers}
    if len(ids)!=len(workers) or len({t['id'] for t in tasks})!=len(tasks):raise OCPError('DUPLICATE_ID')
    for w in workers:
        previous=-1
        for a in sorted(w['availability'],key=lambda a:a['start']):
            if a['start']>=a['end'] or a['start']<previous:raise OCPError('INVALID_AVAILABILITY')
            previous=a['end']
    for t in tasks:
        if t['start']>=t['end']:raise OCPError('INVALID_INTERVAL')
        if not set(t['eligible_workers'])<=ids or set(t['costs'])!=set(t['eligible_workers']):raise OCPError('INVALID_ELIGIBILITY')

def evaluate(p,s):
    workers={w['id']:w for w in p['workers']};tasks={t['id']:t for t in p['tasks']}
    v={k:0 for k in ['task_coverage','eligibility','availability','no_overlap','workload']};counts={k:0 for k in tasks};assigned={k:[] for k in workers};cost=0
    for a in s['assignments']:
        if a['task_id'] not in tasks or a['worker_id'] not in workers:raise OCPError('UNKNOWN_ASSIGNMENT')
        t=tasks[a['task_id']];w=workers[a['worker_id']];counts[t['id']]+=1;assigned[w['id']].append(t)
        if w['id'] not in t['eligible_workers']:raise OCPError('INELIGIBLE_ASSIGNMENT')
        cost+=t['costs'][w['id']]
        if not any(x['start']<=t['start'] and t['end']<=x['end'] for x in w['availability']):v['availability']+=1
    v['task_coverage']=sum(abs(n-1) for n in counts.values())
    for wid,ts in assigned.items():
        v['workload']+=sum(t['end']-t['start'] for t in ts)>workers[wid]['max_minutes']
        v['no_overlap']+=sum(max(a['start'],b['start'])<min(a['end'],b['end']) for i,a in enumerate(ts) for b in ts[i+1:])
    return cost,v

def solve(p,deadline,clock):
    workers={w['id']:w for w in p['workers']};tasks=p['tasks'];assigned={w:[] for w in workers};minutes={w:0 for w in workers}
    best=None;best_cost=float('inf');chosen=[];complete=True
    class Deadline(Exception):pass
    def visit(i,cost):
        nonlocal best,best_cost
        if clock()>=deadline:raise Deadline
        if cost>=best_cost:return
        if i==len(tasks):best={'assignments':[dict(a) for a in chosen]};best_cost=cost;return
        t=tasks[i];duration=t['end']-t['start']
        for wid in sorted(t['eligible_workers'],key=lambda w:(t['costs'][w],w)):
            w=workers[wid]
            if minutes[wid]+duration>w['max_minutes']:continue
            if not any(a['start']<=t['start'] and t['end']<=a['end'] for a in w['availability']):continue
            if any(t['start']<b['end'] and b['start']<t['end'] for b in assigned[wid]):continue
            assigned[wid].append(t);minutes[wid]+=duration;chosen.append({'task_id':t['id'],'worker_id':wid})
            visit(i+1,cost+t['costs'][wid])
            chosen.pop();minutes[wid]-=duration;assigned[wid].pop()
    try:visit(0,0)
    except Deadline:complete=False
    return best,complete
