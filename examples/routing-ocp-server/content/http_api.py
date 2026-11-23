"""Optional loopback asynchronous API and connector for the same Routing engine.

This example demonstrates two API shapes, not two independent optimization
engines or a production Internet service. It never retries an uncertain submit.
"""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid

from ocp_runtime._worker_contract.jobs.worker import WorkerPool
from ocp_runtime._worker_contract.jobs.model import IdempotencyConflict
from ocp_runtime.execution import ExecutionService, ExecutionError
from ocp_runtime.execution.jobs import JobService, Principal
from ocp_runtime.execution.sqlite_store import SQLiteJobStore
from ocp_candidate.server_package import PackageError
from .engine import LibraryConnector, descriptor


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExecutionError("API_REDIRECT_REFUSED")


class HTTPConnector:
    isolation = "remote_requires_reconcile"

    def __init__(self, endpoint, token):
        parsed = urlsplit(endpoint)
        local_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (parsed.scheme != "https" and not local_http) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ExecutionError("API_ENDPOINT_INVALID")
        if not isinstance(token, str) or not token: raise ExecutionError("API_CREDENTIAL_REQUIRED")
        self.endpoint, self.token = endpoint.rstrip("/"), token

    @classmethod
    def from_settings(cls, settings):
        name = settings.get("credential_environment_variable")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
            raise ExecutionError("CREDENTIAL_ENVIRONMENT_VARIABLE_REQUIRED")
        return cls(settings["api_endpoint"], os.environ.get(name))

    def _request(self, path, payload=None, *, timeout=5):
        encoded = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        request = Request(self.endpoint + path, data=encoded, headers={"Authorization": "Bearer " + self.token,
            "Content-Type": "application/json", "Accept": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
                data = response.read(2000001)
                if len(data) > 2000000: raise ExecutionError("API_RESPONSE_TOO_LARGE")
                return json.loads(data)
        except HTTPError as error:
            if error.code in {401, 403}: raise ExecutionError("UPSTREAM_AUTHENTICATION_FAILED") from None
            raise ExecutionError("API_RESPONSE_REJECTED") from None
        except ExecutionError:
            raise
        except (OSError, URLError, ValueError):
            raise ExecutionError("API_UNAVAILABLE") from None

    def describe(self):
        return self._request("/contract")

    def validate(self, input_value, configuration):
        return self._request("/validate", {"input": input_value, "configuration": configuration})

    def execute(self, input_value, configuration):
        request_key = str(uuid.uuid4())
        try:
            submitted = self._request("/jobs", {"input": input_value, "configuration": configuration, "idempotency_key": request_key})
        except ExecutionError as error:
            if error.code == "UPSTREAM_AUTHENTICATION_FAILED": raise
            raise ExecutionError("UPSTREAM_EXECUTION_UNCERTAIN", issues=[{"upstream_idempotency_key": request_key}]) from None
        job_id = submitted.get("job", {}).get("jobId")
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9-]{36}", job_id):
            raise ExecutionError("UPSTREAM_EXECUTION_UNCERTAIN", issues=[{"upstream_idempotency_key": request_key}])
        deadline = time.monotonic() + configuration["time_limit_seconds"] + 10
        while time.monotonic() < deadline:
            try:
                body = self._request("/jobs/" + job_id)
            except ExecutionError:
                raise ExecutionError("UPSTREAM_EXECUTION_UNCERTAIN", issues=[{"upstream_job_id": job_id, "upstream_idempotency_key": request_key}]) from None
            state = body["job"]["status"]
            if state in {"succeeded", "infeasible"}:
                answer = body["outcome"]
                return {k: deepcopy(answer[k]) for k in ("solution_status", "termination_reason", "result", "effective_configuration", "proof")}
            if state in {"failed", "cancelled"}:
                raise ExecutionError("UPSTREAM_JOB_" + state.upper(), issues=[{"upstream_job_id": job_id}])
            time.sleep(0.05)
        raise ExecutionError("UPSTREAM_EXECUTION_UNCERTAIN", issues=[{"upstream_job_id": job_id, "upstream_idempotency_key": request_key}])


def make_api(host, port, state_path, token, *, descriptor_schema=None):
    if host != "127.0.0.1" or not token:
        raise ValueError("LOOPBACK_AND_TOKEN_REQUIRED")
    service = ExecutionService(descriptor(), LibraryConnector(), descriptor_schema=descriptor_schema)
    store = SQLiteJobStore(state_path)
    jobs = JobService(service, store=store, budget_seconds=35)
    principal = Principal("local-api", "authenticated-api-client")
    pool = WorkerPool(lambda index: jobs.worker(), count=2, idle_seconds=0.05)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def answer(self, code, body):
            data = json.dumps(body, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            try: hostname = urlsplit("http://" + self.headers.get("Host", "")).hostname
            except ValueError: hostname = None
            if hostname not in {"127.0.0.1", "localhost"}:
                self.answer(403, {"code": "HOST_FORBIDDEN"}); return False
            origin = self.headers.get("Origin")
            if origin:
                self.answer(403, {"code": "ORIGIN_FORBIDDEN"}); return False
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.answer(401, {"code": "AUTHENTICATION_REQUIRED"}); return False
            return True

        def do_GET(self):
            if not self.authorized(): return
            if self.path == "/contract":
                return self.answer(200, service.connector.describe())
            if self.path.startswith("/jobs/"):
                job_id = self.path[len("/jobs/"):]
                job = jobs.get(principal, job_id)
                if job is not None: return self.answer(200, {"job": job.public(), "outcome": job.result})
            self.answer(404, {"code": "NOT_FOUND"})

        def do_POST(self):
            if not self.authorized(): return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1000000: return self.answer(413, {"code": "REQUEST_SIZE_INVALID"})
                payload = json.loads(self.rfile.read(size))
                if self.path == "/validate":
                    service.validate(payload["input"], payload["configuration"])
                    return self.answer(200, {"valid": True, "issues": []})
                if self.path == "/jobs":
                    job, created = jobs.submit(principal, payload["input"], payload["configuration"], idempotency_key=payload["idempotency_key"])
                    return self.answer(202, {"job": job.public(), "replayed": not created})
                if self.path.startswith("/jobs/") and self.path.endswith("/cancel"):
                    job = jobs.cancel(principal, self.path[len("/jobs/"):-len("/cancel")])
                    return self.answer(200 if job else 404, job.public() if job else {"code": "NOT_FOUND"})
                return self.answer(404, {"code": "NOT_FOUND"})
            except (ExecutionError, PackageError) as error:
                if self.path == "/validate":
                    return self.answer(200, {"valid": False, "issues": getattr(error, "issues", []) or [{"code": error.code, "pointer": getattr(error, "path", "")} ]})
                self.answer(400, {"code": error.code})
            except IdempotencyConflict as error:
                self.answer(409, {"code": "IDEMPOTENCY_CONFLICT", "job_id": error.job_id})
            except Exception:
                self.answer(400, {"code": "REQUEST_INVALID"})

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server, pool


def main():
    parser = argparse.ArgumentParser(description="Run the reference Routing API on loopback")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    token = os.environ.get("OCP_ROUTING_API_TOKEN")
    if not token: raise SystemExit("Set OCP_ROUTING_API_TOKEN in the server environment")
    state = Path(args.state); state.mkdir(parents=True, exist_ok=True, mode=0o700)
    server, pool = make_api("127.0.0.1", args.port, state / "api.sqlite", token)
    pool.start()
    try: server.serve_forever()
    finally: server.server_close(); pool.stop(timeout=37)


if __name__ == "__main__": main()
