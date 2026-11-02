"""Installed registry isolation and separately packaged budget evidence, no model."""
import asyncio
from copy import deepcopy
from dataclasses import fields
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from mcp import Client as MCPClient, StdioServerParameters
from conformance.assessment import CheckerRegistry, digest
from conformance.core_contract import ContractError
from conformance.preparation import WORKER
from foundry_capability_contract import MemoryJobStore, JobStatus
from ocp_candidate import Client
from ocp_candidate.native import NativeError
from ocp_runtime.native_domain import ReferenceDomain
from ocp_runtime.native_evidence import EvidenceService
from ocp_runtime.native_evidence_registry import (
    FEATURE_VERSION, EvidenceRegistry, builtin_evidence, invoke, load_evidence_registry)
from ocp_runtime.providers import make_provider


def registration(**changes):
    entry = builtin_evidence().resolve(WORKER)
    arguments = {field.name: getattr(entry, field.name) for field in fields(entry)}
    arguments['feature_version'] = FEATURE_VERSION
    arguments.update(changes)
    return arguments


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.provider = make_provider('worker.scheduling')
        self.client = ReferenceDomain(self.provider, problem_type='worker-scheduling')
        self.store = MemoryJobStore()
        data = json.loads(Path('inputs.json').read_text())['worker.scheduling']
        self.request = Client(self.provider).request(data, request_id='registry')

    def service(self, **changes):
        registered = EvidenceRegistry(); registered.register(**registration(**changes))
        return EvidenceService({'worker-scheduling': self.client}, self.store, evidence_registry=registered)

    def prepare(self, service, rules=None):
        return service.prepare('worker-scheduling', self.request, rules or [], 'Synthetic requirement', tenant='owner')

    def finish(self, request=None, result=None):
        request = self.request if request is None else request
        response = self.provider.execute(request) if result is None else result
        job, _ = self.store.submit(tenant='owner', problem_type='worker-scheduling', idempotency_key='job',
            request_hash=digest(request), caller='test', problem=request)
        self.store.claim(problem_type='worker-scheduling', worker_id='w', lease_seconds=30)
        self.store.finish(job_id=job.id, worker_id='w', status=JobStatus.SUCCEEDED, result=response)
        return job.id

    def explain(self, service, job, **kw):
        return service.explain('worker-scheduling', job, tenant='owner', **kw)

    def test_duplicate_and_version_mismatch(self):
        registry = builtin_evidence()
        with self.assertRaisesRegex(ContractError, 'DUPLICATE_EVIDENCE_HANDLER'):
            registry.register(**registration())
        with self.assertRaisesRegex(ContractError, 'EVIDENCE_VERSION_MISMATCH'):
            EvidenceRegistry().register(**registration(feature_version='0.4.0'))
        self.assertIsNone(registry.resolve({'id': WORKER['id'], 'version': '99'}))

    def test_malformed_profile_is_rejected_as_input_not_dispatched(self):
        for profile in (None, [], {'id': [], 'version': '0.1.0'}, {'id': WORKER['id'], 'version': {}}):
            self.assertIsNone(builtin_evidence().resolve(profile))
            request = deepcopy(self.request); request['domain_profile'] = profile
            with self.assertRaises(NativeError) as caught:
                self.service().prepare('worker-scheduling', request, [], 'Bad profile', tenant='owner')
            self.assertIn(caught.exception.code, ('SCHEMA_INVALID', 'INVALID_ORIGINAL_PROBLEM'))

    def test_invalid_registration_and_schema_are_rejected(self):
        for changes in ({'identity': {}}, {'prepare': None}, {'mapping_supported': 'yes'},
                        {'requirements_schema': {'type': 'object'}},
                        {'requirements_schema': {'type': 'array', 'items': {'$ref': 'https://example.invalid'}}}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                EvidenceRegistry().register(**registration(**changes))

    def test_snapshot_and_returned_metadata_are_isolated(self):
        source = registration(); registry = EvidenceRegistry(); registry.register(**source)
        frozen = registry.snapshot()
        source['requirements_schema']['maxItems'] = 100
        returned = frozen.resolve(WORKER); returned.identity['id'] = 'changed'
        self.assertEqual(frozen.resolve(WORKER).identity['id'], 'ocp.worker-evidence')
        self.assertEqual(frozen.resolve(WORKER).requirements_schema['maxItems'], 1)
        with self.assertRaisesRegex(ContractError, 'EVIDENCE_REGISTRY_FROZEN'):
            frozen.register(**registration())

    def test_factory_validation_and_no_automatic_import(self):
        with patch('ocp_runtime.native_evidence_registry.import_module', side_effect=AssertionError('import')):
            for name in ('https://example.test', 'pkg:fn()', 'pkg:fn;code'):
                with self.assertRaisesRegex(ContractError, 'INVALID_EVIDENCE_FACTORY'):
                    load_evidence_registry(name)
        self.assertIsNotNone(load_evidence_registry().resolve(WORKER))

    def test_callback_mutation_and_non_json_are_rejected(self):
        data = {'x': 1}
        def mutate(value):
            value['x'] = 2
        with self.assertRaisesRegex(ContractError, 'EVIDENCE_HANDLER_MUTATED_INPUT'):
            invoke(mutate, data)
        self.assertEqual(data, {'x': 1})
        with self.assertRaises(ContractError):
            invoke(lambda value: float('nan'), data)
        with self.assertRaisesRegex(ContractError, 'EVIDENCE_HANDLER_FAILED'):
            invoke(lambda value: 1/0, data)

    def test_invalid_preparation_report_is_not_saved(self):
        original = registration()['verify_preparation']
        for change in ({'status': 'FAIL'}, {'prepared_request_sha256': 'wrong'}, {'checker': {}}):
            def bad(a, b, c):
                return {**original(a, b, c), **change}
            service = self.service(verify_preparation=bad)
            with self.assertRaisesRegex(NativeError, 'INVALID_PREPARATION_REPORT'):
                self.prepare(service)
            self.assertFalse(service._records)

    def test_mutating_mapper_never_saves_a_record(self):
        def mutate(request, requirements):
            request['request_id'] = 'changed'
            return request, {'id': 'identity', 'version': FEATURE_VERSION}
        service = self.service(prepare=mutate)
        with self.assertRaisesRegex(NativeError, 'EVIDENCE_HANDLER_MUTATED_INPUT'):
            self.prepare(service)
        self.assertFalse(service._records)
        self.assertEqual(self.request['request_id'], 'registry')

    def test_catalog_drift_invalidates_preparation(self):
        service = self.service(); record = self.prepare(service); job = self.finish(record['problem'])
        catalog = self.client.capabilities(); catalog['catalogVersion'] = 'changed'
        with patch.object(self.client, 'capabilities', return_value=catalog):
            with self.assertRaisesRegex(NativeError, 'PREPARATION_CATALOG_CHANGED'):
                self.explain(service, job, preparation_id=record['preparation_id'])

    def test_catalog_drift_during_prepare_is_rejected(self):
        service = self.service(); initial = self.client.capabilities(); changed = {**initial, 'catalogVersion': 'changed'}
        with patch.object(self.client, 'capabilities', side_effect=[initial, changed]):
            with self.assertRaisesRegex(NativeError, 'PREPARATION_CATALOG_CHANGED'):
                self.prepare(service)
        self.assertFalse(service._records)

    def test_changed_handler_cannot_reinterpret_old_record(self):
        service = self.service(); record = self.prepare(service); job = self.finish(record['problem'])
        registry = EvidenceRegistry()
        registry.register(**registration(identity={'id': 'other', 'version': '1'}))
        service.evidence_registry = registry.snapshot()
        with self.assertRaisesRegex(NativeError, 'PREPARATION_HANDLER_CHANGED'):
            self.explain(service, job, preparation_id=record['preparation_id'])

    def test_wrong_detail_is_rejected_by_separate_checker(self):
        original = registration()['solution_facts']
        def bad(*args):
            data = original(*args); data['workloads'][0]['assigned_minutes'] += 1
            return data
        with self.assertRaisesRegex(NativeError, 'EXPLANATION_FACTS_MISMATCH'):
            self.explain(self.service(solution_facts=bad), self.finish())

    def test_invalid_detail_report_is_not_accepted(self):
        with self.assertRaisesRegex(NativeError, 'INVALID_DETAIL_REPORT'):
            self.explain(self.service(verify_solution_facts=lambda *args: {'status': 'PASS'}), self.finish())

    def test_failed_result_check_never_calls_detail_builder(self):
        def unexpected(*args):
            self.fail('details called without result verification')
        service = self.service(solution_facts=unexpected)
        service.registry = CheckerRegistry()
        result = self.explain(service, self.finish())
        self.assertEqual(result['status'], 'UNVERIFIED')
        self.assertIsNone(result['facts'])

    def test_handler_context_and_details_match_stored_input(self):
        service = self.service(); context = service.context('worker-scheduling', self.client.capabilities())
        record = self.prepare(service); result = self.explain(service, self.finish(), preparation_id=record['preparation_id'])
        self.assertEqual(context['selected_evidence_handler'], record['handler'])
        detail = result['facts']['domain_details']
        self.assertEqual(detail['data'], result['facts']['worker_assignment'])
        self.assertEqual(detail['verification']['request_sha256'], digest(self.request))
        self.assertEqual(detail['verification']['details_sha256'], digest(detail['data']))

    def test_missing_registration_allows_only_identity(self):
        service = EvidenceService({'worker-scheduling': self.client}, self.store, evidence_registry=EvidenceRegistry())
        self.assertEqual(self.prepare(service)['problem'], self.request)
        with self.assertRaisesRegex(NativeError, 'UNSUPPORTED_MAPPING_PROFILE'):
            self.prepare(service, [{'kind': 'fixed_breaks'}])
        self.assertIsNone(self.explain(service, self.finish())['facts']['domain_details'])

    def test_no_mapping_registration_cannot_accept_nonempty_requirements(self):
        service = self.service(mapping_supported=False)
        with self.assertRaisesRegex(NativeError, 'UNSUPPORTED_REQUIREMENT'):
            self.prepare(service, [{'kind': 'fixed_breaks'}])
        context = service.context('worker-scheduling', self.client.capabilities())
        self.assertIsNone(context['mapped_profile'])
        self.assertEqual(context['capability_scope']['selected_mapping_support'], 'NOT_AVAILABLE')

    def test_identity_cannot_change_request_even_with_a_lying_checker(self):
        def changed(request, requirements):
            result = deepcopy(request); result['request_id'] = 'other'
            return result, {'id': 'identity', 'version': FEATURE_VERSION}
        service = self.service(prepare=changed, verify_preparation=lambda *args: {'status': 'PASS'})
        with self.assertRaisesRegex(NativeError, 'PREPARATION_MISMATCH'):
            self.prepare(service)
        self.assertFalse(service._records)

    def test_installed_budget_package_and_mcp_journey(self):
        asyncio.run(self.budget_journey())

    async def budget_journey(self):
        params = StdioServerParameters(command=sys.executable,
            args=['-I', '-B', '-m', 'ocp_runtime.native_extension', '--extension', 'ocp_budget_engine.registration:extension',
                  '--verification', '--checker-factory', 'ocp_budget_check:registry', '--evidence',
                  '--evidence-factory', 'ocp_budget_evidence:registry'],
            env={'PATH': os.defpath, 'HOME': os.environ['HOME'], 'PYTHONDONTWRITEBYTECODE': '1'})
        events = []
        async with MCPClient(params, read_timeout_seconds=60) as host:
            async def call(name, arguments, error=False):
                result = await host.call_tool(name, arguments)
                self.assertEqual(result.is_error, error, result.structured_content)
                events.append({'tool': name, 'arguments': arguments, 'response': result.structured_content})
                return result.structured_content
            self.assertEqual(len((await host.list_tools()).tools), 11)
            name = 'budget-selection'
            context = await call('ocp_native_context', {'domain': name})
            self.assertEqual(context['evidence']['requirements_schema'], {'type': 'array', 'maxItems': 0})
            self.assertEqual(context['evidence']['selected_evidence_handler']['handler']['id'], 'ocp-budget-evidence-example')
            request = deepcopy(context['catalog']['requestTemplate'])
            request.update(request_id='budget-evidence', input=json.loads(Path('budget-input.json').read_text()))
            rejected = await call('ocp_native_prepare', {'domain': name, 'problem': request,
                'requirements': [{'id': 'b', 'kind': 'fixed_breaks'}], 'source_text': 'Unsupported worker rule'}, True)
            self.assertEqual(rejected['code'], 'UNSUPPORTED_REQUIREMENT')
            record = await call('ocp_native_prepare', {'domain': name, 'problem': request, 'requirements': [], 'source_text': 'Choose within budget'})
            self.assertEqual(record['problem'], request)
            self.assertTrue((await call('ocp_native_validate', {'domain': name, 'problem': request}))['valid'])
            job = (await call('ocp_native_submit', {'domain': name, 'problem': request, 'idempotency_key': 'budget-evidence'}))['job']
            deadline = asyncio.get_running_loop().time()+60
            while job['status'] in ('queued', 'running'):
                self.assertLess(asyncio.get_running_loop().time(), deadline)
                await asyncio.sleep(.05)
                job = await call('ocp_native_job', {'domain': name, 'job_id': job['jobId']})
            answer = await call('ocp_native_explain', {'domain': name, 'job_id': job['jobId'], 'preparation_id': record['preparation_id']})
            self.assertEqual(answer['status'], 'VERIFIED')
            detail = answer['facts']['domain_details']
            self.assertEqual(detail['verification']['status'], 'PASS')
            self.assertEqual(detail['data']['total_benefit'], answer['facts']['objective']['value'])
            selected = set(answer['facts']['solution']['selected'])
            items = [i for i in request['input']['items'] if i['id'] in selected]
            self.assertEqual(detail['data']['items'], items)
            self.assertEqual(detail['data']['used_capacity'], sum(i['cost'] for i in items))
            self.assertEqual(detail['data']['remaining_capacity'], request['input']['capacity']-sum(i['cost'] for i in items))
            self.assertIsNone(answer['facts']['worker_assignment'])
        Path('evidence-registry-budget-mcp.json').write_text(json.dumps(events, indent=2)+'\n')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    report = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped), 'model_calls': 0}
    Path('evidence-registry-test-result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    raise SystemExit(not result.wasSuccessful())
