"""Installed-policy binding tests. Synthetic authority/results, no solver/network.

The Routing descriptor is a public fixture; no private application is imported.
Policy decisions are current and domain-owned. Stored bytes are synthetic so
these checks prove the binding's admission/disclosure paths, not a solver.
"""
from copy import deepcopy
import importlib.resources as resources
import json
from pathlib import Path
import tempfile
import unittest

from ocp_runtime.bindings.mcp import BindingRuntime, create_mcp
from ocp_runtime.execution import ExecutionService
from ocp_runtime.execution.jobs import Principal
from ocp_runtime._worker_contract.jobs.model import JobStatus
from ocp_runtime.operations import OperationService, OperationConnector, OperationAnswer


def routing_content():
    local = Path(__file__).resolve().parents[2] / 'examples/routing-ocp-server/content'
    # Public source checkout or independently installed public example.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / 'examples/routing-ocp-server/content'
        if (candidate / 'manifest.json').is_file():
            return candidate
    return Path(str(resources.files('ocp_routing_ocp_server').joinpath('content')))


class Connector:
    isolation = "local_process"
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.allowed = True
        self.seen = []
        self.explode = False
        self.after = None

    def describe(self):
        return deepcopy(self.descriptor)

    def execute(self, *_):
        raise AssertionError('SOLVER_MUST_NOT_RUN')

    def authorize(self, principal, action, resource):
        self.seen.append((principal, action, deepcopy(resource)))
        if self.explode:
            raise ValueError('sensitive policy message')
        return self.allowed and (self.after is None or self.after(action, resource))


