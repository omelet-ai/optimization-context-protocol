"""Deterministic first-fit by time, choosing the cheapest available worker.

Pure standard library; no reference solver, SDK or checker imports. This is a
heuristic without backtracking: a failed placement proves nothing about whether
another assignment exists. Inputs must have passed the provider's validation.
"""
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class Outcome:
    solution: dict | None
    termination: str


def solve(problem, deadline, clock=time.monotonic):
    workers = {worker['id']: worker for worker in problem['workers']}
    schedule = {wid: [] for wid in workers}
    used = dict.fromkeys(workers, 0)
    assignments = []
    for task in sorted(problem['tasks'], key=lambda t: (t['start'], t['end'], t['id'])):
        if clock() >= deadline:
            return Outcome(None, 'time_limit')
        duration = task['end'] - task['start']
        chosen = None
        for wid in sorted(task['eligible_workers'], key=lambda wid: (task['costs'][wid], wid)):
            if clock() >= deadline:
                return Outcome(None, 'time_limit')
            worker = workers[wid]
            if used[wid] + duration > worker['max_minutes']:
                continue
            if not any(a['start'] <= task['start'] and task['end'] <= a['end'] for a in worker['availability']):
                continue
            if any(task['start'] < end and start < task['end'] for start, end in schedule[wid]):
                continue
            chosen = wid
            break
        if chosen is None:
            return Outcome(None, 'search_exhausted')
        schedule[chosen].append((task['start'], task['end']))
        used[chosen] += duration
        assignments.append({'task_id': task['id'], 'worker_id': chosen})
    # A full feasible incumbent may be retained when the final clock check expires.
    return Outcome({'assignments': assignments}, 'time_limit' if clock() >= deadline else 'completed')
