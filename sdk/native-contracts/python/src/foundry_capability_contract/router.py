"""The standard endpoints of Capability Contract v1 for one problem type.

An API implements a ``CapabilityAdapter`` (what its problem type can do) and mounts
``capability_router(adapter, store, trust)`` at its base path; the router does the rest the same way
for every API: service-token auth, the tenant header, idempotent job submission, tenant-scoped job
reads and cancellation, results, evaluations, and the catalog digest.

    GET    {base}/capabilities                  the catalog; catalogDigest is capability_digest of the
                                                answer without catalogDigest (api.baseUrl left out)
    POST   {base}/validate                      checks a problem, solves nothing
    POST   {base}/configurations/resolve        curation
    POST   {base}/data-requirements/resolve     curation
    POST   {base}/jobs                          202; Idempotency-Key and X-OIP-Tenant-Id required
    GET    {base}/jobs/{jobId}                  the job's state (another tenant's: 404)
    GET    {base}/jobs/{jobId}/result           the result of a succeeded or infeasible job
    DELETE {base}/jobs/{jobId}                  cancels; a cancelled job keeps no result
    POST   {base}/evaluations                   evaluates a job's result or a given solution
    POST   {base}/compilations                  when the adapter has it: the engine's input, no solve
    POST   {base}/repairs                       when the adapter has it: a repair, queued as a job (202)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Request
from fastapi.responses import JSONResponse

from .canonical import canonical_digest, capability_digest
from .errors import CapabilityError, request_id_of
from .jobs.model import TERMINAL, IdempotencyConflict, Job, JobStatus, JobStore
from .trust import ServiceTrust, require_tenant

__all__ = ["CapabilityAdapter", "CONTRACT_VERSION", "capability_document", "capability_router"]

CONTRACT_VERSION = "1"
_KEY = re.compile(r"^[\x21-\x7e]{1,200}$")

Body_ = dict[str, Any]


@dataclass
class CapabilityAdapter:
    """What one problem type's API does; every callable gets JSON and answers JSON."""

    problem_type: str
    #: the catalog without catalogDigest: versions, objectives, constraints, parameters
    capabilities: Callable[[], Body_]
    #: {valid, issues} for a problem
    validate: Callable[[Body_], Body_]
    resolve_configuration: Callable[[Body_], Body_]
    resolve_data_requirements: Callable[[Body_], Body_]
    #: evaluation of a job's result (the job is given) or of a solution in the body (job None)
    evaluate: Callable[[Body_, Job | None], Body_]
    #: a problem's identity for idempotency (default: the canonical digest of the body)
    request_hash: Callable[[Body_], str] = canonical_digest
    #: checks a submission before it is queued; raises CapabilityError (422) for a bad one
    precheck: Callable[[Body_], None] | None = None
    compile: Callable[[Body_], Body_] | None = None
    #: a repair request -> the problem of the job that repairs (validated; CapabilityError for a bad
    #: one); the job is queued like a submission and the API's solve tells the two apart
    repair: Callable[[Body_], Body_] | None = None


def capability_document(adapter: CapabilityAdapter) -> Body_:
    """What GET /capabilities answers: the catalog, the contract version, the problem type, and
    catalogDigest over all of it (api.baseUrl left out). APIs export their snapshot with it too."""
    catalog = {**adapter.capabilities(), "contractVersion": CONTRACT_VERSION, "problemType": adapter.problem_type}
    return {**catalog, "catalogDigest": capability_digest(catalog)}


