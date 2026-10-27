"""Synthetic fixed-time worker assignment: CSV input, explicit scenarios, real checks."""
import argparse
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import re

from ocp_candidate import Client, parse_json
from ocp_planning import worker_adapter
from conformance.worker import verify_result
from conformance.assessment import assess


class AnalysisError(ValueError):
    pass


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', value):
        raise AnalysisError('INVALID_IDENTIFIER')
    return value


def integer(value):
    if not isinstance(value, str) or not re.fullmatch(r'0|[1-9][0-9]{0,5}', value):
        raise AnalysisError('INVALID_INTEGER')
    return int(value)


def read_bytes(path):
    with Path(path).open('rb') as stream:
        data = stream.read(131073)
    if len(data) > 131072:
        raise AnalysisError('INPUT_TOO_LARGE')
    return data


def rows(data, headers):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
    if reader.fieldnames != headers:
        raise AnalysisError('CSV_HEADERS')
    result = list(reader)
    if not result or len(result) > 64 or any(set(r) != set(headers) or None in r.values() for r in result):
        raise AnalysisError('CSV_ROWS')
    return result


def load_problem(workers, tasks, costs, config):
    if not isinstance(config, dict) or set(config) != {'time_unit', 'cost_unit', 'scenarios'}:
        raise AnalysisError('SCENARIO_FIELDS')
    problem = {'time_unit': config['time_unit'], 'cost_unit': config['cost_unit'], 'workers': [], 'tasks': []}
    by_worker = {}
    for row in rows(workers, ['worker_id', 'available_start', 'available_end', 'max_minutes']):
        wid = identifier(row['worker_id'])
        maximum = integer(row['max_minutes'])
        if wid not in by_worker:
            by_worker[wid] = {'id': wid, 'availability': [], 'max_minutes': maximum}
        if by_worker[wid]['max_minutes'] != maximum:
            raise AnalysisError('INCONSISTENT_WORKLOAD')
        by_worker[wid]['availability'].append({'start': integer(row['available_start']), 'end': integer(row['available_end'])})
    problem['workers'] = list(by_worker.values())
    by_task = {}
    for row in rows(tasks, ['task_id', 'start', 'end', 'eligible_workers']):
        tid = identifier(row['task_id'])
        if tid in by_task:
            raise AnalysisError('DUPLICATE_TASK')
        eligible = [identifier(w) for w in row['eligible_workers'].split('|')] if row['eligible_workers'] else []
        if len(eligible) != len(set(eligible)) or set(eligible) - set(by_worker):
            raise AnalysisError('INVALID_ELIGIBILITY')
        by_task[tid] = {'id': tid, 'start': integer(row['start']), 'end': integer(row['end']), 'eligible_workers': eligible, 'costs': {}}
    for row in rows(costs, ['task_id', 'worker_id', 'cost']):
        tid, wid = identifier(row['task_id']), identifier(row['worker_id'])
        if tid not in by_task or wid not in by_task[tid]['eligible_workers']:
            raise AnalysisError('UNEXPECTED_COST')
        if wid in by_task[tid]['costs']:
            raise AnalysisError('DUPLICATE_COST')
        by_task[tid]['costs'][wid] = integer(row['cost'])
    for task in by_task.values():
        if set(task['costs']) != set(task['eligible_workers']):
            raise AnalysisError('MISSING_COST')
    problem['tasks'] = list(by_task.values())
    return problem


def scenarios(problem, config):
    definitions = config['scenarios']
    if not isinstance(definitions, list) or not 1 <= len(definitions) <= 5:
        raise AnalysisError('SCENARIO_COUNT')
    result, ids = [('baseline', deepcopy(problem), [])], {'baseline'}
    for scenario in definitions:
        if not isinstance(scenario, dict) or set(scenario) != {'id', 'changes'}:
            raise AnalysisError('SCENARIO_FIELDS')
        sid = identifier(scenario['id'])
        if sid in ids:
            raise AnalysisError('DUPLICATE_SCENARIO')
        ids.add(sid)
        changes = scenario['changes']
        if not isinstance(changes, list) or not 1 <= len(changes) <= 8:
            raise AnalysisError('SCENARIO_CHANGES')
        changed, touched = deepcopy(problem), set()
        for change in changes:
            if not isinstance(change, dict):
                raise AnalysisError('SCENARIO_CHANGE')
            operation = change.get('op')
            if operation == 'set_cost' and set(change) == {'op', 'task_id', 'worker_id', 'value'}:
                tid, wid = identifier(change['task_id']), identifier(change['worker_id'])
                task = next((t for t in changed['tasks'] if t['id'] == tid), None)
                if task is None or wid not in task['costs'] or type(change['value']) is not int:
                    raise AnalysisError('INVALID_COST_CHANGE')
                task['costs'][wid] = change['value']
                key = (operation, tid, wid)
            elif operation == 'set_availability' and set(change) == {'op', 'worker_id', 'value'}:
                wid = identifier(change['worker_id'])
                worker = next((w for w in changed['workers'] if w['id'] == wid), None)
                if worker is None:
                    raise AnalysisError('UNKNOWN_WORKER')
                worker['availability'] = deepcopy(change['value'])
                key = (operation, wid)
            else:
                raise AnalysisError('UNSUPPORTED_CHANGE')
            if key in touched:
                raise AnalysisError('DUPLICATE_CHANGE')
            touched.add(key)
        result.append((sid, changed, deepcopy(changes)))
    return result


