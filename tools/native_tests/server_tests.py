"""Actual three-domain execution plus labelled lifecycle protocol fixtures."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import asyncio
from importlib.metadata import version
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

import httpx2 as httpx
from foundry_capability_contract.testing.suite import ContractSuite
from foundry_capability_contract.testing.openapi import SchemaChecker

from ocp_candidate.native import NativeError, NativeClient, native_contract
from ocp_runtime.native_server import LocalAPI, Registration, create_native_app, reference_domains, WorkerPool
from ocp_runtime.native_domain import ReferenceDomain, solve_reference
from ocp_runtime.providers import make_provider

INPUTS=json.loads(Path('inputs.json').read_text())


def blocking_fixture(marker, problem):
    """Only a process-cancellation fixture, never a claimed optimization engine."""
    Path(marker).write_text(str(os.getpid()))
    time.sleep(90)
    raise RuntimeError('Cancellation fixture should never finish')


def fault_fixture(marker, problem):
    """Labelled fault injection; the recovery path runs the actual reference solver."""
    mode = problem['request_id']
    if mode in ('fixture-crash', 'fixture-exception', 'fixture-block'):
        Path(marker).write_text(str(os.getpid()))
    if mode == 'fixture-crash': os._exit(23)
    if mode == 'fixture-exception': raise RuntimeError('synthetic-private-solver-detail')
    if mode == 'fixture-block':
        time.sleep(90)
        raise RuntimeError('Blocking fixture should be cancelled')
    return solve_reference('worker.scheduling', problem)


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


class CanonicalContract(unittest.TestCase):
    """Run the installed, unmodified Foundry suite on real HTTP/solver jobs."""
    @classmethod
    def setUpClass(cls):
        cls.local = LocalAPI().__enter__()
        cls.http = httpx.Client(base_url=cls.local.base, timeout=30, trust_env=False)

    @classmethod
    def tearDownClass(cls):
        cls.http.close()
        cls.local.__exit__()

    def test_running_cancellation(self):
        marker = str(Path('canonical-cancel.pid').resolve())
        registration = Registration(ReferenceDomain(make_provider('worker.scheduling'), problem_type='cancel-fixture'),
                                    partial(blocking_fixture, marker))
        class StartedFixtureClient(httpx.Client):
            def delete(client, *args, **kwargs):
                # "running" means a worker claimed the job, not that a spawned
                # child finished importing (especially under CPU emulation).
                # Synchronize this fixture without changing the upstream suite
                # or any HTTP response; absence of actual execution still fails.
                deadline = time.monotonic() + 20
                while not Path(marker).exists() and time.monotonic() < deadline: time.sleep(.02)
                self.assertTrue(Path(marker).exists(), 'Cancellation fixture did not start')
                return super().delete(*args, **kwargs)
        with LocalAPI([registration]) as local, StartedFixtureClient(base_url=local.base, timeout=30, trust_env=False) as client:
            request = local.client('cancel-fixture').capabilities()['requestTemplate']
            request['input'] = INPUTS['worker.scheduling']
            suite = ContractSuite(client, base_path='/api/cancel-fixture/v1', token=local.token,
                                  problem=request, slow_problem=request, openapi=native_contract())
            suite.check_cancel()
            self.assertTrue(Path(marker).exists(), 'The fixture must actually have started')
            with self.assertRaises(ProcessLookupError): os.kill(int(Path(marker).read_text()), 0)


def canonical_case(domain, check):
    def run(self):
        catalog = self.local.client(domain).capabilities()
        request = catalog['requestTemplate']
        request.update(input=deepcopy(INPUTS[catalog['domainProfile']['id']]), request_id='canonical-' + domain)
        other = deepcopy(request); other['request_id'] += '-other'
        suite = ContractSuite(self.http, base_path='/api/' + domain + '/v1', token=self.local.token,
                              problem=request, other_problem=other, openapi=native_contract())
        getattr(suite, check)()
    return run


# Keep each upstream check visible to unittest/CI. Cancellation is tested with
# a running fixture above, never counted as PASS for slow_problem=None.
for _domain in ['routing-basic', 'worker-scheduling', 'inventory-replenishment']:
    for _check in ContractSuite.CHECKS:
        if _check != 'check_cancel':
            setattr(CanonicalContract, 'test_' + _domain.replace('-', '_') + '_' + _check,
                    canonical_case(_domain, _check))


class OperationsAndBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registrations = reference_domains(['worker-scheduling'])
        cls.local = LocalAPI(cls.registrations).__enter__()
        cls.http = httpx.Client(base_url=cls.local.base, timeout=30, trust_env=False)
        cls.schemas = SchemaChecker(native_contract())

    @classmethod
    def tearDownClass(cls):
        cls.http.close()
        cls.local.__exit__()

    def readiness(self, ready):
        response = self.http.get('/ready')
        self.assertEqual(response.status_code, 200 if ready else 503, response.text)
        self.schemas.check('Readiness', response.json())
        self.assertIs(response.json()['ready'], ready)
        return response

    def wait_ready(self, ready):
        deadline = time.monotonic() + 3
        while self.http.get('/ready').json()['ready'] is not ready and time.monotonic() < deadline:
            time.sleep(.02)
        return self.readiness(ready)

    def test_ops_are_read_only_and_match_selected_catalog(self):
        before = len(self.local.app.state.native_store.keys)
        health = self.http.get('/health'); self.assertEqual(health.status_code, 200)
        self.schemas.check('Health', health.json())
        for _ in range(3): self.readiness(True)
        response = self.http.get('/version'); self.schemas.check('Version', response.json())
        value = response.json()
        self.assertEqual(value['packageVersion'], version('ocp-candidate'))
        self.assertEqual(value['contractVersion'], '1')
        self.assertEqual(set(value['catalogs']), {'worker-scheduling'})
        catalog = self.local.client('worker-scheduling').capabilities()
        self.assertEqual(value['catalogs']['worker-scheduling']['catalogDigest'], catalog['catalogDigest'])
        self.assertEqual(len(self.local.app.state.native_store.keys), before)
        with patch.dict(os.environ, {'APP_VERSION': 'synthetic-build'}):
            self.assertEqual(self.http.get('/version').json()['build'], 'synthetic-build')

    def test_before_start_and_after_stop_are_not_ready(self):
        async def check():
            app = create_native_app('synthetic', reference_domains(['worker-scheduling']))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1') as client:
                self.assertEqual((await client.get('/ready')).status_code, 503)
                async with app.router.lifespan_context(app):
                    self.assertEqual((await client.get('/ready')).status_code, 200)
                self.assertEqual((await client.get('/ready')).status_code, 503)
                self.assertEqual((await client.get('/health')).status_code, 200)
        asyncio.run(check())

    def test_store_failure_returns_503_without_exception_details_and_recovers(self):
        with patch.object(self.local.app.state.native_store, 'get', side_effect=RuntimeError('synthetic-private-detail')):
            response = self.readiness(False)
            self.assertNotIn('synthetic-private-detail', response.text)
            self.assertIn({'name': 'store', 'ok': False}, response.json()['checks'])
            self.assertEqual(self.http.get('/health').status_code, 200)
        self.readiness(True)

    def test_poll_failure_and_recovery(self):
        with patch.object(self.local.app.state.native_store, 'claim', side_effect=RuntimeError('synthetic-poll-failure')):
            response = self.wait_ready(False)
            self.assertIn({'name': 'worker:worker-scheduling', 'ok': False}, response.json()['checks'])
        self.wait_ready(True)

    def test_stopped_worker_is_not_ready(self):
        pools = []
        def pool(*args, **kwargs):
            value = WorkerPool(*args, **kwargs); pools.append(value); return value
        with patch('ocp_runtime.native_server.WorkerPool', side_effect=pool):
            with LocalAPI(reference_domains(['worker-scheduling'])) as local:
                pools[0].stop()
                with httpx.Client(base_url=local.base, timeout=10, trust_env=False) as client:
                    response = client.get('/ready')
                    self.assertEqual(response.status_code, 503)
                    self.assertIn({'name': 'worker:worker-scheduling', 'ok': False}, response.json()['checks'])

    def test_busy_worker_remains_ready_without_starting_another_job(self):
        marker = str(Path('ready-busy.pid').resolve())
        registration = Registration(ReferenceDomain(make_provider('worker.scheduling'), problem_type='busy-fixture'),
                                    partial(blocking_fixture, marker))
        with LocalAPI([registration]) as local, httpx.Client(base_url=local.base, timeout=10, trust_env=False) as client:
            api = local.client('busy-fixture'); request = api.capabilities()['requestTemplate']
            request['input'] = INPUTS['worker.scheduling']
            job = api.submit(request, tenant='test', idempotency_key='busy')['job']
            deadline = time.monotonic() + 10
            while not Path(marker).exists() and time.monotonic() < deadline: time.sleep(.02)
            self.assertTrue(Path(marker).exists())
            self.assertEqual(api.job(job['jobId'], tenant='test')['status'], 'running')
            self.assertEqual(client.get('/ready').status_code, 200)
            self.assertEqual(len(local.app.state.native_store.keys), 1)
            api.cancel(job['jobId'], tenant='test')
            self.assertEqual(api.wait(job['jobId'], tenant='test')['status'], 'cancelled')

    def test_catalog_drift_and_failure_recover(self):
        domain = self.registrations[0].domain
        altered = domain.client.describe(); altered['limitations'] = ['synthetic-catalog-drift']
        with patch.object(domain.client, 'describe', return_value=altered):
            self.readiness(False)
        with patch.object(domain.client, 'describe', side_effect=RuntimeError('synthetic-catalog-failure')):
            self.readiness(False)
        self.readiness(True)

    def test_normal_and_router_error_request_ids(self):
        for path in ['/health', '/ready', '/version', '/not-found', '/api/worker-scheduling/v1/capabilities']:
            with self.subTest(path=path):
                response = self.http.get(path, headers={'x-request-id': 'audit.trace-123'})
                self.assertEqual(response.headers['x-request-id'], 'audit.trace-123')
                if response.status_code >= 400:
                    self.schemas.check('ErrorEnvelope', response.json())
                    self.assertEqual(response.json()['requestId'], 'audit.trace-123')

    def test_invalid_or_absent_request_id_gets_unique_safe_ids(self):
        seen = set()
        for candidate in [None, 'bad/id', 'x'*129, None]:
            headers = {'content-type': 'application/json'}
            if candidate is not None: headers['x-request-id'] = candidate
            response = self.http.post('/api/worker-scheduling/v1/validate', content=b'{', headers=headers)
            self.assertEqual(response.status_code, 422)
            value = response.json()['requestId']
            self.assertEqual(response.headers['x-request-id'], value)
            self.assertRegex(value, r'^[a-f0-9]{32}$')
            self.assertNotIn(value, seen); seen.add(value)

    def test_every_early_boundary_rejection_has_the_contract_envelope(self):
        # Direct ASGI probes exercise app framing branches that an HTTP parser
        # can reject before dispatch. The canonical suite above uses real HTTP.
        async def check():
            base = [('content-type', 'application/json'), ('x-request-id', 'boundary-123')]
            cases = [
                ('LOCAL_ONLY', 403, base+[('origin', 'https://example.invalid')], b'{}'),
                ('LOCAL_ONLY', 403, base+[('host', 'example.invalid')], b'{}'),
                ('INVALID_CONTENT_TYPE', 415, [('content-type','text/plain'),('x-request-id','boundary-123')], b'{}'),
                ('INVALID_FRAMING', 400, base+[('transfer-encoding','chunked')], b'{}'),
                ('INVALID_FRAMING', 400, base+[('content-length','bad')], b'{}'),
                ('INVALID_FRAMING', 400, base+[('content-length','3')], b'{}'),
                ('PAYLOAD_TOO_LARGE', 413, base+[('content-length','0')], b''),
                ('PAYLOAD_TOO_LARGE', 413, base+[('content-length','131073')], b'{}'),
            ]
            for name in ['authorization','x-oip-tenant-id','idempotency-key','content-length','host']:
                cases.append(('DUPLICATE_HEADER', 400, base+[(name,'127.0.0.1' if name=='host' else '2')]*2, b'{}'))
            for body in [b'{', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff']:
                cases.append(('INVALID_REQUEST', 422, base, body))
            before = len(self.local.app.state.native_store.keys)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.local.app), base_url='http://127.0.0.1') as client:
                for code, status, headers, body in cases:
                    with self.subTest(code=code, headers=headers, body=body):
                        response = await client.post('/api/worker-scheduling/v1/jobs', headers=headers, content=body)
                        self.assertEqual(response.status_code, status, response.text)
                        self.schemas.check('ErrorEnvelope', response.json())
                        self.assertEqual(response.json()['code'], code)
                        self.assertEqual(response.json()['requestId'], 'boundary-123')
                        self.assertEqual(response.headers['x-request-id'], 'boundary-123')
            self.assertEqual(len(self.local.app.state.native_store.keys), before)
        asyncio.run(check())


class ConcurrentAndRecovery(unittest.TestCase):
    """Real loopback HTTP races and explicit faults, not a production load benchmark."""
    def request(self, local, domain='worker-scheduling'):
        api = local.client(domain)
        catalog = api.capabilities()
        request = catalog['requestTemplate']
        request['input'] = deepcopy(INPUTS[catalog['domainProfile']['id']])
        return api, request

    def race(self, count, operation):
        barrier = threading.Barrier(count, timeout=30)
        def call(index):
            barrier.wait()
            return operation(index)
        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(call, range(count)))

    def submit_answer(self, api, request, key, tenant='race'):
        try:
            return api.submit(request, tenant=tenant, idempotency_key=key)
        except NativeError as error:
            return {'code': error.code, 'status': error.status}

    def test_parallel_replay_is_one_job_and_one_attempt(self):
        with LocalAPI(reference_domains(['worker-scheduling'])) as local:
            api, request = self.request(local)
            responses = self.race(24, lambda _: self.submit_answer(local.client('worker-scheduling'), request, 'same'))
            self.assertEqual(len({r['job']['jobId'] for r in responses}), 1)
            self.assertEqual(sum(not r['replayed'] for r in responses), 1)
            job_id = responses[0]['job']['jobId']
            self.assertEqual(api.wait(job_id, tenant='race', timeout=60)['status'], 'succeeded')
            job = local.app.state.native_store.get(tenant='race', problem_type='worker-scheduling', job_id=job_id)
            self.assertEqual(job.attempt, 1)
            self.assertEqual(len(local.app.state.native_store.ids), 1)
            self.assertEqual(api.result(job_id, tenant='race')['result']['metrics'][0]['value'], 7)

    def test_parallel_conflict_never_creates_a_second_job(self):
        with LocalAPI(reference_domains(['worker-scheduling'])) as local:
            _, request = self.request(local)
            alternative = deepcopy(request); alternative['request_id'] = 'different-body'
            # Admission race only: pause dispatch after a successful startup poll.
            with patch.object(local.app.state.native_store, 'claim', return_value=None):
                responses = self.race(24, lambda i: self.submit_answer(local.client('worker-scheduling'),
                                      request if i % 2 else alternative, 'conflicting'))
                accepted = [r for r in responses if 'job' in r]
                rejected = [r for r in responses if 'code' in r]
                self.assertEqual(len(accepted), 12)
                self.assertEqual(rejected, [{'code':'IDEMPOTENCY_CONFLICT','status':409}] * 12)
                self.assertEqual(sum(not r['replayed'] for r in accepted), 1)
                self.assertEqual(len(local.app.state.native_store.ids), 1)

    def test_parallel_session_limit_is_atomic_and_replay_survives(self):
        with LocalAPI(reference_domains(['worker-scheduling']), max_jobs=4) as local:
            api, request = self.request(local)
            with patch.object(local.app.state.native_store, 'claim', return_value=None):
                responses = self.race(24, lambda i: self.submit_answer(local.client('worker-scheduling'), request, str(i)))
                self.assertEqual(sum('job' in r for r in responses), 4)
                self.assertEqual(sum(r.get('code') == 'LOCAL_JOB_LIMIT' and r.get('status') == 429 for r in responses), 20)
                self.assertEqual(len(local.app.state.native_store.keys), 4)
                i = next(i for i, r in enumerate(responses) if 'job' in r)
                self.assertTrue(api.submit(request, tenant='race', idempotency_key=str(i))['replayed'])
                invalid = deepcopy(request); invalid['input'] = {}
                with self.assertRaisesRegex(NativeError, 'INVALID_PROBLEM'):
                    api.submit(invalid, tenant='race', idempotency_key='invalid')
                self.assertEqual(len(local.app.state.native_store.keys), 4)

    def test_parallel_tenant_and_domain_isolation(self):
        with LocalAPI(reference_domains(['worker-scheduling','inventory-replenishment'])) as local:
            pairs = [(d,t) for d in local.app.state.domain_ids for t in ('tenant-a','tenant-b')]
            requests = {d:self.request(local,d)[1] for d in local.app.state.domain_ids}
            responses = self.race(4, lambda i: self.submit_answer(local.client(pairs[i][0]), requests[pairs[i][0]], 'shared', pairs[i][1]))
            self.assertEqual(len({r['job']['jobId'] for r in responses}), 4)
            for (domain,tenant), response in zip(pairs,responses):
                api = local.client(domain); job_id = response['job']['jobId']
                self.assertEqual(api.wait(job_id, tenant=tenant, timeout=60)['status'], 'succeeded')
                for other_domain,other_tenant in pairs:
                    if (domain,tenant) == (other_domain,other_tenant): continue
                    other = local.client(other_domain)
                    for operation in (other.job,other.result,other.cancel):
                        with self.assertRaisesRegex(NativeError,'JOB_NOT_FOUND'): operation(job_id,tenant=other_tenant)
                    with self.assertRaisesRegex(NativeError,'JOB_NOT_FOUND'):
                        other.evaluate({'jobId':job_id},tenant=other_tenant)
                self.assertEqual(api.job(job_id,tenant=tenant)['status'],'succeeded')

    def test_parallel_error_request_ids_do_not_cross_requests(self):
        with LocalAPI(reference_domains(['worker-scheduling'])) as local:
            def operation(index):
                with httpx.Client(base_url=local.base,timeout=30,trust_env=False) as client:
                    headers = {'content-type':'application/json'}
                    if index % 2: headers['x-request-id'] = 'parallel-' + str(index)
                    return client.post('/api/worker-scheduling/v1/jobs',headers=headers,content=b'{')
            responses = self.race(32,operation)
            seen = set()
            for index,response in enumerate(responses):
                self.assertEqual(response.status_code,422)
                SchemaChecker(native_contract()).check('ErrorEnvelope',response.json())
                request_id = response.json()['requestId']
                self.assertEqual(response.headers['x-request-id'],request_id)
                if index % 2: self.assertEqual(request_id,'parallel-'+str(index))
                else: self.assertRegex(request_id,r'^[a-f0-9]{32}$')
                self.assertNotIn(request_id,seen); seen.add(request_id)
            self.assertEqual(len(local.app.state.native_store.keys),0)

    def fixture(self, name):
        marker = Path(name+'.pid').resolve()
        marker.unlink(missing_ok=True)
        registration = Registration(ReferenceDomain(make_provider('worker.scheduling'),problem_type='fault-fixture'),
                                    partial(fault_fixture,str(marker)))
        return LocalAPI([registration]), marker

    def wait_process(self, marker):
        deadline = time.monotonic()+20
        while (not marker.exists() or not marker.read_text()) and time.monotonic()<deadline: time.sleep(.02)
        self.assertTrue(marker.exists())
        return int(marker.read_text())

    def test_crashed_solver_is_failed_and_next_real_job_succeeds(self):
        self.fault_and_recovery('fixture-crash','SOLVER_CRASHED')

    def test_solver_exception_is_sanitized_and_next_real_job_succeeds(self):
        self.fault_and_recovery('fixture-exception','SOLVE_FAILED')

    def fault_and_recovery(self, mode, code):
        local,marker = self.fixture(mode)
        with local:
            api,request = self.request(local,'fault-fixture'); request['request_id'] = mode
            job_id = api.submit(request,tenant='fault',idempotency_key='fault')['job']['jobId']
            failed = api.wait(job_id,tenant='fault',timeout=60)
            self.assertEqual(failed['status'],'failed'); self.assertEqual(failed['error']['code'],code)
            self.assertNotIn('synthetic-private-solver-detail',json.dumps(failed))
            self.assertFalse(failed['error']['retryable'])
            with self.assertRaisesRegex(NativeError,'JOB_FAILED'): api.result(job_id,tenant='fault')
            self.assertTrue(api.submit(request,tenant='fault',idempotency_key='fault')['replayed'])
            self.assertEqual(local.app.state.native_store.get(tenant='fault',problem_type='fault-fixture',job_id=job_id).attempt,1)
            request['request_id'] = 'real-recovery'
            result = api.solve(request,tenant='fault',idempotency_key='recovery',timeout=60)
            self.assertEqual(result['result']['result']['metrics'][0]['value'],7)
            with self.assertRaises(ProcessLookupError): os.kill(int(marker.read_text()),0)
            with httpx.Client(trust_env=False) as client: self.assertEqual(client.get(local.base+'/ready').status_code,200)

    def test_shutdown_cancels_running_and_queued_jobs_and_reaps_workers(self):
        pools=[]
        def pool(*args,**kwargs):
            value=WorkerPool(*args,**kwargs); pools.append(value); return value
        with patch('ocp_runtime.native_server.WorkerPool',side_effect=pool): local,marker=self.fixture('shutdown')
        with local:
            api,request=self.request(local,'fault-fixture'); request['request_id']='fixture-block'
            first=api.submit(request,tenant='shutdown',idempotency_key='running')['job']['jobId']
            pid=self.wait_process(marker)
            second=api.submit(request,tenant='shutdown',idempotency_key='queued')['job']['jobId']
            self.assertEqual(api.job(second,tenant='shutdown')['status'],'queued')
        for job_id in (first,second):
            self.assertEqual(local.app.state.native_store.get(tenant='shutdown',problem_type='fault-fixture',job_id=job_id).status.value,'cancelled')
        self.assertFalse(local.thread.is_alive())
        self.assertTrue(all(not thread.is_alive() for p in pools for thread in p._threads))
        self.assertEqual(local.socket.fileno(),-1)
        with self.assertRaises(ProcessLookupError): os.kill(pid,0)

    def test_concurrent_cancellations_stop_one_process(self):
        local,marker=self.fixture('parallel-cancel')
        with local:
            api,request=self.request(local,'fault-fixture'); request['request_id']='fixture-block'
            job_id=api.submit(request,tenant='cancel',idempotency_key='cancel')['job']['jobId']
            pid=self.wait_process(marker)
            responses=self.race(16,lambda _:local.client('fault-fixture').cancel(job_id,tenant='cancel'))
            self.assertEqual({r['jobId'] for r in responses},{job_id})
            self.assertTrue(all(r['status'] in ('running','cancelled') for r in responses))
            self.assertEqual(api.wait(job_id,tenant='cancel')['status'],'cancelled')
            self.assertTrue(api.submit(request,tenant='cancel',idempotency_key='cancel')['replayed'])
            with self.assertRaises(ProcessLookupError): os.kill(pid,0)

    def test_client_deadline_reports_timeout_and_server_stops_process(self):
        local,marker=self.fixture('deadline')
        with local:
            api,request=self.request(local,'fault-fixture'); request['request_id']='fixture-block'
            job_id=api.submit(request,tenant='deadline',idempotency_key='deadline')['job']['jobId']
            pid=self.wait_process(marker)
            with self.assertRaisesRegex(NativeError,'WAIT_TIMEOUT'): api.wait(job_id,tenant='deadline',timeout=.05)
            self.assertEqual(api.wait(job_id,tenant='deadline')['status'],'cancelled')
            with self.assertRaises(ProcessLookupError): os.kill(pid,0)

    def test_partial_start_failure_reaps_already_started_pools(self):
        pools=[]
        def pool(*args,**kwargs):
            value=WorkerPool(*args,**kwargs); pools.append(value); return value
        with patch('ocp_runtime.native_server.WorkerPool',side_effect=pool): local=LocalAPI()
        with patch.object(pools[1],'start',side_effect=RuntimeError('synthetic-start-failure')):
            with self.assertRaisesRegex(RuntimeError,'LOCAL_API_START_FAILED'): local.__enter__()
        self.assertTrue(all(not thread.is_alive() for p in pools for thread in p._threads))
        self.assertFalse(local.thread.is_alive()); self.assertEqual(local.socket.fileno(),-1)
        with LocalAPI(reference_domains(['worker-scheduling'])) as recovered:
            with httpx.Client(trust_env=False) as client: self.assertEqual(client.get(recovered.base+'/ready').status_code,200)

    def test_repeated_lifecycle_does_not_leak_workers_or_share_tokens(self):
        pools=[]; tokens=set()
        def pool(*args,**kwargs):
            value=WorkerPool(*args,**kwargs); pools.append(value); return value
        with patch('ocp_runtime.native_server.WorkerPool',side_effect=pool):
            for _ in range(4):
                with LocalAPI(reference_domains(['worker-scheduling'])) as local:
                    for token in tokens:
                        with self.assertRaisesRegex(NativeError,'UNAUTHENTICATED'):
                            NativeClient(local.base+'/api/worker-scheduling/v1',token).capabilities()
                    tokens.add(local.token)
                    self.assertEqual(len(local.app.state.native_store.keys),0)
                self.assertFalse(local.thread.is_alive()); self.assertEqual(local.socket.fileno(),-1)
                self.assertTrue(all(not thread.is_alive() for p in pools for thread in p._threads))
        self.assertEqual(len(tokens),4)

    def test_deep_json_rejected_with_trace_and_server_recovers(self):
        with LocalAPI(reference_domains(['worker-scheduling'])) as local, httpx.Client(base_url=local.base,trust_env=False,timeout=30) as client:
            for raw in [b'['*2000+b'0'+b']'*2000, b'{"x":'*2000+b'0'+b'}'*2000]:
                response=client.post('/api/worker-scheduling/v1/jobs',content=raw,
                                     headers={'content-type':'application/json','x-request-id':'deep-json'})
                self.assertEqual(response.status_code,422,response.text[:200])
                self.assertEqual(response.json()['code'],'INVALID_REQUEST')
                self.assertFalse(response.json()['retryable'])
                self.assertEqual(response.json()['requestId'],'deep-json')
                self.assertEqual(response.headers['x-request-id'],'deep-json')
                SchemaChecker(native_contract()).check('ErrorEnvelope',response.json())
            self.assertEqual(client.get('/ready').status_code,200)
            self.assertEqual(len(local.app.state.native_store.keys),0)
            api,request=self.request(local)
            result=api.solve(request,tenant='recovery',idempotency_key='after-deep-json',timeout=60)
            self.assertEqual(result['result']['result']['metrics'][0]['value'],7)


if __name__=='__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)
                               for c in [Servers, CanonicalContract, OperationsAndBoundary, ConcurrentAndRecovery])
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),
                      'canonical_tests': unittest.defaultTestLoader.loadTestsFromTestCase(CanonicalContract).countTestCases(),
                      'concurrency_recovery_tests': unittest.defaultTestLoader.loadTestsFromTestCase(ConcurrentAndRecovery).countTestCases()}))
    raise SystemExit(not r.wasSuccessful())