def _require_key(value: str | None) -> str:
    key = (value or "").strip()
    if not _KEY.match(key):
        raise CapabilityError(400, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key must be 1-200 printable characters", field_path="Idempotency-Key")
    return key


def _object(body: Any, field: str = "body") -> Body_:
    if not isinstance(body, dict):
        raise CapabilityError(422, "INVALID_REQUEST", f"{field} must be a JSON object", field_path=field)
    return body


def capability_router(adapter: CapabilityAdapter, store: JobStore, trust: ServiceTrust, *, base_path: str = "") -> APIRouter:
    router = APIRouter(prefix=base_path)
    caller = trust.dependency()
    kind = adapter.problem_type

    def tenant_of(tenant: str | None = Header(default=None, alias="X-OIP-Tenant-Id")) -> str:
        return require_tenant(tenant)

    def job_of(tenant: str, job_id: str) -> Job:
        job = store.get(tenant=tenant, problem_type=kind, job_id=job_id)
        if job is None:
            raise CapabilityError(404, "JOB_NOT_FOUND", f"no job {job_id} for this tenant")
        return job

    @router.get("/capabilities")
    def capabilities(_caller: str = Depends(caller)) -> Body_:
        return capability_document(adapter)

    @router.post("/validate")
    def validate(body: Any = Body(...), _caller: str = Depends(caller)) -> Body_:
        return adapter.validate(_object(body))

    @router.post("/configurations/resolve")
    def resolve_configuration(body: Any = Body(...), _caller: str = Depends(caller)) -> Body_:
        return adapter.resolve_configuration(_object(body))

    @router.post("/data-requirements/resolve")
    def resolve_data_requirements(body: Any = Body(...), _caller: str = Depends(caller)) -> Body_:
        return adapter.resolve_data_requirements(_object(body))

    def queue(request: Request, problem: Body_, caller_name: str, tenant: str, key: str) -> JSONResponse:
        try:
            job, created = store.submit(tenant=tenant, problem_type=kind, idempotency_key=key, request_hash=adapter.request_hash(problem), caller=caller_name, problem=problem)
        except IdempotencyConflict as conflict:
            raise CapabilityError(409, "IDEMPOTENCY_CONFLICT", f"Idempotency-Key already names job {conflict.job_id} for a different request") from conflict
        headers = {"Location": f"{base_path}/jobs/{job.id}", "x-request-id": request_id_of(request)}
        if not created:
            headers["Idempotent-Replayed"] = "true"
        return JSONResponse(status_code=202, content=job.public(), headers=headers)

    @router.post("/jobs", status_code=202)
    def submit(
        request: Request,
        body: Any = Body(...),
        caller_name: str = Depends(caller),
        tenant: str = Depends(tenant_of),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        problem = _object(body)
        key = _require_key(idempotency_key)
        if adapter.precheck is not None:
            adapter.precheck(problem)
        return queue(request, problem, caller_name, tenant, key)

    @router.get("/jobs/{job_id}")
    def status(job_id: str, _caller: str = Depends(caller), tenant: str = Depends(tenant_of)) -> Body_:
        return job_of(tenant, job_id).public()

    @router.get("/jobs/{job_id}/result")
    def result(job_id: str, _caller: str = Depends(caller), tenant: str = Depends(tenant_of)) -> Body_:
        job = job_of(tenant, job_id)
        if job.status in (JobStatus.SUCCEEDED, JobStatus.INFEASIBLE):
            return {"jobId": job.id, "status": job.status.value, "result": job.result or {}}
        if job.status not in TERMINAL:
            raise CapabilityError(409, "JOB_NOT_FINISHED", f"job {job.id} is {job.status.value}", retryable=True)
        if job.status == JobStatus.CANCELLED:
            raise CapabilityError(409, "JOB_CANCELLED", f"job {job.id} was cancelled and keeps no result")
        error = job.error or {}
        raise CapabilityError(409, "JOB_FAILED", f"job {job.id} failed: {error.get('code', 'SOLVE_FAILED')}: {error.get('message', '')}".rstrip(": "))

    @router.delete("/jobs/{job_id}", status_code=202)
    def cancel(job_id: str, _caller: str = Depends(caller), tenant: str = Depends(tenant_of)) -> Body_:
        job = store.request_cancel(tenant=tenant, problem_type=kind, job_id=job_id)
        if job is None:
            raise CapabilityError(404, "JOB_NOT_FOUND", f"no job {job_id} for this tenant")
        return job.public()

    @router.post("/evaluations")
    def evaluate(body: Any = Body(...), _caller: str = Depends(caller), tenant: str = Depends(tenant_of)) -> Body_:
        payload = _object(body)
        job_id = payload.get("jobId")
        job = job_of(tenant, str(job_id)) if job_id is not None else None
        if job is not None and job.status not in (JobStatus.SUCCEEDED, JobStatus.INFEASIBLE):
            raise CapabilityError(409, "JOB_NOT_FINISHED", f"job {job.id} is {job.status.value}: nothing to evaluate", retryable=job.status not in TERMINAL)
        return adapter.evaluate(payload, job)

    if adapter.compile is not None:
        compile_fn = adapter.compile

        @router.post("/compilations")
        def compilations(body: Any = Body(...), _caller: str = Depends(caller)) -> Body_:
            return compile_fn(_object(body))

    if adapter.repair is not None:
        repair_fn = adapter.repair

        @router.post("/repairs", status_code=202)
        def repairs(
            request: Request,
            body: Any = Body(...),
            caller_name: str = Depends(caller),
            tenant: str = Depends(tenant_of),
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        ) -> JSONResponse:
            request_body = _object(body)
            key = _require_key(idempotency_key)
            return queue(request, repair_fn(request_body), caller_name, tenant, key)

    return router
