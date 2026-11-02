"""Installed optional verification: scoped jobs, negative evidence and real MCP.

Run outside the checkout with the candidate and checker wheels installed.
Copy tools/native_tests/inputs.json and examples/native/budget-input.json into
the working directory first. Install the three budget example wheels as well.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import unittest

from mcp import Client, StdioServerParameters
from conformance.assessment import CheckerRegistry, assess, digest
from foundry_capability_contract import MemoryJobStore, JobStatus
from ocp_candidate.native import NativeError
from ocp_runtime.native_verification import local_verifier


class VerificationBoundary(unittest.TestCase):
    def setUp(self):
        self.store = MemoryJobStore()
        self.job, _ = self.store.submit(tenant='owner', problem_type='example',
            idempotency_key='key', request_hash='hash', caller='test', problem={})
        self.verify = local_verifier(self.store)

    def error(self, code, *, domain='example', tenant='owner'):
        with self.assertRaises(NativeError) as caught:
            self.verify(domain, self.job.id, tenant=tenant)
        self.assertEqual(caught.exception.code, code)

    def test_scoped_job_lookup(self):
        self.error('JOB_NOT_FOUND', tenant='other')
        self.error('JOB_NOT_FOUND', domain='other')

    def test_no_result_for_active_cancelled_failed(self):
        self.error('JOB_NOT_FINISHED')
        self.store.claim(problem_type='example', worker_id='w', lease_seconds=30)
        self.error('JOB_NOT_FINISHED')
        self.store.finish(job_id=self.job.id, worker_id='w', status=JobStatus.FAILED)
        self.error('JOB_FAILED')
        other = MemoryJobStore()
        job, _ = other.submit(tenant='owner', problem_type='example', idempotency_key='k',
                              request_hash='h', caller='test', problem={})
        other.request_cancel(tenant='owner', problem_type='example', job_id=job.id)
        with self.assertRaisesRegex(NativeError, 'JOB_CANCELLED'):
            local_verifier(other)('example', job.id, tenant='owner')

    def test_expired_job(self):
        store = MemoryJobStore(clock=lambda: datetime.now(timezone.utc) - timedelta(days=30))
        job, _ = store.submit(tenant='owner', problem_type='example', idempotency_key='k',
                              request_hash='h', caller='test', problem={})
        with self.assertRaisesRegex(NativeError, 'JOB_EXPIRED'):
            local_verifier(store)('example', job.id, tenant='owner')

    def test_missing_result_never_passes(self):
        self.store.claim(problem_type='example', worker_id='w', lease_seconds=30)
        self.store.finish(job_id=self.job.id, worker_id='w', status=JobStatus.SUCCEEDED)
        self.error('BAD_ANSWER')

    def test_job_and_mathematical_state_must_match(self):
        self.store.claim(problem_type='example', worker_id='w', lease_seconds=30)
        self.store.finish(job_id=self.job.id, worker_id='w', status=JobStatus.INFEASIBLE,
                          result={'status': 'optimal'})
        self.error('BAD_ANSWER')


class InstalledMCP(unittest.TestCase):
    def test_custom_profile_uses_only_host_selected_checker(self):
        asyncio.run(self.extension())

    async def extension(self):
        for enabled in (False, True):
            args = ['-I','-B','-m','ocp_runtime.native_extension','--extension',
                    'ocp_budget_engine.registration:extension','--verification']
            if enabled:
                args += ['--checker-factory','ocp_budget_check:registry']
            parameters = StdioServerParameters(command=sys.executable,args=args,
                env={'PATH':os.defpath,'HOME':os.environ['HOME'],'PYTHONDONTWRITEBYTECODE':'1'})
            async with Client(parameters,read_timeout_seconds=90) as host:
                async def call(name, arguments):
                    value = await host.call_tool(name,arguments)
                    self.assertFalse(value.is_error,value.structured_content)
                    return value.structured_content
                catalog = (await call('ocp_native_context',{'domain':'budget-selection'}))['catalog']
                request = deepcopy(catalog['requestTemplate'])
                request.update(request_id='custom-profile',input=json.loads(Path('budget-input.json').read_text()))
                job = (await call('ocp_native_submit',{'domain':'budget-selection','problem':request,
                               'idempotency_key':'custom-profile'}))['job']
                deadline = asyncio.get_running_loop().time()+60
                while job['status'] not in ('succeeded','infeasible','failed','cancelled'):
                    self.assertLess(asyncio.get_running_loop().time(),deadline)
                    await asyncio.sleep(.05)
                    job = await call('ocp_native_job',{'domain':'budget-selection','job_id':job['jobId']})
                report = (await call('ocp_native_verify',{'domain':'budget-selection','job_id':job['jobId']}))['verification']
                self.assertEqual(report['status'],'PASS' if enabled else 'FAIL')
                if enabled:
                    self.assertEqual(report['domain_profile']['id'],'example.budget-selection')
                    self.assertEqual(report['checks']['optimality']['status'],'PASS')
                else:
                    self.assertEqual(report['checks']['structure_and_semantics']['reason'],'UNSUPPORTED_PROFILE')

    def test_optional_tool_and_actual_jobs(self):
        asyncio.run(self.exercise())

    async def exercise(self):
        parameters = StdioServerParameters(command=sys.executable,
            args=['-I', '-B', '-m', 'ocp_runtime.native_mcp', '--verification'],
            env={'PATH': os.defpath, 'HOME': os.environ['HOME'], 'PYTHONDONTWRITEBYTECODE': '1'})
        inputs = json.loads(Path('inputs.json').read_text())
        async with Client(parameters, read_timeout_seconds=90) as host:
            async def call(name, args, error=False):
                result = await host.call_tool(name, args)
                self.assertEqual(result.is_error, error, result.structured_content)
                self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                return result.structured_content

            tools = (await host.list_tools()).tools
            self.assertEqual(len(tools), 9)
            verify_tool = next(t for t in tools if t.name == 'ocp_native_verify')
            self.assertEqual(set(verify_tool.input_schema['properties']), {'domain', 'job_id'})
            listing = await call('ocp_native_context', {})
            self.assertEqual(listing['verification']['version'], '0.1.0')
            self.assertEqual(listing['verification']['tool'], 'ocp_native_verify')
            result = await call('ocp_native_verify', {'domain':'made-up','job_id':'none'}, True)
            self.assertEqual(result['code'], 'UNSUPPORTED_DOMAIN')
            result = await call('ocp_native_verify', {'domain':'worker-scheduling','job_id':'none'}, True)
            self.assertEqual(result['code'], 'JOB_NOT_FOUND')
            for domain in listing['availableDomains']:
                catalog = (await call('ocp_native_context', {'domain':domain}))['catalog']
                data = deepcopy(inputs[catalog['domainProfile']['id']])
                variants = [('base', data)]
                if domain == 'worker-scheduling':
                    impossible = deepcopy(data)
                    impossible['tasks'][0].update(eligible_workers=[], costs={})
                    variants.append(('infeasible', impossible))
                for label, data in variants:
                    request = deepcopy(catalog['requestTemplate'])
                    request.update(input=data, request_id=domain+'-'+label)
                    checked = await call('ocp_native_validate', {'domain':domain,'problem':request})
                    self.assertTrue(checked['valid'])
                    submitted = await call('ocp_native_submit', {'domain':domain,'problem':request,
                        'idempotency_key':request['request_id']})
                    job = submitted['job']
                    deadline = asyncio.get_running_loop().time()+60
                    while job['status'] not in ('succeeded','infeasible','failed','cancelled'):
                        self.assertLess(asyncio.get_running_loop().time(), deadline)
                        await asyncio.sleep(.05)
                        job = await call('ocp_native_job', {'domain':domain,'job_id':job['jobId']})
                    response = (await call('ocp_native_result', {'domain':domain,'job_id':job['jobId']}))['result']
                    report = await call('ocp_native_verify', {'domain':domain,'job_id':job['jobId']})
                    evidence = report['verification']
                    self.assertEqual(report['jobStatus'], job['status'])
                    self.assertEqual(evidence, assess(request, response))
                    self.assertEqual(evidence['status'], 'PASS')
                    self.assertEqual(evidence['request_sha256'], digest(request))
                    self.assertEqual(evidence['response_sha256'], digest(response))
                    self.assertEqual(evidence['checks']['execution_attestation']['status'], 'NOT_CHECKED')
                    if label == 'infeasible':
                        self.assertEqual(evidence['checks']['infeasibility']['status'], 'PASS')
                        self.assertIsNone(evidence['checks']['objective_recomputation']['value'])
                    # Store-backed verification must reject changed costs and unsupported checkers.
                    store = MemoryJobStore()
                    local, _ = store.submit(tenant='owner', problem_type=domain, idempotency_key='k',
                        request_hash='h', caller='test', problem=request)
                    store.claim(problem_type=domain, worker_id='w', lease_seconds=30)
                    corrupted = deepcopy(response)
                    if corrupted['solution'] is not None:
                        corrupted['metrics'][0]['value'] += 1
                    else:
                        corrupted['status'] = 'optimal'
                    store.finish(job_id=local.id, worker_id='w', status=JobStatus.SUCCEEDED, result=corrupted)
                    bad = local_verifier(store)(domain, local.id, tenant='owner')
                    self.assertEqual(bad['verification']['status'], 'FAIL')
                    unsupported = local_verifier(store, registry=CheckerRegistry())(domain, local.id, tenant='owner')
                    self.assertEqual(unsupported['verification']['status'], 'FAIL')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'tests_run':result.testsRun, 'failures':len(result.failures),
                      'errors':len(result.errors), 'skipped':len(result.skipped), 'model_calls':0}))
    raise SystemExit(not result.wasSuccessful())
