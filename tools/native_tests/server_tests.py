"""Actual three-domain execution plus labelled lifecycle protocol fixtures."""
from copy import deepcopy
from functools import partial
import json
import os
from pathlib import Path
import time
import unittest

from ocp_candidate.native import NativeError, NativeClient
from ocp_runtime.native_server import LocalAPI, Registration
from ocp_runtime.native_domain import ReferenceDomain
from ocp_runtime.providers import make_provider

INPUTS=json.loads(Path('inputs.json').read_text())


def blocking_fixture(marker, problem):
    """Only a process-cancellation fixture, never a claimed optimization engine."""
    Path(marker).write_text(str(os.getpid()))
    time.sleep(90)
    raise RuntimeError('Cancellation fixture should never finish')


class Servers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local=LocalAPI();cls.local.__enter__();cls.transcripts={}

    @classmethod
    def tearDownClass(cls):
        cls.local.__exit__();Path('python-transcripts.json').write_text(json.dumps(cls.transcripts))

    def request(self, domain):
        api=self.local.client(domain);catalog=api.capabilities();request=catalog['requestTemplate']
        request.update(input=deepcopy(INPUTS[catalog['domainProfile']['id']]),request_id='python-'+domain)
        return api,catalog,request

    def actual_solve(self,domain,expected):
        api,catalog,request=self.request(domain)
        self.assertEqual(catalog['contractVersion'],'1')
        self.assertEqual(catalog['execution']['mode'],'async-jobs')
        self.assertTrue(api.validate(request)['valid'])
        requirements=api.resolve_data_requirements({'configuration':request['configuration']})
        self.assertTrue(requirements['required'])
        self.assertEqual(api.resolve_configuration({'configuration':request['configuration']})['resolved']['configuration'],request['configuration'])
        result=api.solve(request,tenant='engineer',idempotency_key=domain,timeout=60)
        self.assertEqual(result['job']['status'],'succeeded')
        response=result['result']['result'];self.assertEqual(response['metrics'][0]['value'],expected)
        evaluation=api.evaluate({'jobId':result['job']['jobId']},tenant='engineer')
        self.assertEqual(evaluation['evaluation']['metrics'][0]['value'],expected)
        self.transcripts[domain]={'request':request,'response':response}

    def test_01_routing_actual(self):self.actual_solve('routing-basic',18)
    def test_02_worker_actual(self):self.actual_solve('worker-scheduling',7)
    def test_03_inventory_actual(self):self.actual_solve('inventory-replenishment',16)

    def test_04_malformed_inputs_never_queued(self):
        before=len(self.local.app.state.native_store.keys)
        for domain in self.local.app.state.domain_ids:
            api,_,request=self.request(domain);request['input']={}
            self.assertFalse(api.validate(request)['valid'])
            with self.assertRaisesRegex(NativeError,'INVALID_PROBLEM'):api.submit(request,tenant='engineer',idempotency_key='invalid')
        self.assertEqual(len(self.local.app.state.native_store.keys),before)

    def test_05_replay_conflict_and_tenant(self):
        api,_,request=self.request('worker-scheduling')
        first=api.submit(request,tenant='engineer',idempotency_key='worker-scheduling')
        self.assertTrue(first['replayed'])
        changed=deepcopy(request);changed['request_id']='changed'
        with self.assertRaisesRegex(NativeError,'IDEMPOTENCY_CONFLICT'):api.submit(changed,tenant='engineer',idempotency_key='worker-scheduling')
        for op in [api.job,api.result,api.cancel]:
            with self.assertRaisesRegex(NativeError,'JOB_NOT_FOUND'):op(first['job']['jobId'],tenant='other')

    def test_06_auth_and_domain_identity(self):
        api,_,request=self.request('worker-scheduling')
        bad=NativeClient(api.base,'wrong')
        with self.assertRaisesRegex(NativeError,'UNAUTHENTICATED'):bad.capabilities()
        self.assertFalse(self.local.client('routing-basic').validate(request)['valid'])
        with self.assertRaisesRegex(NativeError,'UNSUPPORTED_CONFIGURATION'):
            api.resolve_configuration({'configuration':{'unknown':True}})

    def test_07_running_cancel_really_stops_process(self):
        marker=str(Path('cancel-process.pid').resolve())
        r=Registration(ReferenceDomain(make_provider('worker.scheduling'),problem_type='cancel-fixture'),partial(blocking_fixture,marker))
        with LocalAPI([r]) as local:
            api=local.client('cancel-fixture');request=api.capabilities()['requestTemplate'];request['input']=INPUTS['worker.scheduling']
            job=api.submit(request,tenant='engineer',idempotency_key='cancel')['job'];deadline=time.monotonic()+20
            while not Path(marker).exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(Path(marker).exists());pid=int(Path(marker).read_text())
            self.assertEqual(api.job(job['jobId'],tenant='engineer')['status'],'running')
            with self.assertRaisesRegex(NativeError,'JOB_NOT_FINISHED'):api.result(job['jobId'],tenant='engineer')
            api.cancel(job['jobId'],tenant='engineer')
            self.assertEqual(api.wait(job['jobId'],tenant='engineer')['status'],'cancelled')
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)
            with self.assertRaisesRegex(NativeError,'JOB_CANCELLED'):api.result(job['jobId'],tenant='engineer')

    def test_08_infeasible_is_domain_proof_not_transport_failure(self):
        api,_,request=self.request('worker-scheduling');request['request_id']='infeasible'
        for worker in request['input']['workers']:worker['max_minutes']=0
        value=api.solve(request,tenant='engineer',idempotency_key='infeasible')
        self.assertEqual(value['job']['status'],'infeasible');self.assertIsNone(value['result']['result']['solution'])
        self.transcripts['infeasible']={'request':request,'response':value['result']['result']}
        with self.assertRaisesRegex(NativeError,'NO_SOLUTION'):api.evaluate({'jobId':value['job']['jobId']},tenant='engineer')

    def test_09_local_limit_and_same_key_replay(self):
        with LocalAPI(max_jobs=1) as local:
            api=local.client('worker-scheduling');request=api.capabilities()['requestTemplate'];request['input']=INPUTS['worker.scheduling']
            api.submit(request,tenant='engineer',idempotency_key='one')
            self.assertTrue(api.submit(request,tenant='engineer',idempotency_key='one')['replayed'])
            with self.assertRaisesRegex(NativeError,'LOCAL_JOB_LIMIT'):api.submit(request,tenant='engineer',idempotency_key='two')

    def test_10_unknown_status_keeps_nulls(self):
        from ocp_runtime.native_domain import run_provider
        from ocp_planning import worker
        from ocp_planning.adapter import PlanningAdapter
        ticks=iter([0,10]);provider=PlanningAdapter(worker,clock=lambda:next(ticks))
        _,_,request=self.request('worker-scheduling')
        value=run_provider(provider,request)
        self.assertEqual(value['status'],'succeeded');self.assertEqual(value['result']['status'],'unknown')
        self.assertIsNone(value['result']['solution']);self.assertEqual(value['result']['metrics'],[])

    def test_11_optional_operations_not_advertised(self):
        for domain in self.local.app.state.domain_ids:
            c=self.local.client(domain).capabilities()
            self.assertEqual(c['execution']['optionalOperations'],[])
            self.assertIsNone(c['execution']['stateEnvelope'])

    def test_12_new_domain_registration_does_not_change_server_dispatch(self):
        with self.assertRaisesRegex(ValueError,'INVALID_DOMAIN_REGISTRATION'):
            r=Registration(ReferenceDomain(make_provider('worker.scheduling'),problem_type='same'),None)
            LocalAPI([r,r])

    def test_13_units_versions_and_constraints_not_guessed(self):
        for domain,field in [('routing-basic','load_unit'),('worker-scheduling','time_unit'),('inventory-replenishment','period_unit')]:
            api,_,original=self.request(domain)
            changed=deepcopy(original);changed['input'][field]='invented-unit'
            self.assertFalse(api.validate(changed)['valid'])
            changed=deepcopy(original);changed['domain_profile']['version']='9.0.0'
            self.assertFalse(api.validate(changed)['valid'])
            changed=deepcopy(original);changed['configuration']['constraints'].append('unsupported')
            with self.assertRaisesRegex(NativeError,'INVALID_PROBLEM'):
                api.submit(changed,tenant='engineer',idempotency_key='unsupported-'+domain)


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Servers))
    print(json.dumps({'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped)}))
    raise SystemExit(not r.wasSuccessful())
