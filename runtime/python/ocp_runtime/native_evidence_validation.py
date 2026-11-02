"""Bounded, process-local input-validation receipts for the opt-in MCP binding.

Provider input acceptance is separate from independent result verification.
An explicit validate observation is not a durable authorization or attestation.
"""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock

from conformance.assessment import digest
from ocp_candidate.native import NativeError, native_validate


class ValidationRecords:
    def __init__(self, clients, *, version, max_records):
        self.clients, self.version, self.limit = clients, version, max_records
        self._observed, self._jobs, self._lock = OrderedDict(), OrderedDict(), RLock()

    def _put(self, records, key, value):
        records[key] = deepcopy(value)
        records.move_to_end(key)
        while len(records) > self.limit:
            records.popitem(last=False)

    def _check(self, domain, problem):
        if domain not in self.clients:
            raise NativeError('UNSUPPORTED_DOMAIN')
        client = self.clients[domain]
        request = deepcopy(problem)
        request_hash = digest(request)
        catalog_hash = digest(client.capabilities())
        checked = native_validate('Validation', client.validate(request))
        if digest(request) != request_hash:
            raise NativeError('VALIDATION_REQUEST_CHANGED')
        if digest(client.capabilities()) != catalog_hash:
            raise NativeError('VALIDATION_CATALOG_CHANGED')
        if checked['valid'] and checked['issues']:
            raise NativeError('CONTRADICTORY_VALIDATION')
        return deepcopy(checked), request_hash, catalog_hash

    def validate(self, domain, problem, *, tenant):
        checked, request_hash, catalog_hash = self._check(domain, problem)
        key = (tenant, domain, request_hash, catalog_hash)
        with self._lock:
            self._observed.pop(key, None)
            if checked['valid']:
                self._put(self._observed, key, digest(checked))
        return checked

    def submit(self, domain, problem, *, tenant, idempotency_key):
        request = deepcopy(problem)
        checked, request_hash, catalog_hash = self._check(domain, request)
        if not checked['valid']:
            raise NativeError('INVALID_PROBLEM', status=422, body={
                'code': 'INVALID_PROBLEM', 'message': 'Correct the listed input fields before submitting.',
                'requestId': 'mcp', 'retryable': False, 'issues': checked['issues']})
        with self._lock:
            explicit = (tenant, domain, request_hash, catalog_hash) in self._observed
        # One submission only. A timeout or uncertain response never triggers a retry.
        submitted = self.clients[domain].submit(deepcopy(request), tenant=tenant, idempotency_key=idempotency_key)
        if (not isinstance(submitted, dict) or not isinstance(submitted.get('job'), dict)
                or not isinstance(submitted['job'].get('jobId'), str) or not submitted['job']['jobId']
                or type(submitted.get('replayed')) is not bool):
            raise NativeError('BAD_ANSWER')
        job_id = submitted['job']['jobId']
        key = (tenant, domain, job_id)
        with self._lock:
            previous = self._jobs.get(key)
            if previous is not None:
                self._verify(previous, request_hash)
                if previous['domain'] != domain or previous['job_id'] != job_id:
                    raise NativeError('VALIDATION_RECEIPT_MISMATCH')
            if previous is not None and (previous['checked_before_original_submit'] or submitted['replayed']):
                # Preserve what preceded the original submission, even after replay.
                receipt = deepcopy(previous)
            else:
                replay = submitted['replayed']
                receipt = {'version': self.version, 'status': 'PASS', 'domain': domain, 'job_id': job_id,
                           'request_sha256': request_hash, 'catalog_sha256': catalog_hash,
                           'validation_sha256': digest(checked), 'explicit_validate_observed': explicit,
                           'origin': ('REPLAY_CHECK_ONLY' if replay else
                                      'EXPLICIT_VALIDATE_THEN_SUBMIT' if explicit else 'SUBMIT_PRECHECK'),
                           'checked_before_original_submit': not replay,
                           'scope': 'Provider input validation for this exact request. Separate from independent result '
                                    'verification, execution attestation and completeness of user requirements.'}
                receipt['receipt_sha256'] = digest(receipt)
                self._put(self._jobs, key, receipt)
        return {**submitted, 'input_validation': deepcopy(receipt)}

    @staticmethod
    def _verify(receipt, request_hash):
        body = deepcopy(receipt)
        recorded_hash = body.pop('receipt_sha256', None)
        if digest(body) != recorded_hash or body.get('request_sha256') != request_hash:
            raise NativeError('VALIDATION_RECEIPT_MISMATCH')

    def for_job(self, domain, job_id, problem, *, tenant):
        with self._lock:
            receipt = deepcopy(self._jobs.get((tenant, domain, job_id)))
        if receipt is None:
            return {'status': 'NOT_RECORDED', 'explicit_validate_observed': None,
                    'checked_before_original_submit': None,
                    'scope': 'No retained binding receipt for this job; input validation history is unknown.'}
        self._verify(receipt, digest(problem))
        if receipt['domain'] != domain or receipt['job_id'] != job_id:
            raise NativeError('VALIDATION_RECEIPT_MISMATCH')
        return receipt
