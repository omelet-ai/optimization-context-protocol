"""CSV input and checked reports for a small fixed-time inspection application.

This application format is not an OCP profile or a replacement for project.py.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys


class InputError(ValueError):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code, self.details = code, details


def reject(code, path, row, field):
    raise InputError(code, file=path.name, row=row, field=field)


def table(path, headers, maximum):
    if path.is_symlink(): raise InputError('CSV_SYMLINK', file=path.name)
    try:
        with path.open('rb') as stream: raw = stream.read(65537)
    except OSError: raise InputError('CSV_UNREADABLE', file=path.name) from None
    if len(raw) > 65536: raise InputError('CSV_TOO_LARGE', file=path.name)
    try: content = raw.decode('utf-8-sig')
    except UnicodeError: raise InputError('CSV_UTF8_REQUIRED', file=path.name) from None
    reader = csv.reader(io.StringIO(content, newline=''), strict=True)
    rows = []
    try:
        if next(reader, None) != headers: reject('CSV_HEADER', path, 1, ','.join(headers))
        for values in reader:
            line = reader.line_num
            if len(values) != len(headers): reject('CSV_COLUMNS', path, line, '*')
            if len(rows) >= maximum: reject('CSV_ROW_LIMIT', path, line, '*')
            for key, value in zip(headers, values):
                if not value or value != value.strip(): reject('CSV_EMPTY_OR_WHITESPACE', path, line, key)
            rows.append((line, dict(zip(headers, values))))
    except csv.Error: reject('CSV_SYNTAX', path, reader.line_num, '*')
    return rows, hashlib.sha256(raw).hexdigest()


def identifier(value, path, row, field):
    # Bounded ASCII identifiers also prevent spreadsheet formula output.
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', value): reject('CSV_ID', path, row, field)
    return value


def integer(value, path, row, field, maximum):
    if not re.fullmatch(r'0|[1-9][0-9]*', value) or len(value) > 6:
        reject('CSV_INTEGER', path, row, field)
    number = int(value)
    if number > maximum: reject('CSV_RANGE', path, row, field)
    return number


def clock(value, path, row, field):
    if value == '24:00' and field == 'end': return 1440
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value): reject('CSV_TIME', path, row, field)
    hour, minute = map(int, value.split(':'))
    return 60 * hour + minute


def interval(values, path, row):
    start, end = [clock(values[k], path, row, k) for k in ['start', 'end']]
    if start >= end: reject('CSV_INTERVAL', path, row, 'end')
    return start, end


def problem(workers_path, tasks_path, costs_path):
    workers, whash = table(workers_path, ['worker_id','start','end','max_minutes'], 4)
    tasks, thash = table(tasks_path, ['task_id','start','end'], 8)
    costs, chash = table(costs_path, ['task_id','worker_id','cost'], 32)
    ws, ts = {}, {}
    for line, value in workers:
        key = identifier(value['worker_id'], workers_path, line, 'worker_id')
        if key in ws: reject('CSV_DUPLICATE', workers_path, line, 'worker_id')
        start, end = interval(value, workers_path, line)
        ws[key] = {'id':key, 'availability':[{'start':start,'end':end}],
                   'max_minutes':integer(value['max_minutes'], workers_path, line, 'max_minutes',1440)}
    for line, value in tasks:
        key = identifier(value['task_id'], tasks_path, line, 'task_id')
        if key in ts: reject('CSV_DUPLICATE', tasks_path, line, 'task_id')
        start, end = interval(value, tasks_path, line)
        ts[key] = {'id':key,'start':start,'end':end,'eligible_workers':[],'costs':{}}
    if not ws or not ts: raise InputError('CSV_EMPTY_TABLE', file=(workers_path if not ws else tasks_path).name, row=2)
    for line, value in costs:
        tid, wid = value['task_id'], value['worker_id']
        if tid not in ts: reject('CSV_UNKNOWN_TASK', costs_path, line, 'task_id')
        if wid not in ws: reject('CSV_UNKNOWN_WORKER', costs_path, line, 'worker_id')
        if wid in ts[tid]['costs']: reject('CSV_DUPLICATE', costs_path, line, 'worker_id')
        ts[tid]['costs'][wid] = integer(value['cost'], costs_path, line, 'cost',100000)
        ts[tid]['eligible_workers'].append(wid)
    result = {'time_unit':'minute','cost_unit':'cost_unit','workers':list(ws.values()),'tasks':list(ts.values())}
    from conformance.worker import validate_problem
    validate_problem(result)
    return result, {'workers':whash,'tasks':thash,'costs':chash}


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def reserve(output):
    try: output.mkdir(parents=True, exist_ok=False)
    except FileExistsError: raise InputError('OUTPUT_EXISTS') from None


def prepare(workers, tasks, costs, output):
    data, hashes = problem(workers, tasks, costs)
    reserve(output)
    save(output / 'input.json', data)
    save(output / 'project.json', {'format':'ocp-project/1','domain':'worker-scheduling',
         'profile':{'id':'worker.scheduling','version':'0.1.0'},'input':'input.json'})
    save(output / 'IMPORT.json', {'format':'ocp-inspection-csv/1','source_sha256':hashes,
         'time_origin':'same local day 00:00; no timezone or DST conversion',
         'cost_meaning':'integer cost units per whole task assignment, not hourly rates',
         'eligibility':'only pairs explicitly listed in the costs table are eligible',
         'input_sha256':hashlib.sha256((output/'input.json').read_bytes()).hexdigest()})
    save(output / 'OWNER_REVIEW.json', {'status':'NOT_RUN','reviewer':None,'reviewed_run':None,
         'criteria':{key:'NOT_RUN' for key in ['business_scope','data_meaning','assignment_usability','change_explanation','unsupported_rules']},
         'findings':[], 'note':'Automation does not fill owner acceptance. Synthetic rehearsal only.'})
    return {'status':'PREPARED','directory':str(output),'workers':len(data['workers']),'tasks':len(data['tasks']),
            'execute_calls':0,'model_calls':0}


def project_app():
    # Fixed, locally installed application file; never selected by CSV or transcript.
    spec = importlib.util.spec_from_file_location('inspection_project', Path(__file__).with_name('project.py'))
    app = importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    return app


def hhmm(minutes):
    return f'{minutes//60:02d}:{minutes%60:02d}'


def write_csv(path, fields, rows):
    with path.open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=fields);writer.writeheader();writer.writerows(rows)


def report(run, output):
    reviewed = project_app().review(run)
    if reviewed['request']['domain_profile'] != {'id':'worker.scheduling','version':'0.1.0'}:
        raise InputError('INSPECTION_PROFILE_REQUIRED')
    data, response = reviewed['request']['input'], reviewed['response']
    # This report has the CSV app's single-day scope, not the full profile's week horizon.
    for item, key in [(w,'id') for w in data['workers']] + [(t,'id') for t in data['tasks']]:
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', item[key]): raise InputError('REPORT_ID_UNSUPPORTED')
    if any(t['end'] > 1440 for t in data['tasks']): raise InputError('REPORT_DAY_UNSUPPORTED')
    tasks = {t['id']:t for t in data['tasks']}
    assignments, loads = [], []
    if response['solution'] is not None:
        for entry in response['solution']['assignments']:
            t, w = tasks[entry['task_id']], entry['worker_id']
            assignments.append({'task_id':t['id'],'start':hhmm(t['start']),'end':hhmm(t['end']),
                                'worker_id':w,'minutes':t['end']-t['start'],'cost':t['costs'][w]})
        assignments.sort(key=lambda row:(row['start'],row['task_id']))
        for worker in data['workers']:
            owned = [a for a in assignments if a['worker_id']==worker['id']]
            used = sum(a['minutes'] for a in owned)
            loads.append({'worker_id':worker['id'],'assigned_minutes':used,'max_minutes':worker['max_minutes'],
                          'remaining_minutes':worker['max_minutes']-used,'cost':sum(a['cost'] for a in owned)})
    result = {'status':'PASS','solution_status':response['status'],'objective_value':reviewed['summary']['objective_value'],
              'objective_unit':data['cost_unit'],'assignments':assignments if response['solution'] is not None else None,
              'worker_loads':loads if response['solution'] is not None else None,
              'checks':reviewed['independent_check']['checks'],'human_acceptance':'NOT_RUN',
              'record_manifest_sha256':hashlib.sha256((run/'files.sha256.json').read_bytes()).hexdigest(),
              'execute_calls':0,'model_calls':0}
    reserve(output)
    save(output/'report.json',result)
    shown_cost = str(result['objective_value']) if result['objective_value'] is not None else 'unavailable (null)'
    lines=['# Inspection assignment review','',f"Solution: **{response['status']}**. Cost: **{shown_cost}** {data['cost_unit']}.",'',
           'PASS means the saved transcript passed independent checking. It does not mean business acceptance or authenticated engine execution.','']
    if assignments:
        write_csv(output/'assignments.csv',['task_id','start','end','worker_id','minutes','cost'],assignments)
        write_csv(output/'worker-loads.csv',['worker_id','assigned_minutes','max_minutes','remaining_minutes','cost'],loads)
        lines += ['| Task | Time | Worker | Cost |','| --- | --- | --- | --- |']
        lines += [f"| {r['task_id']} | {r['start']}–{r['end']} | {r['worker_id']} | {r['cost']} |" for r in assignments]
        lines += ['', '| Worker | Assigned minutes | Maximum | Remaining |', '| --- | --- | --- | --- |']
        lines += [f"| {r['worker_id']} | {r['assigned_minutes']} | {r['max_minutes']} | {r['remaining_minutes']} |" for r in loads]
    else:
        lines += ['No assignment or load CSV is emitted: no solution was returned. Cost and loads remain null.']
    lines += ['', '## Verification scope','', 'Availability, eligibility, coverage, overlap, workload and total cost are checked.',
              'Optimality/infeasibility proof is bounded enumeration for at most 8 tasks and 4 workers.',
              'Travel, breaks, fairness, uncertainty, labor rules and production scheduling are not assessed.',
              'Record hashes are not signatures; no human approval or execution attestation is claimed.','']
    (output/'REVIEW.md').write_text('\n'.join(lines))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare')
    for name in ['workers','tasks','costs','output']:p.add_argument('--'+name,type=Path,required=True)
    p=commands.add_parser('report');p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        value=prepare(args.workers,args.tasks,args.costs,args.output) if args.command=='prepare' else report(args.run,args.output)
        print(json.dumps(value,allow_nan=False));return 0
    except Exception as error:
        result={'status':'FAIL','code':getattr(error,'code','INSPECTION_COMMAND_FAILED'),'execute_calls':0,'model_calls':0}
        hints = {'CSV_ID':'Use an ASCII identifier starting with a letter (letters, digits, underscore or hyphen; at most 64 characters). Keep display names in your application.',
                 'CSV_TIME':'Use HH:MM on one local day, for example 09:00; 24:00 is allowed only as an end time.',
                 'CSV_INTEGER':'Use a non-negative integer. Cost is per complete assignment in one declared unit; convert all monetary values consistently before importing.',
                 'CSV_HEADER':'Use the exact header fields shown in field, in that order.',
                 'CSV_COLUMNS':'Use one value for each header field; remove blank rows and extra columns.',
                 'CSV_EMPTY_OR_WHITESPACE':'Provide a non-empty value without surrounding whitespace.',
                 'OUTPUT_EXISTS':'Preserve the existing project or report and choose a new output directory.'}
        if result['code'] in hints: result['hint']=hints[result['code']]
        result.update(getattr(error,'details',{}));print(json.dumps(result,allow_nan=False));return 1


if __name__=='__main__':raise SystemExit(main())
