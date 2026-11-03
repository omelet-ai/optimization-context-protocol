"""Local-only reference server using the unchanged Foundry router/store/worker.

Domains provide a CapabilityAdapter and an importable process solve function.
There are no domain branches in request dispatch, auth, jobs or cancellation.
"""
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import hashlib
from importlib.metadata import version
import secrets
import socket
import threading
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from foundry_capability_contract import (MemoryJobStore, Worker, WorkerPool, ProcessSolveRunner,
    ServiceTrust, CapabilityError, capability_router, install_error_handlers)
from foundry_capability_contract.errors import error_body, request_id_of
from foundry_capability_contract.ops import ReadinessCheck, ops_router
from foundry_capability_contract.router import CONTRACT_VERSION, capability_document
from ocp_candidate.contract import parse_json
from ocp_candidate.native import native_validate
from .native_domain import ReferenceDomain, solve_reference


@dataclass(frozen=True)
class Registration:
    domain: ReferenceDomain
    solve: object  # module-level callable or pickleable partial for ProcessSolveRunner


def reference_domains(names=None):
    from .providers import PROVIDERS, make_provider
    available = {profile.replace('.', '-'): profile for profile in PROVIDERS}
    if names is not None and (not isinstance(names, (list, tuple)) or not names
            or any(not isinstance(name, str) or name not in available for name in names)
            or len(set(names)) != len(names)):
        raise ValueError('INVALID_DOMAIN_SELECTION')
    return [Registration(ReferenceDomain(make_provider(profile), problem_type=profile.replace('.', '-')),
                         partial(solve_reference, profile)) for profile in PROVIDERS
            if names is None or profile.replace('.', '-') in names]


class BoundedLocalStore:
    """Product policy around, not a fork of, the canonical volatile store."""
    def __init__(self, max_jobs):
        self.store = MemoryJobStore(retention=timedelta(hours=2), max_attempts=1)
        self.keys, self.ids, self.lock, self.limit = set(), [], threading.Lock(), max_jobs

    def __getattr__(self, name): return getattr(self.store, name)

    def submit(self, **kwargs):
        key = (kwargs['tenant'], kwargs['problem_type'], kwargs['idempotency_key'])
        with self.lock:
            if key not in self.keys and len(self.keys) >= self.limit:
                raise CapabilityError(429, 'LOCAL_JOB_LIMIT', 'Restart the local reference to start a new session')
            job, created = self.store.submit(**kwargs)
            if created:
                self.keys.add(key); self.ids.append((job.tenant, job.problem_type, job.id))
            return job, created

    def cancel_all(self):
        for tenant, kind, job in self.ids:
            self.store.request_cancel(tenant=tenant, problem_type=kind, job_id=job)


