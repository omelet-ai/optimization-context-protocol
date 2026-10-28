"""The reusable contract suite of Capability Contract v1.

Every Optimization API runs these checks against its own app (a FastAPI TestClient, or an httpx
client on a running server):

    suite = ContractSuite(client, base_path="/v2", token="t", problem={...})
    @pytest.mark.parametrize("check", ContractSuite.CHECKS)
    def test_contract(check): getattr(suite, check)()

``problem`` must solve within ``solve_timeout``. ``slow_problem`` (optional) must still be running
after ``slow_seconds`` so that cancelling a running job can be seen; ``evaluation`` (optional) is a
body for POST /evaluations without a job. With ``openapi`` (``contract_openapi()``), every answer
is also checked against the contract's schemas.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..canonical import capability_digest
from .openapi import SchemaChecker

__all__ = ["ContractSuite"]

_ENVELOPE_KEYS = {"code", "message", "requestId", "retryable", "issues"}
_TERMINAL = {"succeeded", "infeasible", "failed", "cancelled"}


@dataclass
class ContractSuite:
    client: Any
    base_path: str
    token: str
    problem: dict[str, Any]
    other_problem: dict[str, Any] | None = None
    slow_problem: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    solve_timeout: float = 60.0
    slow_seconds: float = 1.0
    tenant: str = "tenant-a"
    other_tenant: str = "tenant-b"
    openapi: dict[str, Any] | None = None
    _seq: list[int] = field(default_factory=lambda: [0])
    _schemas: SchemaChecker | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.openapi is not None:
            self._schemas = SchemaChecker(self.openapi)

    CHECKS = (
        "check_ops",
        "check_auth",
        "check_capabilities_digest",
        "check_validate",
        "check_tenant_required",
        "check_idempotency_key_required",
        "check_job_lifecycle",
        "check_idempotent_replay",
        "check_idempotency_conflict",
        "check_tenant_isolation",
        "check_cancel",
        "check_error_envelope",
        "check_evaluation",
    )

    # ------------------------------------------------------------------ helpers

    def _headers(self, *, tenant: str | None = None, key: str | None = None, token: str | None = "default") -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if token is not None:
            headers["authorization"] = f"Bearer {self.token if token == 'default' else token}"
        if tenant is not None:
            headers["X-OIP-Tenant-Id"] = tenant
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    def _key(self) -> str:
        self._seq[0] += 1
        return f"suite-{uuid.uuid4().hex[:8]}-{self._seq[0]}"

    def _conform(self, schema: str, body: Any) -> None:
        if self._schemas is not None:
            self._schemas.check(schema, body)

    def _submit(self, problem: dict[str, Any], *, tenant: str | None = None, key: str | None = None) -> Any:
        response = self.client.post(f"{self.base_path}/jobs", json=problem, headers=self._headers(tenant=tenant or self.tenant, key=key or self._key()))
        if response.status_code == 202:
            self._conform("Job", response.json())
        return response

    def _job(self, job_id: str, *, tenant: str | None = None) -> Any:
        response = self.client.get(f"{self.base_path}/jobs/{job_id}", headers=self._headers(tenant=tenant or self.tenant))
        if response.status_code == 200:
            self._conform("Job", response.json())
        return response

    def _wait(self, job_id: str, *, tenant: str | None = None) -> dict[str, Any]:
        """The job once it is terminal."""
        deadline = time.monotonic() + self.solve_timeout
        while True:
            body = self._job(job_id, tenant=tenant).json()
            if body["status"] in _TERMINAL:
                return body
            if time.monotonic() > deadline:
                raise AssertionError(f"job {job_id} still {body['status']} after {self.solve_timeout} s")
            time.sleep(0.1)

    def _envelope(self, response: Any, status: int, code: str | None = None) -> dict[str, Any]:
        assert response.status_code == status, f"want {status}, got {response.status_code}: {response.text[:300]}"
        body = response.json()
        missing = _ENVELOPE_KEYS - set(body)
        assert not missing, f"error envelope lacks {sorted(missing)}: {body}"
        self._conform("ErrorEnvelope", body)
        if code is not None:
            assert body["code"] == code, f"want code {code}, got {body['code']}"
        assert response.headers.get("x-request-id") == body["requestId"], "the request id is echoed"
        return body

    # ------------------------------------------------------------------ checks

    def check_ops(self) -> None:
        health = self.client.get("/health")
        assert health.status_code == 200
        self._conform("Health", health.json())
        ready = self.client.get("/ready")
        assert ready.status_code == 200, f"/ready answered {ready.status_code}: {ready.text[:300]}"
        self._conform("Readiness", ready.json())
        version = self.client.get("/version").json()
        assert version.get("service") and version.get("build"), version
        self._conform("Version", version)

    def check_auth(self) -> None:
        url = f"{self.base_path}/capabilities"
        self._envelope(self.client.get(url, headers=self._headers(token=None)), 401, "UNAUTHENTICATED")
        self._envelope(self.client.get(url, headers=self._headers(token="not-a-known-token")), 401, "UNAUTHENTICATED")
        self._envelope(self.client.post(f"{self.base_path}/jobs", json=self.problem, headers=self._headers(token=None, tenant=self.tenant, key=self._key())), 401, "UNAUTHENTICATED")

    def check_capabilities_digest(self) -> None:
        response = self.client.get(f"{self.base_path}/capabilities", headers=self._headers())
        assert response.status_code == 200, response.text[:300]
        body = response.json()
        self._conform("Capabilities", body)
        assert body.get("contractVersion") == "1", body.get("contractVersion")
        assert body.get("problemType"), "the catalog names its problem type"
        catalog = {key: value for key, value in body.items() if key != "catalogDigest"}
        assert body.get("catalogDigest") == capability_digest(catalog), "catalogDigest is capability_digest of the answer without it"

    def check_validate(self) -> None:
        response = self.client.post(f"{self.base_path}/validate", json=self.problem, headers=self._headers())
        assert response.status_code == 200, response.text[:300]
        body = response.json()
        self._conform("Validation", body)
        assert body["valid"] is True, f"the suite's problem is not valid: {body['issues']}"

    def check_tenant_required(self) -> None:
        self._envelope(self.client.post(f"{self.base_path}/jobs", json=self.problem, headers=self._headers(key=self._key())), 400, "TENANT_REQUIRED")
        self._envelope(self.client.get(f"{self.base_path}/jobs/{uuid.uuid4()}", headers=self._headers()), 400, "TENANT_REQUIRED")

    def check_idempotency_key_required(self) -> None:
        self._envelope(self.client.post(f"{self.base_path}/jobs", json=self.problem, headers=self._headers(tenant=self.tenant)), 400, "IDEMPOTENCY_KEY_REQUIRED")

    def check_job_lifecycle(self) -> None:
        submitted = self._submit(self.problem)
        assert submitted.status_code == 202, submitted.text[:300]
        job = submitted.json()
        assert job["status"] in {"queued", "running", "succeeded", "infeasible"}, job
        final = self._wait(job["jobId"])
        assert final["status"] in {"succeeded", "infeasible"}, final
        result = self.client.get(f"{self.base_path}/jobs/{job['jobId']}/result", headers=self._headers(tenant=self.tenant))
        assert result.status_code == 200, result.text[:300]
        self._conform("JobResult", result.json())
        assert result.json()["status"] == final["status"]

    def check_idempotent_replay(self) -> None:
        key = self._key()
        first = self._submit(self.problem, key=key)
        again = self._submit(self.problem, key=key)
        assert first.status_code == again.status_code == 202
        assert again.json()["jobId"] == first.json()["jobId"]
        assert again.headers.get("Idempotent-Replayed") == "true"
        self._wait(first.json()["jobId"])

    def check_idempotency_conflict(self) -> None:
        other = self.other_problem
        if other is None:
            other = {**self.problem, "_suite_variant": True}
        key = self._key()
        first = self._submit(self.problem, key=key)
        self._envelope(self._submit(other, key=key), 409, "IDEMPOTENCY_CONFLICT")
        self._wait(first.json()["jobId"])

    def check_tenant_isolation(self) -> None:
        key = self._key()
        mine = self._submit(self.problem, key=key).json()["jobId"]
        final = self._wait(mine)
        other = self.other_tenant
        self._envelope(self._job(mine, tenant=other), 404, "JOB_NOT_FOUND")
        self._envelope(self.client.get(f"{self.base_path}/jobs/{mine}/result", headers=self._headers(tenant=other)), 404, "JOB_NOT_FOUND")
        self._envelope(self.client.delete(f"{self.base_path}/jobs/{mine}", headers=self._headers(tenant=other)), 404, "JOB_NOT_FOUND")
        self._envelope(self.client.post(f"{self.base_path}/evaluations", json={"jobId": mine}, headers=self._headers(tenant=other)), 404, "JOB_NOT_FOUND")
        theirs = self._submit(self.problem, tenant=other, key=key)
        assert theirs.status_code == 202, theirs.text[:300]
        assert theirs.headers.get("Idempotent-Replayed") is None, "another tenant's key is not a replay"
        assert theirs.json()["jobId"] != mine, "the same key makes another job for another tenant"
        assert self._job(mine).json()["status"] == final["status"], "the other tenant changed nothing"
        self._wait(theirs.json()["jobId"], tenant=other)

    def check_cancel(self) -> None:
        if self.slow_problem is None:
            return
        job = self._submit(self.slow_problem).json()["jobId"]
        deadline = time.monotonic() + self.solve_timeout
        while self._job(job).json()["status"] == "queued" and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(self.slow_seconds)
        cancelled = self.client.delete(f"{self.base_path}/jobs/{job}", headers=self._headers(tenant=self.tenant))
        assert cancelled.status_code == 202, cancelled.text[:300]
        final = self._wait(job)
        assert final["status"] == "cancelled", final
        self._envelope(self.client.get(f"{self.base_path}/jobs/{job}/result", headers=self._headers(tenant=self.tenant)), 409, "JOB_CANCELLED")

    def check_error_envelope(self) -> None:
        response = self.client.post(f"{self.base_path}/validate", content=b"[not json", headers=self._headers())
        body = self._envelope(response, 422)
        assert isinstance(body["issues"], list)
        self._envelope(self._job(str(uuid.uuid4())), 404, "JOB_NOT_FOUND")
        self._envelope(self.client.get(f"{self.base_path}/no-such-endpoint", headers=self._headers()), 404, "NOT_FOUND")

    def check_evaluation(self) -> None:
        job = self._submit(self.problem).json()["jobId"]
        self._wait(job)
        evaluated = self.client.post(f"{self.base_path}/evaluations", json={"jobId": job}, headers=self._headers(tenant=self.tenant))
        assert evaluated.status_code == 200, evaluated.text[:300]
        if self.evaluation is not None:
            direct = self.client.post(f"{self.base_path}/evaluations", json=self.evaluation, headers=self._headers(tenant=self.tenant))
            assert direct.status_code == 200, direct.text[:300]