def comparison(baseline, current):
    if baseline['response']['solution'] is None or current['response']['solution'] is None:
        return {'cost_delta': None, 'reason': 'A scenario has no solution; no comparable cost is available.'}
    left, right = baseline['response']['metrics'][0], current['response']['metrics'][0]
    if baseline['request']['domain_profile'] != current['request']['domain_profile'] or any(left[k] != right[k] for k in ('id', 'definition', 'unit', 'role')):
        return {'cost_delta': None, 'reason': 'Different profile or objective semantics; costs are not comparable.'}
    return {'cost_delta': right['value'] - left['value'], 'reason': 'Same profile/version and objective semantics; changed inputs are listed.'}


def markdown(report):
    text = ['# Worker assignment analysis', '', 'Synthetic fixed-time tasks; a bounded reference example, not a production roster.', '',
            '| Scenario | Solver status | Checked cost | Change from baseline |', '| --- | --- | --- | --- |']
    for case in report['scenarios']:
        cost = case['independent_check']['total_cost'] if case['independent_check'] is not None else None
        delta = case['comparison']['cost_delta']
        text.append(f"| {case['id']} | {case['response']['status']} | {cost if cost is not None else 'unavailable'} | {delta if delta is not None else 'not comparable'} |")
    for case in report['scenarios']:
        text += ['', '## ' + case['id'], '', 'Changes: `' + json.dumps(case['changes']) + '`', '', case['comparison']['reason']]
        text += ['', '| Independent check | Status |', '| --- | --- |']
        text += [f"| {name} | {value['status']} |" for name, value in case['verification']['checks'].items()]
        if case['response']['solution'] is None:
            text += ['', 'No assignment returned. Infeasible requires a checked proof; unknown is not infeasible.']
        else:
            tasks = {t['id']: t for t in case['request']['input']['tasks']}
            text += ['', '| Task | Minutes | Worker |', '| --- | --- | --- |']
            for item in case['response']['solution']['assignments']:
                task = tasks[item['task_id']]
                text.append(f"| {task['id']} | {task['start']}–{task['end']} | {item['worker_id']} |")
    text += ['', 'Checks cover task coverage, eligibility, availability, overlap, workload and cost. The small-domain oracle checks optimality/infeasibility claims. Provider evaluation is separate. No model calls or external acceptance test.', '']
    return '\n'.join(text)


def analyze(worker_file, task_file, cost_file, scenario_file, output, run_id):
    identifier(run_id)
    destination = Path(output).absolute()
    if destination.exists() or destination.is_symlink():
        raise AnalysisError('OUTPUT_EXISTS')
    data = {key: read_bytes(path) for key, path in [('workers', worker_file), ('tasks', task_file), ('costs', cost_file), ('scenarios', scenario_file)]}
    config = parse_json(data['scenarios'].decode('utf-8-sig'))
    problem = load_problem(data['workers'], data['tasks'], data['costs'], config)
    prepared = scenarios(problem, config)
    adapter = worker_adapter()
    client = Client(adapter)
    requests = []
    for sid, value, changes in prepared:
        request = client.request(value, request_id=run_id + '-' + sid)
        validation = adapter.validate(request)
        if not validation['valid']:
            raise AnalysisError('INPUT_REJECTED:' + sid)
        requests.append((sid, request, changes))
    # All input/scenario validation precedes every execution. Exclusive output
    # creation precedes solve too, so an existing report cannot trigger a rerun.
    destination.mkdir()
    results = []
    for sid, request, changes in requests:
        response = client.execute(request['input'], request_id=request['request_id'])
        if response['kind'] != 'result':
            raise AnalysisError('EXECUTION_FAILED:' + sid)
        checked = verify_result(request, response)
        item = {'id': sid, 'changes': changes, 'request': request, 'response': response,
                'independent_check': checked, 'verification': assess(request, response),
                'provider_evaluation': adapter.evaluate(request, response['solution']) if response['solution'] is not None else None}
        item['comparison'] = comparison(results[0] if results else item, item)
        results.append(item)
    report = {'status': 'PASS', 'report_version': '0.1.0', 'input_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in data.items()},
              'scenarios': results, 'execute_calls': len(results), 'model_calls': 0,
              'scope': 'Local synthetic scenario transcript checks; PASS does not mean every scenario has a solution or external adoption.'}
    (destination / 'analysis.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (destination / 'analysis.md').write_text(markdown(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('workers', 'tasks', 'costs', 'scenarios', 'output', 'run-id'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.workers, args.tasks, args.costs, args.scenarios, args.output, args.run_id)
    except Exception as error:
        result = {'status': 'FAIL', 'code': str(error) if isinstance(error, AnalysisError) else 'ANALYSIS_FAILED',
                  'hint': 'Check CSV headers, explicit units/costs and supported scenario changes. Use a new output directory and preserve failed output; no automatic retry.'}
    print(json.dumps(result, allow_nan=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