class LocalWorker(Worker):
    """Observe canonical worker polling without changing job/solver semantics."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.polled = threading.Event()
        self.thread = None

    def run_once(self):
        self.thread = threading.current_thread()
        try:
            result = super().run_once()
        except BaseException:
            self.polled.clear()
            raise
        self.polled.set()
        return result

    def available(self):
        # A busy solver may take longer than the polling interval. Liveness is
        # not a deadline or a claim that a particular optimization will succeed.
        return self.polled.is_set() and self.thread is not None and self.thread.is_alive()


def create_native_app(token, registrations=None, *, max_jobs=128):
    if not token or not isinstance(token, str) or not 1 <= max_jobs <= 1024: raise ValueError('INVALID_LOCAL_CONFIG')
    registrations = reference_domains() if registrations is None else registrations
    ids = [r.domain.problem_type for r in registrations]
    if not ids or len(ids) != len(set(ids)) or any(not callable(r.solve) for r in registrations):
        raise ValueError('INVALID_DOMAIN_REGISTRATION')
    store = BoundedLocalStore(max_jobs)
    trust = ServiceTrust({'local-reference': hashlib.sha256(token.encode()).hexdigest()}, 'local ephemeral token')
    adapters = [r.domain.adapter() for r in registrations]
    catalogs = [deepcopy(native_validate('Capabilities', capability_document(adapter))) for adapter in adapters]
    workers = [LocalWorker(store, problem_type=r.domain.problem_type, solve=r.solve,
                          runner=ProcessSolveRunner(), heartbeat_seconds=.05) for r in registrations]
    pools = [WorkerPool(lambda i, worker=worker: worker, count=1, idle_seconds=.02) for worker in workers]
    started = threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        try:
            for pool in pools: pool.start()
            # Wait for each first real queue poll, not merely thread creation.
            for worker in workers:
                if not worker.polled.wait(5): raise RuntimeError('LOCAL_WORKER_START_FAILED')
            started.set()
            yield
        finally:
            started.clear()
            try: store.cancel_all()
            finally:
                for pool in pools: pool.stop()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    install_error_handlers(app)

    @app.middleware('http')
    async def boundary(request, call_next):
        def reject(code, status=400):
            request_id = request_id_of(request)
            return JSONResponse(error_body(code, code, request_id), status_code=status,
                                headers={'x-request-id': request_id})
        if request.headers.get('origin') or request.url.hostname != '127.0.0.1': return reject('LOCAL_ONLY', 403)
        for name in ['authorization','x-oip-tenant-id','idempotency-key','content-length','host']:
            if len(request.headers.getlist(name)) > 1: return reject('DUPLICATE_HEADER')
        if request.method == 'POST':
            if request.headers.get('content-type','').split(';')[0] != 'application/json': return reject('INVALID_CONTENT_TYPE',415)
            size = request.headers.get('content-length', '')
            if request.headers.get('transfer-encoding') or not size.isdigit(): return reject('INVALID_FRAMING')
            if not 0 < int(size) <= 131072: return reject('PAYLOAD_TOO_LARGE',413)
            raw = await request.body()
            if len(raw) != int(size): return reject('INVALID_FRAMING')
            try: parse_json(raw.decode('utf-8'))
            except (ValueError, UnicodeError, RecursionError): return reject('INVALID_REQUEST',422)
        return await call_next(request)

    def store_ready():
        # Non-mutating lookup through the same store used by jobs; never queue
        # a synthetic solve, consume a session slot, or expose another tenant.
        return store.get(tenant='readiness', problem_type=ids[0], job_id='readiness-probe') is None

    checks = [ReadinessCheck('lifecycle', started.is_set), ReadinessCheck('store', store_ready)]
    for adapter, catalog, worker in zip(adapters, catalogs, workers):
        checks.extend([
            ReadinessCheck('worker:' + adapter.problem_type, worker.available),
            ReadinessCheck('catalog:' + adapter.problem_type,
                           lambda a=adapter, c=catalog: capability_document(a) == c)])
        app.include_router(capability_router(adapter, store, trust,
                           base_path='/api/' + adapter.problem_type + '/v1'))
    app.include_router(ops_router(service='ocp-native-local', checks=checks, versions=lambda: {
        'contractVersion': CONTRACT_VERSION, 'packageVersion': version('ocp-candidate'),
        'catalogs': {c['problemType']: {'catalogVersion': c['catalogVersion'],
                    'catalogDigest': c['catalogDigest'], 'domainProfile': c['domainProfile']} for c in catalogs}}))
    app.state.native_store = store
    app.state.domain_ids = ids
    return app


class LocalAPI:
    """No-account startup; token is internal to this process, never tool arguments."""
    def __init__(self, registrations=None, *, max_jobs=128):
        self.token = secrets.token_urlsafe(32)
        self.app = create_native_app(self.token, registrations, max_jobs=max_jobs)

    def __enter__(self):
        import uvicorn
        self.socket = socket.socket(); self.socket.bind(('127.0.0.1',0)); self.socket.listen(128)
        self.base = 'http://127.0.0.1:' + str(self.socket.getsockname()[1])
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_level='critical', access_log=False, lifespan='on'))
        self.thread = threading.Thread(target=self.server.run, kwargs={'sockets':[self.socket]}, daemon=True)
        self.thread.start(); deadline = time.monotonic() + 15
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.__exit__(None,None,None); raise RuntimeError('LOCAL_API_START_FAILED')
            time.sleep(.01)
        return self

    def client(self, problem_type):
        from ocp_candidate.native import NativeClient
        if problem_type not in self.app.state.domain_ids: raise ValueError('UNSUPPORTED_DOMAIN')
        return NativeClient(self.base + '/api/' + problem_type + '/v1', self.token)

    def __exit__(self, *args):
        self.server.should_exit = True; self.thread.join(15); self.socket.close()
        if self.thread.is_alive(): raise RuntimeError('LOCAL_API_SHUTDOWN_FAILED')
