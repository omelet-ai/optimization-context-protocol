"""Check a new evaluation packet and solve its fixtures through installed MCP; no model."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import Client, StdioServerParameters
from conformance.assessment import digest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prepare_packet',HERE/'prepare_multidomain_evaluation.py')
preparer=importlib.util.module_from_spec(spec);spec.loader.exec_module(preparer)
SOURCE=HERE/'multidomain-evaluation.json'
EVENTS=[]


class PacketTests(unittest.TestCase):
    def test_independent_oracles_and_participant_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'packet'
            before=SOURCE.read_bytes()
            manifest=preparer.prepare(SOURCE,out)
            self.assertEqual(SOURCE.read_bytes(),before)
            self.assertEqual(manifest['cases'],12)
            self.assertEqual(manifest['planned_sessions'],48)
            answers={a['id']:a for a in json.loads((out/'reviewer/answers.json').read_text())}
            for identifier,value in [('G-R01',30),('G-R02',None),('G-W01',14),('G-W02',15),('G-I01',13),('G-I02',None)]:
                self.assertEqual(answers[identifier]['scenarios']['current']['optimal_objective'],value)
            self.assertEqual(answers['G-W02']['current_minus_baseline'],1)
            for path in (out/'participant').glob('*/case.json'):
                data=json.loads(path.read_text())
                self.assertEqual(set(data),{'id','domain','prompt','inputs'})
                self.assertNotIn('review',data)
                self.assertNotIn('optimal_objective',path.read_text())
            for relative,expected in manifest['files'].items():
                self.assertEqual(hashlib.sha256((out/relative).read_bytes()).hexdigest(),expected)
            runs=json.loads((out/'reviewer/runs.json').read_text())
            self.assertTrue(all(r['status']=='NOT_RUN' and r['task_complete'] is None for r in runs))
            self.assertEqual(manifest['model_calls'],0)
            with self.assertRaises(FileExistsError):preparer.prepare(SOURCE,out)

    def test_custom_repetition_counts_and_bad_packet_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'one'
            manifest=preparer.prepare(SOURCE,out,hosts=('claude-code','codex-cli'),repeats=1)
            self.assertEqual(manifest['planned_sessions'],24)
            criteria=json.loads((out/'reviewer/criteria.json').read_text())
            self.assertEqual(criteria['normal_completion'],{'minimum':6,'sessions_per_host':6})
            self.assertEqual(criteria['missing_data']['sessions_per_host'],3)
            with self.assertRaisesRegex(ValueError,'SELECT_TWO_DISTINCT_HOSTS'):
                preparer.prepare(SOURCE,Path(temp)/'bad',hosts=('claude-code','claude-code'))
            bad=json.loads(SOURCE.read_text());bad['cases'][1]['id']=bad['cases'][0]['id']
            path=Path(temp)/'bad.json';path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'INVALID_CASE_SET'):preparer.prepare(path,Path(temp)/'bad')
            self.assertFalse((Path(temp)/'bad').exists())

    def test_actual_mcp_solutions_diagnostics_and_comparison(self):
        asyncio.run(self.journey())

    async def journey(self):
        params=StdioServerParameters(command=str(Path(sys.executable).parent/'ocp-native'),args=['serve','--evidence'],
            env={'PATH':os.defpath,'HOME':os.environ['HOME'],'PYTHONDONTWRITEBYTECODE':'1'})
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'packet';preparer.prepare(SOURCE,out)
            answers={a['id']:a for a in json.loads((out/'reviewer/answers.json').read_text())}
            cases=json.loads(SOURCE.read_text())['cases']
            async with Client(params,read_timeout_seconds=60) as host:
                async def call(name,args,error=False):
                    response=await host.call_tool(name,args)
                    self.assertEqual(response.is_error,error,response.structured_content)
                    EVENTS.append({'tool':name,'arguments':args,'response':response.structured_content})
                    return response.structured_content
                for case in cases:
                    domain=case['domain'];identifier=case['id']
                    context=await call('ocp_native_context',{'domain':domain})
                    request=deepcopy(context['catalog']['requestTemplate'])
                    request.update(request_id=identifier,input=deepcopy(case['inputs']['current']))
                    if case['category'] in ('missing','unsupported'):
                        validation=await call('ocp_native_validate',{'domain':domain,'problem':request})
                        self.assertFalse(validation['valid'])
                        field=case['review'].get('required_question',case['review'].get('unsupported_path'))
                        self.assertTrue(any(i.get('fieldPath')==field for i in validation['issues']),validation)
                        # This scripted check stops here; model clarification behavior is still NOT_RUN.
                        continue
                    jobs={};results={}
                    for scenario,data in case['inputs'].items():
                        problem=deepcopy(request);problem.update(request_id=identifier+'-'+scenario,input=deepcopy(data))
                        self.assertTrue((await call('ocp_native_validate',{'domain':domain,'problem':problem}))['valid'])
                        submitted=await call('ocp_native_submit',{'domain':domain,'problem':problem,'idempotency_key':identifier+'-'+scenario})
                        self.assertEqual(submitted['input_validation']['request_sha256'],digest(problem))
                        job=submitted['job'];deadline=asyncio.get_running_loop().time()+60
                        while job['status'] in ('queued','running'):
                            self.assertLess(asyncio.get_running_loop().time(),deadline)
                            await asyncio.sleep(.05)
                            job=await call('ocp_native_job',{'domain':domain,'job_id':job['jobId']})
                        explained=await call('ocp_native_explain',{'domain':domain,'job_id':job['jobId']})
                        self.assertEqual(explained['verification']['status'],'PASS')
                        self.assertEqual(explained['explanation_basis']['current']['request_sha256'],digest(problem))
                        expected=answers[identifier]['scenarios'][scenario]['optimal_objective']
                        actual=explained['facts']['objective']['value']
                        if expected is None:
                            self.assertIsNone(actual)
                            self.assertTrue(explained['facts']['infeasibility_verified'])
                        elif domain=='routing-basic':
                            self.assertGreaterEqual(actual,expected)
                        else:self.assertEqual(actual,expected)
                        jobs[scenario]=job['jobId'];results[scenario]=explained
                    if case['category']=='compare':
                        comparison=await call('ocp_native_explain',{'domain':domain,'job_id':jobs['current'],'baseline_job_id':jobs['baseline']})
                        self.assertEqual(comparison['comparison']['difference'],answers[identifier]['current_minus_baseline'])
                        self.assertEqual(comparison['explanation_basis']['baseline']['job_id'],jobs['baseline'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PacketTests))
    summary={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'fixture_cases':12,'model_calls':0,'actual_host_acceptance':'NOT_RUN','scope':'Packet integrity, independent oracles and scripted installed MCP'}
    Path('multidomain-test-result.json').write_text(json.dumps(summary,indent=2)+'\n')
    Path('multidomain-mcp-events.json').write_text(json.dumps(EVENTS,indent=2)+'\n')
    print(json.dumps(summary))
    raise SystemExit(not result.wasSuccessful())
