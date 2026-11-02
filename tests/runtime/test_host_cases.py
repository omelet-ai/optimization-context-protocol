"""Rehearse the 20 shared cases through installed stdio MCP, without a model.

Also observe the real local job store when invalid submissions bypass validate.
Host conversations and external participants are measured separately.
"""
import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest

from mcp import Client, StdioServerParameters
from ocp_candidate.native import NativeError
from ocp_runtime.native_server import LocalAPI
from conformance.assessment import digest

EVALUATION = None
OUTCOMES = []


class HostCases(unittest.TestCase):
    def test_rejected_inputs_create_no_jobs(self):
        answers = json.loads((EVALUATION/'reviewer/answers.json').read_text())
        with LocalAPI() as local:
            client = local.client('worker-scheduling')
            catalog = client.capabilities()
            self.assertEqual(len(local.app.state.native_store.ids), 0)
            for answer in answers:
                if answer['group'] == 'normal':
                    continue
                with self.subTest(case=answer['id']):
                    request = deepcopy(catalog['requestTemplate'])
                    request.update(request_id=answer['id'], input=json.loads(
                        (EVALUATION/'participant'/answer['id']/'input.json').read_text()))
                    with self.assertRaises(NativeError) as caught:
                        client.submit(request, tenant='case-reviewer', idempotency_key=answer['id'])
                    self.assertEqual(caught.exception.code, 'INVALID_PROBLEM')
                    self.assertEqual(len(local.app.state.native_store.ids), 0)

    def test_twenty_cases_through_mcp(self):
        asyncio.run(self.exercise())

    async def exercise(self):
        parameters = StdioServerParameters(command=sys.executable,
            args=['-I','-B','-m','ocp_runtime.native_mcp','--verification'],
            env={'PATH':os.defpath,'HOME':os.environ['HOME'],'PYTHONDONTWRITEBYTECODE':'1'})
        answers = json.loads((EVALUATION/'reviewer/answers.json').read_text())
        async with Client(parameters, read_timeout_seconds=90) as host:
            async def call(tool, arguments, error=False):
                result = await host.call_tool(tool, arguments)
                self.assertEqual(result.is_error, error, result.structured_content)
                return result.structured_content
            catalog = (await call('ocp_native_context', {'domain':'worker-scheduling'}))['catalog']
            for answer in answers:
                with self.subTest(case=answer['id']):
                    events = []
                    async def recorded(tool, arguments, error=False):
                        value = await call(tool, arguments, error)
                        events.append({'tool':tool,'arguments':arguments,'response':value,'is_error':error})
                        return value
                    request = deepcopy(catalog['requestTemplate'])
                    data = json.loads((EVALUATION/'participant'/answer['id']/'input.json').read_text())
                    self.assertEqual(digest(data), answer['input_sha256'])
                    request.update(request_id=answer['id'], input=data)
                    validation = await recorded('ocp_native_validate', {'domain':'worker-scheduling','problem':request})
                    arguments = {'domain':'worker-scheduling','problem':request,'idempotency_key':answer['id']}
                    if answer['group'] != 'normal':
                        self.assertFalse(validation['valid'])
                        expected_paths = {
                            'M01': '/tasks/0/costs/alex', 'M02': '/time_unit',
                            'M03': '/workers/0/max_minutes', 'M04': '/workers/0/availability',
                            'M05': '/tasks/0/end', 'U01': '/breaks', 'U02': '/fairness',
                            'U03': '/overtime', 'U04': '/travel_time', 'U05': '/shift_generation'}
                        self.assertEqual(validation['issues'][0]['fieldPath'], expected_paths[answer['id']])
                        rejected = await recorded('ocp_native_submit', arguments, True)
                        self.assertEqual(rejected['code'], 'INVALID_PROBLEM')
                        # Reviewer clarification repairs only missing fields; no model guessed a value.
                        if answer['group'] == 'missing':
                            repaired = deepcopy(request)
                            for missing in answer['must_ask']:
                                parent = repaired['input']
                                for part in missing['path'][:-1]: parent = parent[part]
                                parent[missing['path'][-1]] = missing['clarification']
                            valid = await recorded('ocp_native_validate', {'domain':'worker-scheduling','problem':repaired})
                            self.assertTrue(valid['valid'])
                        OUTCOMES.append({'case':answer['id'],'group':answer['group'],'status':'PASS',
                                         'outcome':'rejected_before_job','events':events})
                        continue
                    self.assertTrue(validation['valid'])
                    job = (await recorded('ocp_native_submit', arguments))['job']
                    deadline = asyncio.get_running_loop().time()+60
                    while job['status'] not in ('succeeded','infeasible','failed','cancelled'):
                        self.assertLess(asyncio.get_running_loop().time(), deadline)
                        await asyncio.sleep(.05)
                        job = await recorded('ocp_native_job', {'domain':'worker-scheduling','job_id':job['jobId']})
                    response = (await recorded('ocp_native_result', {'domain':'worker-scheduling','job_id':job['jobId']}))['result']
                    report = await recorded('ocp_native_verify', {'domain':'worker-scheduling','job_id':job['jobId']})
                    evidence = report['verification']
                    self.assertEqual(evidence['status'], 'PASS')
                    self.assertEqual(response['status'], answer['result_status'])
                    self.assertEqual(evidence['checks']['objective_recomputation']['value'], answer['objective_value'])
                    self.assertEqual(evidence['request_sha256'], digest(request))
                    self.assertEqual(evidence['response_sha256'], digest(response))
                    replay = await recorded('ocp_native_submit', arguments)
                    self.assertTrue(replay['replayed'])
                    self.assertEqual(replay['job']['jobId'], job['jobId'])
                    OUTCOMES.append({'case':answer['id'],'group':answer['group'],'status':'PASS',
                        'outcome':response['status'],'objective_value':answer['objective_value'],'events':events})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    EVALUATION = args.evaluation.resolve()
    # Reserve the report before testing; a failed or interrupted run is retained.
    with args.report.open('x') as stream:
        json.dump({'status':'INCOMPLETE'},stream)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HostCases))
    report = {'status':'PASS' if result.wasSuccessful() and len(OUTCOMES)==20 else 'FAIL',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':len(result.skipped),'cases_checked':len(OUTCOMES),'cases':OUTCOMES,
        'model_calls':0,'actual_host_acceptance':'NOT_RUN','human_acceptance':'NOT_RUN',
        'scope':'Installed SDK/stdIO MCP and local job boundary with synthetic inputs'}
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
    raise SystemExit(report['status']!='PASS')