class BindingAuthorization(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        content = routing_content()
        self.doc = json.loads((content / 'manifest.json').read_text())
        self.input = json.loads((content / 'examples/matrix/input.json').read_text())
        self.config = {'time_limit_seconds': .05}
        self.connector = Connector(self.doc)
        self.service = ExecutionService(self.doc, self.connector)
        self.principal = Principal('tenant', 'caller')
        self.runtime = BindingRuntime({self.doc['id']: self.service}, self.root)
        self.addCleanup(self.runtime.close)
        self.server = create_mcp(self.runtime, principal=self.principal)
        self.sid = self.doc['id']

    async def call(self, tool, **args):
        response = await self.server.call_tool(tool, args)
        return response.is_error, response.structured_content

    def submit(self, key='one'):
        return self.runtime.jobs[self.sid].submit(self.principal, self.input, self.config,
                                                 idempotency_key=key)[0]

    def finish(self, result):
        job = self.submit()
        store = self.runtime.jobs[self.sid].store
        claimed = store.claim(problem_type=self.runtime.jobs[self.sid].problem_type,
                              worker_id='synthetic', lease_seconds=30)
        self.assertEqual(claimed.id, job.id)
        store.finish(job_id=job.id, worker_id='synthetic', status=JobStatus.SUCCEEDED, result=result)
        return job

    async def test_current_policy_blocks_submit_before_any_job(self):
        self.connector.allowed = False
        error, value = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
                                      configuration=self.config, idempotency_key='no')
        self.assertTrue(error)
        self.assertEqual(value['code'], 'AUTHORIZATION_DENIED')
        with self.runtime.jobs[self.sid].store._transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0], 0)

    async def test_all_saved_job_paths_recheck_and_pass_original_request(self):
        job = self.finish({'solution_status': 'unknown', 'result': None, 'evaluation': None})
        for name in ('ocp_job', 'ocp_result', 'ocp_evaluate', 'ocp_cancel'):
            error, _ = await self.call(name, server_id=self.sid, job_id=job.id)
            self.assertFalse(error, name)
            seen = self.connector.seen[-1][2]
            self.assertEqual(seen['stored_request']['input'], self.input)
            self.assertEqual(seen['stored_request']['configuration'], self.service.request(self.input, self.config)['configuration'])
            self.assertEqual(seen['stored_owner'], {'tenant': 'tenant', 'caller': 'caller'})
            self.connector.allowed = False
            error, value = await self.call(name, server_id=self.sid, job_id=job.id)
            self.assertTrue(error)
            self.assertEqual(value['code'], 'AUTHORIZATION_DENIED')
            self.connector.allowed = True

    async def test_stored_request_decides_resource_not_requested_job_identifier(self):
        job = self.submit()
        self.connector.after = lambda action, body: body.get('stored_request', {}).get('input', {}).get('depot_id') == 'another-resource'
        error, value = await self.call('ocp_result', server_id=self.sid, job_id=job.id)
        self.assertTrue(error)
        self.assertEqual(value['code'], 'AUTHORIZATION_DENIED')

    async def test_revoked_idempotency_replay_does_not_admit_again(self):
        job = self.submit()
        self.connector.allowed = False
        error, value = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
                                      configuration=self.config, idempotency_key='one')
        self.assertTrue(error)
        self.assertEqual(value['code'], 'AUTHORIZATION_DENIED')
        self.connector.allowed = True
        error, value = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
                                      configuration=self.config, idempotency_key='one')
        self.assertFalse(error)
        self.assertTrue(value['replayed'])
        self.assertEqual(value['job']['jobId'], job.id)

    async def test_post_dispatch_revocation_hides_body_preserves_observation_need(self):
        def policy(action, resource):
            if action == 'submit':
                return sum(x[1] == 'submit' for x in self.connector.seen) == 1
            return True
        self.connector.after = policy
        error, value = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
                                      configuration=self.config, idempotency_key='one')
        self.assertTrue(error)
        self.assertEqual(value['outcome'], 'requires_observation')
        self.assertEqual(value['code'], 'AUTHORIZATION_REVOKED_AFTER_DISPATCH')
        self.assertNotIn('job', value)
        self.connector.after = None
        error, replay = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
                                       configuration=self.config, idempotency_key='one')
        self.assertFalse(error)
        self.assertTrue(replay['replayed'])

    async def test_deleted_hook_and_policy_exception_fail_closed_without_details(self):
        job = self.submit()
        self.connector.authorize = None
        error, value = await self.call('ocp_job', server_id=self.sid, job_id=job.id)
        self.assertTrue(error)
        self.assertEqual(value['code'], 'AUTHORIZATION_HOOK_UNAVAILABLE')
        del self.connector.authorize
        self.connector.explode = True
        error, value = await self.call('ocp_job', server_id=self.sid, job_id=job.id)
        self.assertTrue(error)
        self.assertEqual(value['code'], 'AUTHORIZATION_UNAVAILABLE')
        self.assertNotIn('sensitive', json.dumps(value))

    async def test_restart_without_previously_required_policy_rejects(self):
        self.submit()
        self.connector.authorize = None
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_HOOK_UNAVAILABLE'):
            BindingRuntime({self.sid: self.service}, self.root)

    async def test_legacy_connector_without_policy_remains_supported(self):
        self.connector.authorize = None
        fresh = BindingRuntime({self.sid: self.service}, self.root / 'legacy')
        self.addCleanup(fresh.close)
        server = create_mcp(fresh, principal=self.principal)
        out = await server.call_tool('ocp_validate', {'server_id': self.sid, 'input_value': self.input,
                                                     'configuration': self.config})
        self.assertFalse(out.is_error)

    async def test_large_result_artifact_current_authorization_and_scope(self):
        job = self.finish({'blob': 'x' * 70000, 'evaluation': None})
        error, value = await self.call('ocp_result', server_id=self.sid, job_id=job.id)
        self.assertFalse(error)
        ref = value['artifact']
        error, _ = await self.call('ocp_read_artifact', reference=ref)
        self.assertFalse(error)
        self.assertEqual(self.connector.seen[-1][2]['stored_request']['input'], self.input)
        self.connector.allowed = False
        error, blocked = await self.call('ocp_read_artifact', reference=ref)
        self.assertTrue(error)
        self.assertNotIn('data_base64', blocked)
        # ArtifactStore without the binding callback cannot bypass stored policy.
        with self.assertRaisesRegex(ValueError, 'ARTIFACT_AUTHORIZATION_REQUIRED'):
            self.runtime.artifacts.get(ref, principal='tenant')

    async def test_artifact_prepare_reuse_checks_origin_policy(self):
        authorization = self.runtime.authorization(self.principal, self.sid, 'result', {'input': self.input})
        ref = self.runtime.artifacts.put(b'header\nvalue\n', principal='tenant', media_type='text/csv', authorization=authorization)
        self.connector.after = lambda action, resource: action == 'prepare'
        error, value = await self.call('ocp_prepare', server_id=self.sid, configuration=self.config,
                                      files={'input.csv': ref}, format_id='unregistered')
        self.assertTrue(error)
        self.assertEqual(value['code'], 'ARTIFACT_NOT_ACCESSIBLE')
        self.assertTrue(any(item[1] == 'result' for item in self.connector.seen))

    async def test_artifact_post_read_revocation_and_reference_tamper(self):
        authorization = self.runtime.authorization(self.principal, self.sid, 'result', {'input': self.input})
        ref = self.runtime.artifacts.put(b'private', principal='tenant', media_type='text/plain', authorization=authorization)
        self.connector.seen.clear()
        self.connector.after = lambda action, resource: len(self.connector.seen) == 1
        error, value = await self.call('ocp_read_artifact', reference=ref)
        self.assertTrue(error)
        self.assertNotIn('data_base64', value)
        self.connector.after = None
        error, _ = await self.call('ocp_read_artifact', reference={**ref, 'authorization': None})
        self.assertTrue(error)

    async def test_analysis_scope_uses_stored_plan_and_rechecks_reads(self):
        plan = self.runtime.analyses[self.sid].plan(self.principal, 'vehicle_weights', self.input,
                    self.config, variables=[{'binding': 'vehicle_weight', 'values': [0, 200]}], ranking_metric='total_distance_m')
        identifier = plan['id']
        for tool in ('ocp_analysis', 'ocp_compare', 'ocp_run', 'ocp_stop_analysis'):
            self.connector.allowed = False
            args = {'server_id': self.sid, 'analysis_id': identifier}
            if tool == 'ocp_run':
                args['expected_plan_fingerprint'] = plan['plan']['plan_fingerprint']
            error, value = await self.call(tool, **args)
            self.assertTrue(error)
            self.assertEqual(value['code'], 'AUTHORIZATION_DENIED')
            self.assertEqual(self.connector.seen[-1][2]['stored_plan'], plan['plan'])
        self.assertEqual(self.runtime.futures, {})

    async def test_operation_output_artifact_and_prepare_reuse_are_guarded(self):
        doc = deepcopy(self.doc)
        doc['required_extensions'] = ['ocp.operations']
        doc['schemas']['op_input'] = {'type': 'object', 'additionalProperties': False}
        doc['schemas']['op_output'] = {'type': 'object'}
        op = {'id': 'report', 'version': '1.0.0', 'kind': 'query', 'description': 'Synthetic large scoped report',
              'request_schema': 'op_input', 'response_schema': 'op_output', 'effects': 'none', 'execution': 'sync',
              'binding': {'connector': 'report'},
              'capabilities': {x: False for x in ('idempotency', 'reconciliation', 'cancel', 'atomic_precondition', 'snapshot')}}
        doc['extensions'] = {'ocp.operations': {'version': '0.1.0-draft.2', 'operations': [op]}}
        connector = Connector(doc)
        operation = OperationService(doc, {'report': OperationConnector(lambda: deepcopy(op),
                    lambda *args: OperationAnswer({'blob': 'x' * 70000}, effect='none'), lambda *args: True)},
                    journal=self.root / 'op.sqlite')
        runtime = BindingRuntime({self.sid: ExecutionService(doc, connector)}, self.root / 'op-runtime',
                                 operation_services={self.sid: operation})
        self.addCleanup(runtime.close)
        server = create_mcp(runtime, principal=self.principal)
        expected = operation.advertised()[0]['reference']
        out = await server.call_tool('op_routing_example__report', {'request': {}, 'expected': expected, 'request_id': 'report'})
        self.assertFalse(out.is_error, out.structured_content)
        ref = out.structured_content['artifact']
        connector.allowed = False
        out = await server.call_tool('ocp_read_artifact', {'reference': ref})
        self.assertTrue(out.is_error)
        connector.after = lambda action, resource: action == 'prepare_operation'
        connector.allowed = True
        out = await server.call_tool('ocp_prepare_operation', {'server_id': self.sid, 'operation_id': 'report',
            'expected': expected, 'files': {'report.json': ref}, 'format_id': 'not-registered'})
        self.assertTrue(out.is_error)
        self.assertEqual(out.structured_content['code'], 'ARTIFACT_NOT_ACCESSIBLE')

    async def test_conflicting_key_does_not_disclose_unauthorized_original_job(self):
        job = self.submit()
        self.connector.after = lambda action, resource: action != 'job'
        error, value = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
            configuration={'time_limit_seconds': .06}, idempotency_key='one')
        self.assertTrue(error)
        self.assertEqual(value['code'], 'IDEMPOTENCY_CONFLICT')
        self.assertNotIn('job_id', value)
        self.assertEqual(self.connector.seen[-1][2]['stored_request']['input'], self.input)
        self.connector.after = None
        error, value = await self.call('ocp_submit', server_id=self.sid, input_value=self.input,
            configuration={'time_limit_seconds': .06}, idempotency_key='one')
        self.assertTrue(error)
        self.assertEqual(value['job_id'], job.id)

    async def test_malformed_policy_rejected_before_state_allocation(self):
        self.connector.authorize = 'not a callable'
        path = self.root / 'invalid-policy'
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_HOOK_INVALID'):
            BindingRuntime({self.sid: self.service}, path)
        self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
