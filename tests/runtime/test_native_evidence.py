"""Run with the installed SDK/checker, outside the checkout; no model calls."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import sys
import unittest

from mcp import Client as MCPClient, StdioServerParameters
from conformance.assessment import CheckerRegistry, digest
from conformance.core_contract import ContractError
from conformance.preparation import verify_preparation
from foundry_capability_contract import MemoryJobStore, JobStatus
from ocp_candidate import Client
from ocp_candidate.native import NativeError
from ocp_runtime.native_domain import ReferenceDomain
from ocp_runtime.native_evidence import EvidenceService, compare_facts
from ocp_runtime.providers import make_provider


def input_data():
    return {'time_unit': 'minute', 'cost_unit': 'cost_unit',
            'workers': [{'id': 'alex', 'availability': [{'start': 0, 'end': 60}], 'max_minutes': 60},
                        {'id': 'blair', 'availability': [{'start': 0, 'end': 180}], 'max_minutes': 60}],
            'tasks': [{'id': 'task', 'start': 30, 'end': 90, 'eligible_workers': ['alex', 'blair'],
                       'costs': {'alex': 2, 'blair': 40}}]}


def overtime(rate=1):
    return [{'id': 'ot', 'kind': 'outside_availability_cost', 'enforcement': 'soft',
             'worker_rates': {'alex': rate}, 'unit': 'cost_unit_per_minute'}]


def breaks(*windows):
    return [{'id': 'break', 'kind': 'fixed_breaks', 'enforcement': 'hard',
             'breaks': [{'worker_id': 'alex', 'start': a, 'end': b} for a, b in windows]}]


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.provider = make_provider('worker.scheduling')
        self.client = ReferenceDomain(self.provider, problem_type='worker-scheduling')
        self.store = MemoryJobStore()
        self.service = EvidenceService({'worker-scheduling': self.client}, self.store)
        self.request = Client(self.provider).request(input_data(), request_id='evidence-case')

    def prepare(self, reqs=None, problem=None, **kwargs):
        return self.service.prepare('worker-scheduling', problem or self.request,
                                    [] if reqs is None else reqs, 'Original user requirement', tenant='owner', **kwargs)

    def finish(self, request, *, response=None, status=None):
        result = self.provider.execute(deepcopy(request)) if response is None else response
        self.assertEqual(result['kind'], 'result')
        job, _ = self.store.submit(tenant='owner', problem_type='worker-scheduling',
                                   idempotency_key='job-' + str(len(self.jobs)), request_hash=digest(request),
                                   caller='test', problem=request)
        self.jobs.append(job.id)
        self.store.claim(problem_type='worker-scheduling', worker_id='worker', lease_seconds=30)
        self.store.finish(job_id=job.id, worker_id='worker',
                          status=status or (JobStatus.INFEASIBLE if result['status']=='infeasible' else JobStatus.SUCCEEDED),
                          result=result)
        return job.id

    def explain(self, job, **kwargs):
        return self.service.explain('worker-scheduling', job, tenant='owner', **kwargs)

    @property
    def jobs(self):
        if not hasattr(self, '_jobs'):
            self._jobs = []
        return self._jobs

    def test_identity_records_exact_input_and_uninterpreted_text(self):
        original = deepcopy(self.request)
        record = self.prepare()
        self.assertEqual(record['problem'], original)
        self.assertEqual(record['verification']['prepared_request_sha256'], digest(original))
        self.assertEqual(record['source_text_interpretation'], 'NOT_CHECKED')
        record['problem']['input']['tasks'][0]['costs']['alex'] = 999
        self.assertEqual(self.request, original)
        self.assertEqual(self.prepare()['problem'], original)

    def test_overtime_partial_and_full_minutes_and_hard_workload(self):
        partial = self.prepare(overtime())
        self.assertEqual(partial['problem']['input']['tasks'][0]['costs']['alex'], 32)
        self.assertEqual(partial['problem']['input']['workers'][0]['max_minutes'], 60)
        full = deepcopy(self.request)
        full['input']['tasks'][0].update(start=60, end=120)
        self.assertEqual(self.prepare(overtime(), full)['problem']['input']['tasks'][0]['costs']['alex'], 62)
        partial['problem']['input']['workers'][0]['max_minutes'] = 90
        with self.assertRaisesRegex(ContractError, 'PREPARATION_MISMATCH'):
            verify_preparation(self.request, overtime(), partial['problem'])

    def test_vacuous_overtime_and_real_zero(self):
        self.request['input']['tasks'][0].update(start=0, end=60)
        original = self.prepare(overtime())
        self.assertEqual(original['problem']['input']['tasks'][0]['costs']['alex'], 2)
        self.assertEqual(self.prepare(overtime(0))['problem']['input']['tasks'][0]['costs']['alex'], 2)

    def test_break_boundaries_overlaps_and_many_windows(self):
        self.request['input']['workers'][0]['availability'] = [{'start': 0, 'end': 180}]
        touching = self.prepare(breaks((0, 30), (90, 120)))
        self.assertEqual(touching['problem'], self.request)
        overlapping = self.prepare(breaks((30, 40), (35, 50)))
        self.assertEqual(overlapping['problem']['input']['tasks'][0]['eligible_workers'], ['blair'])
        all_day = self.prepare(breaks((0, 180)))
        self.assertEqual(all_day['problem']['input']['workers'], self.request['input']['workers'])
        many = self.prepare(breaks(*[(i*10, i*10+1) for i in range(12)]))
        self.assertEqual(many['problem']['input']['tasks'][0]['eligible_workers'], ['blair'])

    def test_no_eligible_workers_is_ready_not_invalid(self):
        self.request['input']['tasks'][0].update(eligible_workers=['alex'], costs={'alex': 2})
        r = self.prepare(breaks((0, 180)))
        self.assertEqual(r['status'], 'READY')
        self.assertEqual(r['verification']['feasible_assignments'], 0)
        explained = self.explain(self.finish(r['problem']), preparation_id=r['preparation_id'])
        self.assertTrue(explained['facts']['infeasibility_verified'])
        self.assertIsNone(explained['facts']['objective']['value'])
        self.assertIsNone(explained['facts']['solution'])

    def test_invalid_and_unsupported_never_return_reduced_request(self):
        cases = [([{'id': 'v', 'kind': 'variable_start'}], 'UNSUPPORTED_REQUIREMENT'),
                 (overtime() + breaks((0, 20)), 'UNSUPPORTED_REQUIREMENT_COMBINATION'),
                 (overtime(-1), 'INVALID_REQUIREMENT'), (overtime(True), 'INVALID_REQUIREMENT'),
                 (overtime(1.5), 'INVALID_REQUIREMENT'), (breaks((60, 30)), 'INVALID_BREAK')]
        for rule, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(NativeError, code):
                self.prepare(rule)
        unknown = overtime(); unknown[0]['worker_rates'] = {'missing': 1}
        with self.assertRaisesRegex(NativeError, 'UNKNOWN_WORKER'):
            self.prepare(unknown)
        self.assertEqual(len(self.service._records), 0)

    def test_cost_limit_and_wrong_profile_version(self):
        with self.assertRaisesRegex(NativeError, 'PREPARED_INPUT_OUT_OF_SCOPE'):
            self.prepare(overtime(100000))
        self.request['domain_profile']['version'] = '0.2.0'
        with self.assertRaisesRegex(NativeError, 'UNSUPPORTED_MAPPING_PROFILE'):
            self.prepare(overtime())

    def test_invalid_original_fields_and_missing_data(self):
        self.request['input']['breaks'] = []
        with self.assertRaises(NativeError): self.prepare()
        del self.request['input']['breaks']
        del self.request['input']['tasks'][0]['costs']
        with self.assertRaises(NativeError): self.prepare(overtime())

    def test_prepare_preserves_missing_field_diagnostics(self):
        del self.request['input']['tasks'][0]['costs']['alex']
        for rules in ([], overtime()):
            with self.subTest(rules=rules), self.assertRaises(NativeError) as caught:
                self.prepare(rules)
            self.assertEqual(caught.exception.body['issues'][0]['fieldPath'], '/tasks/0/costs/alex')
            self.assertIn('cost', caught.exception.body['issues'][0]['message'].lower())
            self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.service._records, {})
        self.assertEqual(self.jobs, [])
        del self.request['input']['tasks'][0]['costs']
        with self.assertRaises(NativeError) as caught:
            self.prepare(overtime())
        self.assertEqual(caught.exception.body['issues'][0]['fieldPath'], '/tasks/0/costs')

    def test_bare_input_rejected_with_full_request_guidance(self):
        with self.assertRaises(NativeError) as caught:
            self.prepare(problem=self.request['input'])
        self.assertIn('catalog.requestTemplate', caught.exception.body['message'])
        self.assertTrue(caught.exception.body['issues'])
        self.assertEqual(self.service._records, {})

    def test_compact_preserves_ready_problem_hash_and_audit_record(self):
        full = self.prepare(overtime())
        compact = self.prepare(overtime(), detail='compact')
        self.assertEqual(full['preparation_id'], compact['preparation_id'])
        for key in ('problem', 'requirements', 'verification', 'mapping_facts'):
            self.assertEqual(full[key], compact[key])
        self.assertNotIn('original_problem', compact)
        self.assertNotIn('source_text', compact)
        self.assertLess(len(json.dumps(compact)), len(json.dumps(full)))
        self.assertEqual(self.prepare(overtime())['original_problem'], self.request)
        with self.assertRaisesRegex(NativeError, 'INVALID_EVIDENCE_DETAIL'):
            self.prepare(detail='invalid')

    def test_checked_assignment_rows_and_workloads(self):
        self.request['input'] = json.loads(Path('evidence-regressions.json').read_text())['input']
        answer = self.explain(self.finish(self.request))
        facts = answer['facts']['worker_assignment']
        self.assertEqual(facts['total_cost'], 16)
        self.assertEqual(sum(a['cost'] for a in facts['assignments']), 16)
        self.assertEqual([a['duration_minutes'] for a in facts['assignments']], [60]*6)
        loads = {w['worker_id']: w for w in facts['workloads']}
        self.assertEqual([loads[w]['assigned_minutes'] for w in ('alex', 'blair', 'casey')], [120]*3)
        self.assertEqual([loads[w]['remaining_minutes'] for w in ('alex', 'blair', 'casey')], [0,60,0])

    def test_break_overlap_and_all_constraint_count_are_distinct(self):
        self.request['input'] = json.loads(Path('evidence-regressions.json').read_text())['input']
        r = self.prepare(breaks((600,630)))
        facts = r['mapping_facts']
        self.assertEqual(facts['breaks'][0]['overlapping_task_ids'], ['valve','safety'])
        self.assertEqual(facts['breaks'][0]['removed_eligible_task_ids'], ['valve'])
        self.assertEqual((facts['assignments_checked'], facts['feasible_assignments']), (729,5))
        self.assertEqual(facts['feasible_count_scope'], 'ALL_ORIGINAL_CONSTRAINTS_AND_DECLARED_REQUIREMENTS')
        self.assertIsNone(facts['requirement_only_count'])
        self.assertEqual(facts['requirement_only_count_status'], 'NOT_COMPUTED')
        answer = self.explain(self.finish(r['problem']), preparation_id=r['preparation_id'])
        self.assertEqual(answer['preparation']['mapping_facts'], facts)
        self.assertEqual(answer['facts']['worker_assignment']['total_cost'], 19)

    def test_selected_overtime_cost_and_unused_worker_workload(self):
        r = self.prepare(overtime())
        answer = self.explain(self.finish(r['problem']), preparation_id=r['preparation_id'])
        facts = answer['facts']['worker_assignment']
        row = facts['assignments'][0]
        self.assertEqual(row['worker_id'], 'alex')
        self.assertEqual(row['cost'], 32)
        self.assertEqual(row['cost_adjustment']['original_pair_cost'], 2)
        self.assertEqual(row['cost_adjustment']['outside_original_availability_minutes'], 30)
        self.assertEqual(row['cost_adjustment']['additional_cost'], 30)
        self.assertEqual(facts['workloads'][1]['assigned_minutes'], 0)
        # Without a preparation link, do not claim the submitted cost's original decomposition.
        unlinked = self.explain(self.jobs[-1])['facts']['worker_assignment']
        self.assertNotIn('cost_adjustment', unlinked['assignments'][0])
        free = self.prepare(overtime(0))
        self.assertEqual(free['mapping_facts']['cost_adjustments'][0]['additional_cost'], 0)

    def test_canonical_request_schema_rejects_bare_and_unknown_fields(self):
        from jsonschema import Draft202012Validator
        from ocp_runtime.native_evidence_facts import request_schema
        validator = Draft202012Validator(request_schema())
        self.assertTrue(validator.is_valid(self.request))
        self.assertFalse(validator.is_valid(self.request['input']))
        changed = deepcopy(self.request); changed['invented'] = True
        self.assertFalse(validator.is_valid(changed))

    def test_seeded_mapping_equivalence(self):
        rng = random.Random(20261101)
        for index in range(80):
            p = deepcopy(self.request)
            for w in p['input']['workers']:
                w['max_minutes'] = rng.choice([0, 30, 60, 120])
            p['input']['tasks'] = []
            for j in range(rng.randint(1, 5)):
                a = rng.randrange(0, 150, 15)
                p['input']['tasks'].append({'id': str(j), 'start': a, 'end': a+rng.choice([15,30]),
                    'eligible_workers': ['alex','blair'], 'costs': {'alex': rng.randrange(10), 'blair': rng.randrange(10)}})
            rule = overtime(rng.randrange(4)) if index % 2 else breaks((rng.randrange(0, 90), 120))
            with self.subTest(index=index):
                r = self.prepare(rule, p)
                self.assertEqual(r['verification']['assignments_checked'], 2**len(p['input']['tasks']))
                self.assertEqual(r['verification']['status'], 'PASS')

    def test_mapping_at_profile_assignment_limit(self):
        p = deepcopy(self.request)
        p['input']['workers'] = [{'id': str(i), 'availability': [{'start': 0, 'end': 8}], 'max_minutes': 8}
                                for i in range(4)]
        p['input']['tasks'] = [{'id': str(i), 'start': i, 'end': i+1,
                               'eligible_workers': ['0','1','2','3'], 'costs': {str(w): w for w in range(4)}}
                              for i in range(8)]
        rule = [{'id':'b','kind':'fixed_breaks','enforcement':'hard',
                 'breaks':[{'worker_id':'0','start':0,'end':1}]}]
        r = self.prepare(rule, p)
        self.assertEqual(r['verification']['assignments_checked'], 65536)
        self.assertEqual(r['verification']['feasible_assignments'], 3 * 4**7)

    def test_checker_detects_changed_cost_and_task_time(self):
        r = self.prepare(overtime())
        p = deepcopy(r['problem']); p['input']['tasks'][0]['costs']['alex'] += 1
        with self.assertRaisesRegex(ContractError, 'PREPARATION_MISMATCH'):
            verify_preparation(self.request, overtime(), p)
        p = deepcopy(r['problem']); p['input']['tasks'][0]['start'] += 1
        with self.assertRaisesRegex(ContractError, 'PREPARATION_MISMATCH'):
            verify_preparation(self.request, overtime(), p)

    def test_observed_partial_assignment_and_overtime_regressions(self):
        from conformance.worker import evaluate
        fixture = json.loads(Path('evidence-regressions.json').read_text())
        self.request['input'] = fixture['input']
        expected = fixture['expectations']
        base = self.finish(self.request)
        self.assertEqual(self.explain(base)['facts']['objective']['value'], expected['base_optimum'])
        mapped = self.prepare(overtime())
        answer = self.explain(self.finish(mapped['problem']), preparation_id=mapped['preparation_id'], baseline_job_id=base)
        self.assertEqual(answer['comparison']['difference'], expected['outside_availability_increment'])
        partial = deepcopy(self.request)
        partial['input']['tasks'] = [t for t in partial['input']['tasks'] if t['id'] != 'panel']
        measured = evaluate(partial['input'], fixture['invalid_partial_assignment'])
        self.assertFalse(measured['feasible']); self.assertEqual(measured['violations']['workload'], 1)
        partial_facts = self.explain(self.finish(partial))['facts']
        self.assertEqual(partial_facts['objective']['value'], expected['without_panel_optimum'])
        alternative = evaluate(self.request['input'], fixture['invalid_alternative'])
        self.assertFalse(alternative['feasible']); self.assertEqual(alternative['violations']['no_overlap'], 1)
        # No partial assignment or cost is fabricated for a different impossible request.
        impossible = deepcopy(self.request)
        impossible['input']['tasks'][1].update(eligible_workers=[], costs={})
        facts = self.explain(self.finish(impossible))['facts']
        self.assertIsNone(facts['solution']); self.assertIsNone(facts['objective']['value'])

    def test_record_limit_and_idempotent_replay(self):
        self.service.max_records = 1
        a = self.prepare()
        self.assertEqual(a['preparation_id'], self.prepare()['preparation_id'])
        with self.assertRaisesRegex(NativeError, 'PREPARATION_RECORD_LIMIT'):
            self.prepare(overtime())

    def test_source_text_shape_and_tenant_isolation(self):
        with self.assertRaisesRegex(NativeError, 'INVALID_SOURCE_TEXT'):
            self.service.prepare('worker-scheduling', self.request, [], '', tenant='owner')
        r = self.prepare()
        job = self.finish(r['problem'])
        with self.assertRaisesRegex(NativeError, 'JOB_NOT_FOUND'):
            self.service.explain('worker-scheduling', job, tenant='other')
        with self.assertRaisesRegex(NativeError, 'UNSUPPORTED_DOMAIN'):
            self.service.explain('other', job, tenant='owner')
        other = self.service.prepare('worker-scheduling', self.request, [], 'Different', tenant='other')
        with self.assertRaisesRegex(NativeError, 'PREPARATION_NOT_FOUND'):
            self.explain(job, preparation_id=other['preparation_id'])

    def test_preparation_links_exact_job_and_rechecks_tampering(self):
        r = self.prepare(overtime())
        job = self.finish(r['problem'])
        answer = self.explain(job, preparation_id=r['preparation_id'])
        self.assertEqual(answer['facts']['objective']['value'], 32)
        self.assertEqual(answer['preparation']['status'], 'PASS')
        self.assertEqual(answer['verification']['request_sha256'], r['verification']['prepared_request_sha256'])
        changed = deepcopy(r['problem']); changed['request_id'] = 'changed'
        with self.assertRaisesRegex(NativeError, 'PREPARATION_JOB_MISMATCH'):
            self.explain(self.finish(changed), preparation_id=r['preparation_id'])
        key = ('owner', 'worker-scheduling', r['preparation_id'])
        self.service._records[key]['source_text'] = 'tampered'
        with self.assertRaisesRegex(NativeError, 'PREPARATION_JOB_MISMATCH'):
            self.explain(job, preparation_id=r['preparation_id'])

    def test_failed_check_suppresses_facts(self):
        result = self.provider.execute(self.request)
        result['metrics'][0]['value'] += 1
        answer = self.explain(self.finish(self.request, response=result))
        self.assertEqual(answer['status'], 'UNVERIFIED')
        self.assertIsNone(answer['facts'])
        self.assertEqual(answer['explanation_basis']['current']['verification_status'], 'FAIL')
        self.assertEqual(answer['explanation_basis']['comparison_status'], 'UNAVAILABLE')
        self.service.registry = CheckerRegistry()
        answer = self.explain(self.jobs[0])
        self.assertIsNone(answer['facts'])

    def test_incomplete_proof_suppresses_facts(self):
        from conformance.worker import verify_result
        from conformance.assessment import builtin_checkers
        entry = builtin_checkers().resolve(self.request['domain_profile'])
        def limited_checker(request, result):
            if result['status'] == 'optimal':
                raise ContractError('ORACLE_SCOPE_EXCEEDED')
            return verify_result(request, result)
        registry = CheckerRegistry()
        registry.register(self.request['domain_profile'], limited_checker, scope=entry.scope,
                          metric_id=entry.metric_id, value_key=entry.value_key, identity=entry.identity)
        self.service.registry = registry
        answer = self.explain(self.finish(self.request))
        self.assertEqual(answer['verification']['status'], 'INCOMPLETE')
        self.assertIsNone(answer['facts'])

    def test_zero_null_unknown_and_two_verified_costs(self):
        baseline = self.finish(self.request)
        r = self.prepare(overtime())
        current = self.finish(r['problem'])
        comparison = self.explain(current, preparation_id=r['preparation_id'], baseline_job_id=baseline)
        self.assertEqual(comparison['comparison']['difference'], -8)
        for name, identifier in [('current', current), ('baseline', baseline)]:
            source = comparison if name == 'current' else comparison['baseline']
            basis = comparison['explanation_basis'][name]
            self.assertEqual(basis['job_id'], identifier)
            self.assertEqual(basis['request_sha256'], source['verification']['request_sha256'])
            self.assertEqual(basis['response_sha256'], source['verification']['response_sha256'])
            self.assertEqual(basis['verification_status'], 'PASS')
        zero = deepcopy(self.request)
        zero['input']['tasks'][0]['costs'] = {'alex': 0, 'blair': 0}
        zero_job = self.finish(zero)
        self.assertEqual(self.explain(zero_job)['facts']['objective']['value'], 0)
        impossible = deepcopy(self.request)
        impossible['input']['tasks'][0].update(eligible_workers=[], costs={})
        no_job = self.finish(impossible)
        no_cost = self.explain(no_job, baseline_job_id=zero_job)
        self.assertEqual(no_cost['comparison']['reason'], 'NO_OBJECTIVE')
        self.assertIsNone(no_cost['comparison']['difference'])
        unknown = self.provider.execute(impossible)
        unknown.update(status='unknown', proof=None, termination='time_limit')
        unknown_job = self.finish(impossible, response=unknown)
        explanation = self.explain(unknown_job)
        self.assertEqual(explanation['facts']['result_status'], 'unknown')
        self.assertFalse(explanation['facts']['infeasibility_verified'])
        self.assertIsNone(explanation['facts']['objective']['value'])
        self.assertIsNone(explanation['facts']['worker_assignment'])
        self.assertIsNone(self.explain(no_job)['facts']['worker_assignment'])

    def test_absent_baseline_has_no_inferred_cost_or_validation_history(self):
        answer = self.explain(self.finish(self.request))
        self.assertEqual(answer['comparison']['reason'], 'BASELINE_NOT_PROVIDED')
        self.assertIsNone(answer['comparison']['difference'])
        self.assertFalse(answer['comparison']['accepted_inputs']['supplied_solution_accepted'])
        self.assertIn('reoptimizes', answer['comparison']['accepted_inputs']['supplied_assignment'])
        self.assertIsNone(answer['explanation_basis']['baseline'])
        self.assertEqual(answer['explanation_basis']['additional_claims'], 'NOT_CHECKED')
        self.assertEqual(answer['input_validation']['status'], 'NOT_RECORDED')

    def test_unhashable_result_remains_unverified_without_invented_hash(self):
        bad = self.provider.execute(self.request); bad['metrics'][0]['value'] = float('nan')
        answer = self.explain(self.finish(self.request, response=bad))
        self.assertIsNone(answer['facts'])
        self.assertEqual(answer['status'], 'UNVERIFIED')
        self.assertIsNone(answer['explanation_basis']['current']['response_sha256'])

    def test_comparison_requires_baseline_and_verified_results(self):
        with self.assertRaisesRegex(NativeError, 'BASELINE_JOB_REQUIRED'):
            self.explain('none', baseline_preparation_id='x')
        a = self.finish(self.request)
        b = self.finish(self.request)
        bad = self.provider.execute(self.request); bad['metrics'][0]['value'] += 1
        c = self.finish(self.request, response=bad)
        self.assertEqual(self.explain(c, baseline_job_id=a)['comparison']['reason'], 'UNVERIFIED_RESULT')
        self.assertEqual(self.explain(b, baseline_job_id=a)['comparison']['difference'], 0)

    def test_incomparable_units_definitions_profiles_and_configuration(self):
        answer = self.explain(self.finish(self.request))
        for field in ('unit', 'definition'):
            changed = deepcopy(answer)
            changed['facts']['objective'][field] = 'different'
            result = compare_facts(answer, self.request, changed, self.request)
            self.assertEqual(result['reason'], 'INCOMPARABLE_OBJECTIVES')
            self.assertIsNone(result['difference'])
        for field in ('domain_profile', 'execution_profile', 'configuration'):
            changed = deepcopy(self.request)
            changed[field] = {'changed': True}
            result = compare_facts(answer, self.request, answer, changed)
            self.assertEqual(result['reason'], 'INCOMPARABLE_OBJECTIVES')

    def test_pending_cancelled_failed_expired_and_missing_results(self):
        for status, code in [(JobStatus.QUEUED,'JOB_NOT_FINISHED'), (JobStatus.FAILED,'JOB_FAILED'),
                             (JobStatus.CANCELLED,'JOB_CANCELLED'), (JobStatus.SUCCEEDED,'BAD_ANSWER')]:
            store = MemoryJobStore()
            job, _ = store.submit(tenant='owner', problem_type='worker-scheduling', idempotency_key='k',
                                  request_hash='h', caller='test', problem=self.request)
            if status == JobStatus.CANCELLED:
                store.request_cancel(tenant='owner', problem_type='worker-scheduling', job_id=job.id)
            elif status != JobStatus.QUEUED:
                store.claim(problem_type='worker-scheduling', worker_id='w', lease_seconds=30)
                store.finish(job_id=job.id, worker_id='w', status=status)
            self.service.store = store
            with self.subTest(status=status), self.assertRaisesRegex(NativeError, code):
                self.explain(job.id)
        store = MemoryJobStore(clock=lambda: datetime.now(timezone.utc)-timedelta(days=30))
        job, _ = store.submit(tenant='owner', problem_type='worker-scheduling', idempotency_key='k',
                              request_hash='h', caller='test', problem=self.request)
        self.service.store = store
        with self.assertRaisesRegex(NativeError, 'JOB_EXPIRED'): self.explain(job.id)


class InstalledMCP(unittest.TestCase):
    def parameters(self, flags):
        return StdioServerParameters(command=sys.executable,
            args=['-I','-B','-m','ocp_runtime.native_mcp', *flags],
            env={'PATH': os.defpath, 'HOME': os.environ['HOME'], 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_legacy_tools_and_catalogs_unchanged(self):
        asyncio.run(self.compatibility())

    async def compatibility(self):
        signatures, catalogs = [], []
        for flags, count in [([],8), (['--verification'],9), (['--verification','--evidence'],11)]:
            async with MCPClient(self.parameters(flags), read_timeout_seconds=90) as host:
                tools = (await host.list_tools()).tools
                self.assertEqual(len(tools), count)
                signatures.append({t.name: t.model_dump(by_alias=True) for t in tools})
                values = {}
                for domain in ('routing-basic','worker-scheduling','inventory-replenishment'):
                    value = await host.call_tool('ocp_native_context', {'domain': domain})
                    self.assertFalse(value.is_error)
                    values[domain] = digest(value.structured_content['catalog'])
                    self.assertEqual('evidence' in value.structured_content, '--evidence' in flags)
                    if '--evidence' in flags:
                        self.assertEqual(value.structured_content['evidence']['constraint_scope']['intrinsic_rules_status'],
                                         'PACKAGED_PROFILE_SUMMARY')
                        scope = value.structured_content['evidence']['capability_scope']
                        self.assertEqual(scope['configured_domains'], value.structured_content['availableDomains'])
                        self.assertEqual(scope['selected_domain'], domain)
                        self.assertEqual(scope['selected_profile'], value.structured_content['catalog']['domainProfile'])
                        self.assertEqual(scope['selected_mapping_support'],
                                         'AVAILABLE' if domain == 'worker-scheduling' else 'NOT_AVAILABLE')
                catalogs.append(values)
                if '--evidence' in flags:
                    index = (await host.call_tool('ocp_native_context', {})).structured_content
                    self.assertIsNone(index['catalog'])
                    self.assertIsNone(index['evidence']['capability_scope']['selected_domain'])
                    self.assertEqual(index['evidence']['capability_scope']['selected_mapping_support'], 'SELECT_DOMAIN')
        for earlier, later in zip(signatures, signatures[1:]):
            for name, definition in earlier.items():
                self.assertEqual(definition, later[name])
        self.assertEqual(catalogs[0], catalogs[1]); self.assertEqual(catalogs[1], catalogs[2])
        baseline_python = os.environ.get('OCP_TEST_BASELINE_PYTHON')
        if baseline_python:
            params = self.parameters(['--verification'])
            params.command = baseline_python
            async with MCPClient(params, read_timeout_seconds=90) as host:
                old_tools = (await host.list_tools()).tools
                self.assertEqual({t.name: t.model_dump(by_alias=True) for t in old_tools}, signatures[1])
                for domain, expected in catalogs[0].items():
                    result = await host.call_tool('ocp_native_context', {'domain':domain})
                    self.assertFalse(result.is_error)
                    self.assertEqual(digest(result.structured_content['catalog']), expected)
        Path('evidence-mcp-compatibility.json').write_text(json.dumps({
            'tool_counts': [len(s) for s in signatures], 'existing_tool_definitions_identical': True,
            'prior_installed_candidate_compared': bool(baseline_python),
            'catalogs_identical': True, 'catalogs': catalogs[0]}, indent=2)+'\n')

    def test_custom_profile_identity_and_explanation(self):
        asyncio.run(self.custom_profile())

    async def custom_profile(self):
        params = StdioServerParameters(command=sys.executable,
            args=['-I','-B','-m','ocp_runtime.native_extension','--extension','ocp_budget_engine.registration:extension',
                  '--verification','--checker-factory','ocp_budget_check:registry','--evidence'],
            env={'PATH':os.defpath, 'HOME':os.environ['HOME'], 'PYTHONDONTWRITEBYTECODE':'1'})
        async with MCPClient(params, read_timeout_seconds=90) as host:
            async def call(name, args):
                r = await host.call_tool(name, args)
                self.assertFalse(r.is_error, r.structured_content)
                return r.structured_content
            domain = 'budget-selection'
            context = await call('ocp_native_context', {'domain':domain})
            scope = context['evidence']['capability_scope']
            self.assertEqual(scope['configured_domains'], [domain])
            self.assertEqual(scope['selected_profile']['id'], 'example.budget-selection')
            self.assertEqual(scope['selected_mapping_support'], 'NOT_AVAILABLE')
            self.assertEqual(context['evidence']['constraint_scope']['intrinsic_rules_status'], 'NOT_SUMMARIZED')
            self.assertIsNone(context['evidence']['constraint_scope']['intrinsic_rules'])
            self.assertEqual(context['evidence']['input_policy']['status'], 'SELECTED_CATALOG')
            problem = deepcopy(context['catalog']['requestTemplate'])
            problem.update(request_id='custom-evidence', input=json.loads(Path('budget-input.json').read_text()))
            record = await call('ocp_native_prepare', {'domain':domain,'problem':problem,'requirements':[],
                               'source_text':'Select projects within the supplied budget.'})
            self.assertTrue((await call('ocp_native_validate', {'domain':domain,'problem':record['problem']}))['valid'])
            job = (await call('ocp_native_submit', {'domain':domain,'problem':record['problem'],
                               'idempotency_key':'custom-evidence'}))['job']
            deadline = asyncio.get_running_loop().time()+60
            while job['status'] in ('queued','running'):
                self.assertLess(asyncio.get_running_loop().time(), deadline)
                await asyncio.sleep(.05)
                job = await call('ocp_native_job', {'domain':domain,'job_id':job['jobId']})
            answer = await call('ocp_native_explain', {'domain':domain,'job_id':job['jobId'],
                                'preparation_id':record['preparation_id']})
            self.assertEqual(answer['status'], 'VERIFIED')
            self.assertTrue(answer['facts']['optimality_verified'])
            self.assertEqual(answer['verification']['domain_profile']['id'], 'example.budget-selection')
            self.assertIsNone(answer['facts']['worker_assignment'])
            self.assertEqual(answer['input_validation']['origin'], 'EXPLICIT_VALIDATE_THEN_SUBMIT')
            self.assertEqual(answer['explanation_basis']['current']['request_sha256'], digest(record['problem']))
            Path('evidence-custom-profile.json').write_text(json.dumps(answer, indent=2)+'\n')

    def test_installed_prepare_solve_explain_and_compare(self):
        asyncio.run(self.journey())

    async def journey(self):
        inputs = json.loads(Path('inputs.json').read_text())
        events = []
        async with MCPClient(self.parameters(['--verification','--evidence']), read_timeout_seconds=90) as host:
            async def call(name, args, error=False):
                result = await host.call_tool(name, args)
                self.assertEqual(result.is_error, error, result.structured_content)
                self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                events.append({'tool': name, 'arguments': args, 'response': result.structured_content})
                return result.structured_content

            async def solve(domain, record, key):
                checked = await call('ocp_native_validate', {'domain':domain, 'problem': record['problem']})
                self.assertTrue(checked['valid'])
                job = (await call('ocp_native_submit', {'domain':domain, 'problem':record['problem'],
                                   'idempotency_key':key}))['job']
                deadline = asyncio.get_running_loop().time() + 60
                while job['status'] in ('queued','running'):
                    self.assertLess(asyncio.get_running_loop().time(), deadline)
                    await asyncio.sleep(.05)
                    job = await call('ocp_native_job', {'domain':domain, 'job_id':job['jobId']})
                return job['jobId']

            for domain in ('routing-basic','worker-scheduling','inventory-replenishment'):
                catalog = (await call('ocp_native_context', {'domain':domain}))['catalog']
                request = deepcopy(catalog['requestTemplate'])
                request.update(request_id='evidence-'+domain, input=deepcopy(inputs[catalog['domainProfile']['id']]))
                record = await call('ocp_native_prepare', {'domain':domain,'problem':request,
                                    'requirements':[], 'source_text':'Use the supplied synthetic input.'})
                job_id = await solve(domain, record, domain)
                answer = await call('ocp_native_explain', {'domain':domain,'job_id':job_id,
                                    'preparation_id':record['preparation_id']})
                self.assertEqual(answer['status'], 'VERIFIED')
                self.assertEqual(answer['preparation']['status'], 'PASS')
                self.assertEqual(answer['verification']['request_sha256'], digest(request))
                self.assertEqual(answer['input_validation']['status'], 'PASS')
                self.assertEqual(answer['input_validation']['origin'], 'EXPLICIT_VALIDATE_THEN_SUBMIT')
                self.assertEqual(answer['input_validation']['request_sha256'], digest(request))
                self.assertEqual(answer['comparison']['reason'], 'BASELINE_NOT_PROVIDED')
                if domain != 'worker-scheduling':
                    continue
                request.update(request_id='outside-availability', input=input_data())
                base = await call('ocp_native_prepare', {'domain':domain,'problem':request,
                                  'requirements':[], 'source_text':'Hard availability baseline.'})
                base_job = await solve(domain, base, 'baseline')
                mapped = await call('ocp_native_prepare', {'domain':domain,'problem':request,
                                    'requirements':overtime(), 'source_text':'Allow time outside Alex availability at 1 cost unit/minute; workload stays 60.'})
                mapped_job = await solve(domain, mapped, 'overtime')
                answer = await call('ocp_native_explain', {'domain':domain,'job_id':mapped_job,
                                    'preparation_id':mapped['preparation_id'], 'baseline_job_id':base_job,
                                    'baseline_preparation_id':base['preparation_id']})
                self.assertEqual(answer['facts']['objective']['value'], 32)
                self.assertEqual(answer['baseline']['facts']['objective']['value'], 40)
                self.assertEqual(answer['comparison']['difference'], -8)
                mismatch = await call('ocp_native_explain', {'domain':domain,'job_id':base_job,
                                      'preparation_id':mapped['preparation_id']}, True)
                self.assertEqual(mismatch['code'], 'PREPARATION_JOB_MISMATCH')
                unsupported = await call('ocp_native_prepare', {'domain':domain,'problem':request,
                                         'requirements':[{'id':'start','kind':'variable_start'}],
                                         'source_text':'Optimize start times too.'}, True)
                self.assertEqual(unsupported['code'], 'UNSUPPORTED_REQUIREMENT')
        Path('evidence-mcp-journey.json').write_text(json.dumps({'model_calls':0,'events':events}, indent=2)+'\n')

    def test_installed_submit_without_validate_and_replay_receipt(self):
        asyncio.run(self.submit_receipt())

    async def submit_receipt(self):
        events = []
        async with MCPClient(self.parameters(['--verification','--evidence']), read_timeout_seconds=90) as host:
            async def call(name, args, error=False):
                result = await host.call_tool(name, args)
                self.assertEqual(result.is_error, error, result.structured_content)
                events.append({'tool': name, 'arguments': args, 'response': result.structured_content})
                return result.structured_content
            domain = 'worker-scheduling'
            context = await call('ocp_native_context', {'domain':domain})
            request = deepcopy(context['catalog']['requestTemplate'])
            request.update(request_id='no-explicit-validate', input=input_data())
            invalid = deepcopy(request); del invalid['input']['tasks'][0]['costs']['alex']
            bad = await call('ocp_native_submit', {'domain':domain,'problem':invalid,'idempotency_key':'receipt'}, True)
            self.assertEqual(bad['code'], 'INVALID_PROBLEM')
            self.assertEqual(bad['issues'][0]['fieldPath'], '/tasks/0/costs/alex')
            # Same key after invalid input succeeds: the rejected input created no job.
            args = {'domain':domain,'problem':request,'idempotency_key':'receipt'}
            response = await call('ocp_native_submit', args)
            self.assertFalse(response['replayed'])
            proof = response['input_validation']
            self.assertEqual(proof['origin'], 'SUBMIT_PRECHECK')
            self.assertFalse(proof['explicit_validate_observed'])
            await call('ocp_native_validate', {'domain':domain,'problem':request})
            replay = await call('ocp_native_submit', args)
            self.assertTrue(replay['replayed'])
            self.assertEqual(replay['input_validation'], proof)
            job = response['job']
            deadline = asyncio.get_running_loop().time()+60
            while job['status'] in ('queued','running'):
                self.assertLess(asyncio.get_running_loop().time(), deadline)
                await asyncio.sleep(.05)
                job = await call('ocp_native_job', {'domain':domain,'job_id':job['jobId']})
            answer = await call('ocp_native_explain', {'domain':domain,'job_id':job['jobId']})
            self.assertEqual(answer['input_validation'], proof)
            self.assertEqual(answer['explanation_basis']['current']['request_sha256'], digest(request))
            self.assertEqual(answer['comparison']['reason'], 'BASELINE_NOT_PROVIDED')
        Path('evidence-mcp-validation-receipt.json').write_text(json.dumps({'model_calls':0,'events':events}, indent=2)+'\n')

    def test_installed_usability_schema_diagnostics_and_short_workflow(self):
        asyncio.run(self.usability())

    async def usability(self):
        from jsonschema import Draft202012Validator
        events = []
        async with MCPClient(self.parameters(['--verification','--evidence']), read_timeout_seconds=90) as host:
            tools = {t.name: t for t in (await host.list_tools()).tools}
            schema = tools['ocp_native_prepare'].input_schema['properties']['problem']
            self.assertIn('input', schema['required'])
            self.assertIn('configuration', schema['required'])
            self.assertFalse(Draft202012Validator(schema).is_valid(input_data()))
            async def call(name, args, error=False):
                r = await host.call_tool(name, args)
                self.assertEqual(r.is_error, error, r.structured_content)
                events.append({'tool': name, 'arguments': args, 'response': r.structured_content})
                return r.structured_content
            domain = 'worker-scheduling'
            context = await call('ocp_native_context', {'domain':domain})
            request = deepcopy(context['catalog']['requestTemplate'])
            request.update(request_id='usability', input=json.loads(Path('evidence-regressions.json').read_text())['input'])
            missing = deepcopy(request); del missing['input']['tasks'][0]['costs']['alex']
            bad = await call('ocp_native_prepare', {'domain':domain, 'problem':missing,
                             'requirements':[], 'source_text':'Missing cost'}, True)
            self.assertEqual(bad['issues'][0]['fieldPath'], '/tasks/0/costs/alex')
            record = await call('ocp_native_prepare', {'domain':domain, 'problem':request,
                                'requirements':breaks((600,630)), 'source_text':'Alex break 600 to 630', 'detail':'compact'})
            self.assertNotIn('original_problem', record)
            self.assertTrue((await call('ocp_native_validate', {'domain':domain,'problem':record['problem']}))['valid'])
            job = (await call('ocp_native_submit', {'domain':domain,'problem':record['problem'],
                                                 'idempotency_key':'usability'}))['job']
            deadline = asyncio.get_running_loop().time()+60
            while job['status'] in ('queued','running'):
                self.assertLess(asyncio.get_running_loop().time(), deadline)
                await asyncio.sleep(.05)
                job = await call('ocp_native_job', {'domain':domain,'job_id':job['jobId']})
            answer = await call('ocp_native_explain', {'domain':domain,'job_id':job['jobId'],
                                                     'preparation_id':record['preparation_id']})
            self.assertEqual(answer['verification']['status'], 'PASS')
            self.assertEqual(answer['facts']['worker_assignment']['total_cost'], 19)
            self.assertEqual(answer['preparation']['mapping_facts']['breaks'][0]['overlapping_task_ids'], ['valve','safety'])
            self.assertFalse({'ocp_native_result','ocp_native_verify','ocp_native_evaluate'} & {e['tool'] for e in events})
        Path('evidence-usability-mcp.json').write_text(json.dumps({'model_calls':0,'events':events}, indent=2)+'\n')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    summary = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': len(result.skipped), 'model_calls': 0, 'scope': 'Installed local evidence candidate'}
    Path('evidence-test-result.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))
    raise SystemExit(not result.wasSuccessful())
