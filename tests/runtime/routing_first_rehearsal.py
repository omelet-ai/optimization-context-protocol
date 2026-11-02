"""Installed routing MCP exercise. Synthetic agent rehearsal, not human adoption."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import time

from mcp import Client, StdioServerParameters
from conformance.assessment import assess


DATA = {
    'depot': 'H', 'load_unit': 'kg',
    'visits': [{'id': name, 'demand': demand} for name, demand in zip('ABCD', [2, 3, 1, 2])],
    'vehicles': [{'id': 'V1', 'capacity': 5}, {'id': 'V2', 'capacity': 5}],
    'matrix': {'node_ids': ['H', 'A', 'B', 'C', 'D'], 'unit': 'meter',
               'model': 'explicit_matrix', 'rounding': 'none',
               'values': [[0,4,7,9,6], [4,0,3,6,5], [7,3,0,4,4], [9,6,4,0,3], [6,5,4,3,0]]}}


def independent_cost(data, solution):
    """Exercise-specific arithmetic; imports no solver/checker implementation."""
    positions = {name: index for index, name in enumerate(data['matrix']['node_ids'])}
    demands = {v['id']: v['demand'] for v in data['visits']}
    capacities = {v['id']: v['capacity'] for v in data['vehicles']}
    seen, vehicles, rows = [], [], []
    for route in solution['routes']:
        vehicle, stops = route['vehicle_id'], route['visits']
        assert vehicle in capacities and vehicle not in vehicles
        assert all(stop in demands for stop in stops)
        load = sum(demands[stop] for stop in stops)
        assert load <= capacities[vehicle]
        path = [data['depot'], *stops, data['depot']]
        distance = sum(data['matrix']['values'][positions[a]][positions[b]] for a,b in zip(path,path[1:]))
        rows.append({'vehicle': vehicle, 'visits': stops, 'load_kg': load, 'distance_m': distance})
        seen.extend(stops); vehicles.append(vehicle)
    assert sorted(seen) == sorted(demands) and sorted(vehicles) == sorted(capacities)
    return sum(row['distance_m'] for row in rows), rows


def small_oracle(data):
    assert len(data['visits']) == 4 and len(data['vehicles']) == 2
    best = None
    for order in itertools.permutations(v['id'] for v in data['visits']):
        for split in range(5):
            routes = {'routes': [{'vehicle_id': 'V1', 'visits': list(order[:split])},
                                  {'vehicle_id': 'V2', 'visits': list(order[split:])}]}
            try:
                cost, _ = independent_cost(data, routes)
            except AssertionError:
                continue
            best = cost if best is None else min(best, cost)
    return best


async def exercise(mode, output):
    started = time.monotonic()
    events, checks, outcomes = [], [], {}
    output.mkdir(exist_ok=False, parents=True)
    home = output/'home'; home.mkdir()
    candidate = mode == 'candidate'
    args = ['-I', '-B', '-m', 'ocp_runtime.native_mcp']
    if candidate:
        args = ['-I', '-B', '-m', 'ocp_runtime.native_cli', 'serve', '--domain', 'routing-basic', '--evidence']
    parameters = StdioServerParameters(command=sys.executable, args=args,
        env={'PATH': os.defpath, 'HOME': str(home), 'PYTHONDONTWRITEBYTECODE': '1'})
    report = {'status': 'INCOMPLETE', 'mode': mode, 'synthetic': True,
              'scope': 'Agent/script first-user rehearsal; not blind or external-human acceptance',
              'additional_model_calls': 0, 'external_humans': 0, 'checks': checks, 'outcomes': outcomes}
    try:
        async with Client(parameters, read_timeout_seconds=60) as host:
            async def call(name, arguments, error=False):
                response = await host.call_tool(name, arguments)
                value = response.structured_content
                events.append({'tool': name, 'arguments': deepcopy(arguments), 'is_error': response.is_error, 'response': value})
                assert response.is_error == error, (name, value)
                return value
            listing = await call('ocp_native_context', {})
            assert listing['availableDomains'] == (['routing-basic'] if candidate else
                ['routing-basic', 'worker-scheduling', 'inventory-replenishment'])
            tools = [t.name for t in (await host.list_tools()).tools]
            assert len(tools) == (11 if candidate else 8)
            context = await call('ocp_native_context', {'domain': 'routing-basic'})
            catalog = context['catalog']
            requirements = await call('ocp_native_requirements', {'domain': 'routing-basic', 'selection': catalog['selectionTemplate']})
            assert requirements and catalog['domainProfile'] == {'id': 'routing.basic', 'version': '0.1.0'}
            assert not any(e['tool'] == 'ocp_native_submit' for e in events)
            checks.append('discovery_and_requirements_without_solve')
            if candidate:
                assert context['evidence']['capability_scope']['configured_domains'] == ['routing-basic']
                forbidden = await call('ocp_native_context', {'domain': 'worker-scheduling'}, error=True)
                assert forbidden['code'] == 'UNSUPPORTED_DOMAIN'
                checks.append('only_selected_domain_advertised')
            def problem(data, label):
                value = deepcopy(catalog['requestTemplate'])
                value.update(input=deepcopy(data), request_id='routing-rehearsal-'+label)
                return value
            for label in ['missing-matrix', 'time-window', 'wrong-unit']:
                bad = problem(DATA, label)
                if label == 'missing-matrix': del bad['input']['matrix']
                elif label == 'time-window': bad['input']['visits'][0]['time_window'] = [480,540]
                else: bad['input']['matrix']['unit'] = 'km'
                result = await call('ocp_native_validate', {'domain': 'routing-basic', 'problem': bad})
                assert result['valid'] is False and result['issues']
                checks.append(label+'_rejected_without_submit')
            async def solve(data, label):
                request = problem(data, label)
                prep = None
                if candidate:
                    prep = await call('ocp_native_prepare', {'domain': 'routing-basic', 'problem': request,
                        'requirements': [], 'source_text': 'Synthetic explicit matrix; preserve every mandatory visit and kg capacity.', 'detail': 'compact'})
                    assert prep['problem'] == request
                    request = prep['problem']
                validated = await call('ocp_native_validate', {'domain': 'routing-basic', 'problem': request})
                assert validated['valid']
                arguments = {'domain': 'routing-basic', 'problem': request, 'idempotency_key': request['request_id']}
                submitted = await call('ocp_native_submit', arguments)
                job = submitted['job']; deadline = time.monotonic()+30
                while job['status'] in ('queued', 'running'):
                    assert time.monotonic() < deadline, 'JOB_TIMEOUT'
                    await asyncio.sleep(.05)
                    job = await call('ocp_native_job', {'domain': 'routing-basic', 'job_id': job['jobId']})
                assert job['status'] in ('succeeded', 'infeasible'), job
                response = (await call('ocp_native_result', {'domain': 'routing-basic', 'job_id': job['jobId']}))['result']
                check = assess(request, response); assert check['status'] == 'PASS', check
                replay = await call('ocp_native_submit', arguments)
                assert replay['replayed'] and replay['job']['jobId'] == job['jobId']
                outcome = {'request': request, 'response': response, 'job_id': job['jobId'], 'check': check}
                if candidate:
                    explained = await call('ocp_native_explain', {'domain': 'routing-basic', 'job_id': job['jobId'], 'preparation_id': prep['preparation_id']})
                    assert explained['verification']['status'] == 'PASS'
                    assert explained['comparison']['difference'] is None
                    outcome['explanation'] = explained
                outcomes[label] = outcome
                checks.extend([label+'_independently_checked', label+'_idempotent_replay'])
                return outcome
            base = await solve(DATA, 'base')
            changed_data = deepcopy(DATA); changed_data['vehicles'][0]['capacity'] = 8
            changed = await solve(changed_data, 'larger-vehicle')
            for label, data, outcome, expected in [('base',DATA,base,32), ('larger-vehicle',changed_data,changed,20)]:
                assert outcome['response']['status'] == 'feasible'
                cost, routes = independent_cost(data, outcome['response']['solution'])
                assert cost == outcome['response']['metrics'][0]['value'] == small_oracle(data) == expected
                outcome['exercise_arithmetic'] = {'distance_m': cost, 'routes': routes,
                    'small_fixture_oracle_m': expected, 'solver_optimality_claim': False}
                checks.append(label+'_separate_arithmetic_and_small_oracle')
            if candidate:
                compared = await call('ocp_native_explain', {'domain': 'routing-basic', 'job_id': changed['job_id'], 'baseline_job_id': base['job_id']})
                assert compared['comparison']['status'] == 'VERIFIED' and compared['comparison']['difference'] == -12
                report['comparison'] = compared['comparison']; checks.append('two_checked_jobs_comparison')
                forbidden = await call('ocp_native_submit', {'domain': 'worker-scheduling', 'problem': base['request'], 'idempotency_key': 'not-selected'}, error=True)
                assert forbidden['code'] == 'UNSUPPORTED_DOMAIN'; checks.append('unselected_domain_cannot_submit')
            impossible = deepcopy(DATA)
            for vehicle in impossible['vehicles']: vehicle['capacity'] = 3
            infeasible = await solve(impossible, 'capacity-infeasible')
            assert infeasible['response']['status'] == 'infeasible' and infeasible['response']['solution'] is None
            assert infeasible['check']['checks']['objective_recomputation']['value'] is None
            checks.append('proved_infeasible_preserves_null')
            for label in ['wrong-cost', 'duplicate-visit']:
                corrupt = deepcopy(base['response'])
                if label == 'wrong-cost': corrupt['metrics'][0]['value'] += 1
                else: corrupt['solution']['routes'][0]['visits'].append('A')
                assert assess(base['request'], corrupt)['status'] == 'FAIL'
                checks.append(label+'_checker_rejects')
            report.update(status='PASS', tools=tools, checks_run=len(checks), real_jobs=3,
                          elapsed_seconds=round(time.monotonic()-started,2))
    except Exception as error:
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['test_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (output/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('outcomes','tools')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['public','candidate'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.mode, args.output))
