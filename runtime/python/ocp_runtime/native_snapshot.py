"""Opt-in immutable submission records, scoped to actual stored native jobs.

Records survive uncertain submission responses in this process. They are not a
durable journal, raw-file provenance, execution attestation or a solution check.
"""
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock

from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.native import NativeError, native_validate

VERSION = '0.1.0-draft.1'


class ExecutionSnapshots:
    def __init__(self, clients, store, *, max_records=128):
        if type(max_records) is not int or not 1 <= max_records <= 4096:
            raise ValueError('INVALID_SNAPSHOT_LIMIT')
        self.clients, self.store, self.limit = dict(clients), store, max_records
        self._pending, self._jobs, self._lock = {}, {}, RLock()

    def descriptor(self):
        return {'version': VERSION, 'tool': 'ocp_native_snapshot', 'storage': 'volatile-memory',
            'scope': 'Exact submitted Core input and configuration; pre-mapping files and natural-language completeness are not recorded.',
            'max_records': self.limit, 'execution_attestation': False}

    def _prepare(self, domain, problem):
        client = self.clients[domain]
        request = deepcopy(problem)
        request_hash = fingerprint(request)
        catalog = deepcopy(client.capabilities())
        checked = native_validate('Validation', client.validate(request))
        if not checked['valid'] or checked['issues']:
            raise NativeError('INVALID_PROBLEM', body={'code': 'INVALID_PROBLEM',
                'message': 'Correct the listed input fields before submitting.', 'requestId': 'snapshot',
                'retryable': False, 'issues': checked['issues']})
        configuration = client.resolve_configuration({'configuration': deepcopy(request['configuration'])})
        effective = configuration['resolved']['configuration']
        if fingerprint(effective) != fingerprint(request['configuration']):
            raise NativeError('EXPLICIT_EFFECTIVE_CONFIGURATION_REQUIRED')
        if fingerprint(request) != request_hash:
            raise NativeError('VALIDATION_REQUEST_CHANGED')
        if fingerprint(client.capabilities()) != fingerprint(catalog):
            raise NativeError('VALIDATION_CATALOG_CHANGED')
        constraints = request['configuration'].get('constraints')
        mode = 'omitted' if 'constraints' not in request['configuration'] else 'empty' if constraints == [] else 'explicit'
        record = {'version': VERSION, 'domain': domain, 'profile': deepcopy(request['domain_profile']),
            'mapper': {'id': 'ocp.core.identity', 'version': '0.1.0'},
            'source_stage': 'submitted_core_request', 'original_input': deepcopy(request['input']),
            'selected_configuration': deepcopy(request['configuration']),
            'effective_configuration': deepcopy(effective), 'applied_defaults': [],
            'constraint_selection': mode,
            'constraint_scope': 'Selection does not disable intrinsic rules of the declared profile.',
            'submitted_problem': request, 'request_fingerprint': request_hash,
            'input_fingerprint': fingerprint(request['input']),
            'catalog_fingerprint': fingerprint(catalog),
            'execution_attestation': False, 'pre_mapping_source': 'NOT_RECORDED'}
        record['fingerprint'] = fingerprint(record)
        return record

    def submit(self, domain, problem, *, tenant, idempotency_key, operation):
        if domain not in self.clients:
            raise NativeError('UNSUPPORTED_DOMAIN')
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise NativeError('IDEMPOTENCY_KEY_REQUIRED')
        key = (tenant, domain, idempotency_key)
        with self._lock:
            previous = self._pending.get(key)
            if previous and previous['request_fingerprint'] != fingerprint(problem):
                raise NativeError('SNAPSHOT_IDEMPOTENCY_CONFLICT')
            if previous is None:
                if len(self._pending) >= self.limit:
                    raise NativeError('SNAPSHOT_LIMIT')
                record = self._prepare(domain, problem)
                self._pending[key] = deepcopy(record)
            else:
                record = deepcopy(previous)
                if fingerprint(self.clients[domain].capabilities()) != record['catalog_fingerprint']:
                    raise NativeError('SNAPSHOT_CATALOG_CHANGED')
            # One call. On uncertainty retain the original intent; only the caller
            # may explicitly retry the same key. Never replay under new defaults.
            submitted = operation(deepcopy(record['submitted_problem']))
            job_id = submitted['job']['jobId']
            self._jobs[(tenant, domain, job_id)] = deepcopy(record)
            return {**submitted, 'execution_snapshot': {'version': VERSION, 'job_id': job_id,
                'fingerprint': record['fingerprint'], 'request_fingerprint': record['request_fingerprint']}}

    def get(self, domain, job_id, *, tenant):
        job = self.store.get(tenant=tenant, problem_type=domain, job_id=job_id)
        if job is None:
            raise NativeError('JOB_NOT_FOUND')
        if job.expires_at and job.expires_at <= datetime.now(timezone.utc):
            raise NativeError('JOB_EXPIRED')
        with self._lock:
            record = deepcopy(self._jobs.get((tenant, domain, job_id)))
        if record is None:
            return {'job_id': job_id, 'status': 'NOT_RECORDED', 'version': VERSION}
        body = deepcopy(record)
        digest = body.pop('fingerprint')
        if fingerprint(body) != digest or fingerprint(job.problem) != record['request_fingerprint']:
            raise NativeError('SNAPSHOT_MISMATCH')
        if isinstance(job.result, dict) and 'effective_configuration' in job.result:
            if fingerprint(job.result['effective_configuration']) != fingerprint(record['effective_configuration']):
                raise NativeError('RESULT_CONFIGURATION_MISMATCH')
        return {'job_id': job_id, 'status': 'RECORDED', 'snapshot': record}
