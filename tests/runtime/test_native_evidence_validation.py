"""Local validation-observation regressions; fixture submits do not run a solver."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

from conformance.assessment import digest
from foundry_capability_contract import MemoryJobStore
from ocp_candidate import Client
from ocp_candidate.native import NativeError
from ocp_runtime.native_domain import ReferenceDomain
from ocp_runtime.native_evidence import EvidenceService
from ocp_runtime.providers import make_provider


class RecordingClient:
    """Real provider validation and job-store replay, instrumented for unit tests."""
    def __init__(self, store):
        self.provider = make_provider('worker.scheduling')
        self.domain = ReferenceDomain(self.provider, problem_type='worker-scheduling')
        self.catalog = self.domain.capabilities()
        self.store, self.calls, self.validations = store, [], []
        self.failure = self.invalid_reply = None
        self.mutate = self.drift = False

    def capabilities(self):
        return deepcopy(self.catalog)

    def validate(self, problem):
        self.validations.append(deepcopy(problem))
        if self.mutate:
            problem['request_id'] = 'mutated'
        if self.drift:
            self.catalog['catalogVersion'] += '-changed'
        return self.domain.validate(problem) if self.invalid_reply is None else deepcopy(self.invalid_reply)

    def submit(self, problem, *, tenant, idempotency_key):
        self.calls.append(deepcopy(problem))
        if self.failure:
            raise NativeError(self.failure)
        job, created = self.store.submit(tenant=tenant, problem_type='worker-scheduling',
            idempotency_key=idempotency_key, request_hash=digest(problem), caller='unit-test', problem=problem)
        return {'job': {'jobId': job.id, 'status': job.status.value}, 'replayed': not created}


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryJobStore()
        self.client = RecordingClient(self.store)
        self.service = EvidenceService({'worker-scheduling': self.client}, self.store)
        data = {'time_unit': 'minute', 'cost_unit': 'cost_unit',
            'workers': [{'id': 'w', 'availability': [{'start': 0, 'end': 120}], 'max_minutes': 60}],
            'tasks': [{'id': 't', 'start': 0, 'end': 60, 'eligible_workers': ['w'], 'costs': {'w': 7}}]}
        self.request = Client(self.client.provider).request(data, request_id='validation-receipt')

    def validate(self, problem=None, tenant='owner'):
        return self.service.validate('worker-scheduling', self.request if problem is None else problem, tenant=tenant)

    def submit(self, key='key', problem=None, tenant='owner'):
        return self.service.submit('worker-scheduling', self.request if problem is None else problem,
                                   tenant=tenant, idempotency_key=key)

    def receipt(self, response, *, tenant='owner', problem=None):
        return self.service.validation.for_job('worker-scheduling', response['job']['jobId'],
            self.request if problem is None else problem, tenant=tenant)

    def test_omitted_validate_is_checked_but_not_claimed_as_explicit(self):
        response = self.submit()
        proof = response['input_validation']
        self.assertEqual(proof['origin'], 'SUBMIT_PRECHECK')
        self.assertFalse(proof['explicit_validate_observed'])
        self.assertTrue(proof['checked_before_original_submit'])
        self.assertEqual(proof['request_sha256'], digest(self.request))
        self.assertEqual(self.client.validations, [self.request])
        self.assertEqual(self.client.calls, [self.request])
        self.assertEqual(self.receipt(response), proof)

    def test_explicit_validate_is_preserved_and_submit_rechecks(self):
        expected = self.client.domain.validate(self.request)
        self.assertEqual(self.validate(), expected)
        response = self.submit()
        self.assertEqual(response['input_validation']['origin'], 'EXPLICIT_VALIDATE_THEN_SUBMIT')
        self.assertEqual(len(self.client.validations), 2)
        self.assertEqual(response['input_validation']['validation_sha256'], digest(expected))

    def test_invalid_input_has_field_diagnostic_and_no_submit(self):
        bad = deepcopy(self.request); del bad['input']['tasks'][0]['costs']['w']
        self.assertFalse(self.validate(bad)['valid'])
        with self.assertRaises(NativeError) as caught:
            self.submit(problem=bad)
        self.assertEqual(caught.exception.code, 'INVALID_PROBLEM')
        self.assertEqual(caught.exception.body['issues'][0]['fieldPath'], '/tasks/0/costs/w')
        self.assertEqual(self.client.calls, [])
        self.assertEqual(len(self.service.validation._jobs), 0)

    def test_changed_input_catalog_or_tenant_does_not_borrow_explicit_observation(self):
        self.validate()
        changed = deepcopy(self.request); changed['input']['tasks'][0]['costs']['w'] = 8
        self.assertFalse(self.submit('changed', changed)['input_validation']['explicit_validate_observed'])
        self.assertFalse(self.submit('other', tenant='other')['input_validation']['explicit_validate_observed'])
        self.client.catalog['catalogVersion'] = 'new-version'
        self.assertFalse(self.submit('catalog')['input_validation']['explicit_validate_observed'])

    def test_domain_isolation_and_unsupported_domain(self):
        self.validate()
        self.service.clients['other'] = self.client
        response = self.service.submit('other', self.request, tenant='owner', idempotency_key='other')
        self.assertFalse(response['input_validation']['explicit_validate_observed'])
        self.assertEqual(self.receipt(response)['status'], 'NOT_RECORDED')
        with self.assertRaisesRegex(NativeError, 'UNSUPPORTED_DOMAIN'):
            self.service.submit('missing', self.request, tenant='owner', idempotency_key='missing')

    def test_preparation_internal_validation_is_not_explicit(self):
        self.service.prepare('worker-scheduling', self.request, [], 'Synthetic input', tenant='owner')
        self.assertFalse(self.submit()['input_validation']['explicit_validate_observed'])

    def test_replay_keeps_original_receipt_despite_later_explicit_validate(self):
        original = self.submit()
        self.validate()
        replay = self.submit()
        self.assertTrue(replay['replayed'])
        self.assertEqual(original['input_validation'], replay['input_validation'])
        self.assertEqual(len(self.client.calls), 2)

    def test_replay_without_original_receipt_does_not_rewrite_history(self):
        self.client.submit(self.request, tenant='owner', idempotency_key='key')
        self.validate()
        response = self.submit()
        self.assertTrue(response['replayed'])
        self.assertEqual(response['input_validation']['origin'], 'REPLAY_CHECK_ONLY')
        self.assertFalse(response['input_validation']['checked_before_original_submit'])

    def test_failed_or_uncertain_submit_has_no_receipt_and_no_retry(self):
        for failure in ('UNREACHABLE', 'INVALID_PROBLEM'):
            self.client.failure = failure
            with self.assertRaisesRegex(NativeError, failure):
                self.submit(failure)
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(len(self.service.validation._jobs), 0)

    def test_malformed_submit_reply_has_no_receipt(self):
        self.client.submit = lambda *args, **kwargs: {'job': {'jobId': ''}, 'replayed': 'false'}
        with self.assertRaisesRegex(NativeError, 'BAD_ANSWER'):
            self.submit()
        self.assertFalse(self.service.validation._jobs)

    def test_mutation_during_validation_never_reaches_submit(self):
        original = deepcopy(self.request)
        self.client.mutate = True
        with self.assertRaisesRegex(NativeError, 'VALIDATION_REQUEST_CHANGED'):
            self.submit()
        self.assertEqual(self.request, original)
        self.assertFalse(self.client.calls)

    def test_catalog_drift_during_validation_never_reaches_submit(self):
        self.client.drift = True
        with self.assertRaisesRegex(NativeError, 'VALIDATION_CATALOG_CHANGED'):
            self.submit()
        self.assertFalse(self.client.calls)

    def test_bad_or_contradictory_validation_never_reaches_submit(self):
        for reply in ({'valid': 'true', 'issues': []}, {'valid': True, 'issues': [{'code': 'BAD', 'message': 'bad'}]}):
            self.client.invalid_reply = reply
            with self.assertRaises(NativeError): self.submit()
        self.assertFalse(self.client.calls)

    def test_receipt_isolation_tampering_and_changed_job_request(self):
        response = self.submit()
        self.assertEqual(self.receipt(response, tenant='other')['status'], 'NOT_RECORDED')
        changed = deepcopy(self.request); changed['request_id'] = 'changed'
        with self.assertRaisesRegex(NativeError, 'VALIDATION_RECEIPT_MISMATCH'):
            self.receipt(response, problem=changed)
        response['input_validation']['explicit_validate_observed'] = True
        self.assertFalse(self.receipt(response)['explicit_validate_observed'])
        key = ('owner', 'worker-scheduling', response['job']['jobId'])
        self.service.validation._jobs[key]['explicit_validate_observed'] = True
        with self.assertRaisesRegex(NativeError, 'VALIDATION_RECEIPT_MISMATCH'):
            self.receipt(response)
        with self.assertRaisesRegex(NativeError, 'VALIDATION_RECEIPT_MISMATCH'):
            self.submit()

    def test_bounded_eviction_reports_unknown_history_and_replay_only(self):
        self.service = EvidenceService({'worker-scheduling': self.client}, self.store, max_records=1)
        self.validate()
        first = self.submit()
        changed = deepcopy(self.request); changed['request_id'] = 'next'
        self.validate(changed)
        self.submit('next', changed)
        missing = self.receipt(first)
        self.assertEqual(missing['status'], 'NOT_RECORDED')
        self.assertIsNone(missing['explicit_validate_observed'])
        replay = self.submit()
        self.assertEqual(replay['input_validation']['origin'], 'REPLAY_CHECK_ONLY')
        self.assertFalse(replay['input_validation']['explicit_validate_observed'])
        self.assertLessEqual(len(self.service.validation._jobs), 1)
        self.assertLessEqual(len(self.service.validation._observed), 1)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    summary = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': len(result.skipped), 'model_calls': 0, 'scope': 'Input validation receipts with instrumented job store'}
    Path('evidence-validation-test-result.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))
    raise SystemExit(not result.wasSuccessful())
