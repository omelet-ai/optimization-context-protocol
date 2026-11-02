"""Optional local job verification, separate from provider evaluation and wire v1.

The host supplies the store and trusted checker registry. A tool caller supplies
only a domain and job ID; the original request/result come from that scoped job.
"""
from datetime import datetime, timezone

from foundry_capability_contract import JobStatus
from ocp_candidate.native import NativeError

VERIFICATION_VERSION = '0.1.0'


def completed_job(store, domain, job_id, *, tenant):
    """Return one scoped terminal snapshot for assessment and derived facts."""
    job = store.get(tenant=tenant, problem_type=domain, job_id=job_id)
    if job is None:
        raise NativeError('JOB_NOT_FOUND', status=404)
    if job.expires_at is not None and job.expires_at <= datetime.now(timezone.utc):
        raise NativeError('JOB_EXPIRED', status=410)
    if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise NativeError('JOB_NOT_FINISHED', status=409)
    if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise NativeError('JOB_' + job.status.value.upper(), status=409)
    if job.status not in (JobStatus.SUCCEEDED, JobStatus.INFEASIBLE) or not isinstance(job.result, dict):
        raise NativeError('BAD_ANSWER', status=502)
    if (job.status == JobStatus.INFEASIBLE) != (job.result.get('status') == 'infeasible'):
        raise NativeError('BAD_ANSWER', status=502)
    return job


def local_verifier(store, *, registry=None):
    # Keep the base MCP binding usable without the optional checker package.
    from conformance.assessment import assess, builtin_checkers
    selected = builtin_checkers() if registry is None else registry

    def verify(domain, job_id, *, tenant):
        job = completed_job(store, domain, job_id, tenant=tenant)
        report = assess(job.problem, job.result, registry=selected)
        return {'jobId': job.id, 'jobStatus': job.status.value,
                'verificationVersion': VERIFICATION_VERSION, 'verification': report}

    return verify
