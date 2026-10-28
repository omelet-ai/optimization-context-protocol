"""Explicit Capability Contract v1 client; Core 0.1 Client remains unchanged.

Schemas and canonicalization come from the separately installed pinned Foundry
contract artifact. No workspace lookup, schema copy, automatic retry or fallback.
"""
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

from jsonschema import Draft202012Validator, FormatChecker
from .contract import parse_json, strict_json


class NativeError(ValueError):
    def __init__(self, code, *, status=0, body=None):
        super().__init__(code)
        self.code, self.status, self.body = code, status, body

    @property
    def retryable(self):
        return self.body['retryable'] if self.body else self.code in ('UNREACHABLE', 'WAIT_TIMEOUT')


@lru_cache(maxsize=1)
def native_contract():
    try:
        return parse_json(files('foundry_capability_contract').joinpath('capability-contract-v1.json').read_text())
    except (ModuleNotFoundError, FileNotFoundError):
        raise NativeError('NATIVE_CONTRACT_NOT_INSTALLED') from None


def native_validate(component, value):
    strict_json(value)
    document = native_contract()
    schema = {'$ref': '#/components/schemas/' + component, 'components': document['components']}
    if component not in document['components']['schemas']:
        raise NativeError('UNKNOWN_CONTRACT_COMPONENT')
    if next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), None):
        raise NativeError('BAD_ANSWER')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class NativeClient:
    """One native problem type. Token/tenant are trusted host configuration."""
    def __init__(self, base_url, token, *, timeout=10):
        url = urlsplit(base_url)
        if (url.scheme != 'https' and not (url.scheme == 'http' and url.hostname == '127.0.0.1')) or url.username or url.password or url.query or url.fragment:
            raise NativeError('INVALID_ENDPOINT')
        if not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise NativeError('INVALID_CREDENTIAL')
        if not 0 < timeout <= 60: raise NativeError('INVALID_TIMEOUT')
        self.base, self.token, self.timeout = base_url.rstrip('/'), token, timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, method, path, component=None, *, body=None, tenant=None, key=None):
        headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + self.token}
        for name, value, pattern in [('X-OIP-Tenant-Id', tenant, r'[A-Za-z0-9._:-]{1,128}'),
                                     ('Idempotency-Key', key, r'[!-~]{1,200}')]:
            if value is not None:
                if not isinstance(value, str) or not re.fullmatch(pattern, value): raise NativeError('INVALID_HEADER')
                headers[name] = value
        data = None
        if body is not None:
            strict_json(body); data = json.dumps(body, allow_nan=False).encode()
            headers['Content-Type'] = 'application/json'
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError):
            raise NativeError('UNREACHABLE') from None
        with response:
            raw = response.read(1048577)
            if len(raw) > 1048576: raise NativeError('BAD_ANSWER')
            try: value = parse_json(raw.decode('utf-8'))
            except (ValueError, UnicodeError): raise NativeError('BAD_ANSWER') from None
            if not 200 <= response.status < 300:
                native_validate('ErrorEnvelope', value)
                raise NativeError(value['code'], status=response.status, body=value)
            if response.headers.get_content_type() != 'application/json': raise NativeError('BAD_ANSWER')
            if component: native_validate(component, value)
            elif not isinstance(value, dict): raise NativeError('BAD_ANSWER')
            return value, response.headers

    def capabilities(self):
        from foundry_capability_contract import capability_digest
        value = self.call('GET', '/capabilities', 'Capabilities')[0]
        original = deepcopy(value); digest = original.pop('catalogDigest')
        if capability_digest(original) != digest: raise NativeError('CATALOG_DIGEST_MISMATCH')
        return value

    def validate(self, problem): return self.call('POST', '/validate', 'Validation', body=problem)[0]
    def resolve_configuration(self, selection): return self.call('POST', '/configurations/resolve', body=selection)[0]
    def resolve_data_requirements(self, selection): return self.call('POST', '/data-requirements/resolve', body=selection)[0]

    @staticmethod
    def tenant(value):
        if not value: raise NativeError('TENANT_REQUIRED')
        return value

    def submit(self, problem, *, tenant, idempotency_key):
        if not idempotency_key: raise NativeError('IDEMPOTENCY_KEY_REQUIRED')
        job, headers = self.call('POST', '/jobs', 'Job', body=problem, tenant=self.tenant(tenant), key=idempotency_key)
        return {'job': job, 'replayed': headers.get('Idempotent-Replayed') == 'true'}

    def job(self, job_id, *, tenant): return self.call('GET', '/jobs/' + quote(job_id, safe=''), 'Job', tenant=self.tenant(tenant))[0]
    def result(self, job_id, *, tenant): return self.call('GET', '/jobs/' + quote(job_id, safe='') + '/result', 'JobResult', tenant=self.tenant(tenant))[0]
    def cancel(self, job_id, *, tenant): return self.call('DELETE', '/jobs/' + quote(job_id, safe=''), 'Job', tenant=self.tenant(tenant))[0]
    def evaluate(self, body, *, tenant): return self.call('POST', '/evaluations', body=body, tenant=self.tenant(tenant))[0]

    def wait(self, job_id, *, tenant, timeout=30):
        if not 0 < timeout <= 300: raise NativeError('INVALID_TIMEOUT')
        from foundry_capability_contract import TERMINAL
        terminal = {s.value for s in TERMINAL}
        deadline = time.monotonic() + timeout
        while True:
            job = self.job(job_id, tenant=tenant)
            if job['status'] in terminal: return job
            if time.monotonic() >= deadline:
                # Cancellation request is not proof that a remote worker has stopped.
                try: self.cancel(job_id, tenant=tenant)
                except NativeError: pass
                raise NativeError('WAIT_TIMEOUT')
            time.sleep(.03)

    def solve(self, problem, *, tenant, idempotency_key, timeout=30):
        submitted = self.submit(problem, tenant=tenant, idempotency_key=idempotency_key)
        job = self.wait(submitted['job']['jobId'], tenant=tenant, timeout=timeout)
        result = self.result(job['jobId'], tenant=tenant)
        if result['jobId'] != job['jobId'] or result['status'] != job['status']: raise NativeError('BAD_ANSWER')
        return {'job': job, 'result': result, 'replayed': submitted['replayed']}
