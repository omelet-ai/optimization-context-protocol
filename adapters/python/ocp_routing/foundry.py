"""Pinned Capability Contract HTTP integration; no internal source or solver dependency."""
from copy import copy, deepcopy
from http.client import HTTPException
import hashlib
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler

from ocp_candidate.contract import OCPError, failure, parse_json
from ocp_candidate.http_adapter import NoRedirect
from .coordinates import CoordinatesAdapter
from .ortools_backend import Outcome


def document_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class FoundryBackend:
    name = "omelet.standard-vrp"
    version = "0.0.0-unreported"  # Upstream has no independently identified native solver build version.

    def __init__(self, base_url, service_token, catalog_digest, catalog_document_sha256, *,
                 catalog_version="1.4.0", deadline_grace_ms=3000):
        # Selection is operator configuration, never inferred from a response or
        # retried with a different version. Both revisions use the same narrow
        # distance/weight mapping; their complete catalog pins remain distinct.
        if catalog_version not in ("1.3.0", "1.4.0"):
            raise ValueError("Unreviewed upstream catalog version")
        endpoint = urlparse(base_url)
        if (endpoint.scheme != "https" and not (endpoint.scheme == "http" and endpoint.hostname == "127.0.0.1")) or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in {"","/"}:
            raise ValueError("Explicit HTTPS or loopback origin required")
        if not isinstance(service_token,str) or not service_token or any(c in service_token for c in "\r\n"):
            raise ValueError("Server-side service credential required")
        if any(not re.fullmatch(r"[0-9a-f]{64}",v) for v in (catalog_digest,catalog_document_sha256)):
            raise ValueError("Both catalog identity and complete document hash must be pinned")
        if type(deadline_grace_ms) is not int or not 0 <= deadline_grace_ms <= 3000:
            raise ValueError("Local preparation grace must be between 0 and 3000 ms")
        self.base_url = base_url.rstrip("/")
        self._token = service_token
        self.catalog_digest, self.catalog_document_sha256 = catalog_digest,catalog_document_sha256
        self.catalog_version = catalog_version
        self.grace_ms = deadline_grace_ms
        self._tenant = self._idem = None
        self._record_job = None
        self.opener = build_opener(NoRedirect(),ProxyHandler({}))
        self.check_catalog()

    def scoped(self, owner, idem):
        # Only the trusted gateway supplies these; never accept caller tenant headers/body.
        child = copy(self)
        child._tenant = "ocp-" + hashlib.sha256(owner.encode()).hexdigest()
        child._idem = hashlib.sha256((owner+"\0"+idem).encode()).hexdigest()
        return child

    def _call(self, method, suffix, body=None, *, timeout=3):
        headers = {"Content-Type":"application/json", "Authorization":"Bearer "+self._token}
        if self._tenant: headers["X-OIP-Tenant-Id"] = self._tenant
        if self._idem: headers["Idempotency-Key"] = self._idem
        req = Request(self.base_url+"/api/routing/v1"+suffix,
                      data=None if body is None else json.dumps(body,allow_nan=False).encode(),
                      headers=headers,method=method)
        try:
            try: response = self.opener.open(req,timeout=max(.01,timeout))
            except HTTPError as error: response = error
            with response:
                if response.headers.get_content_type() != "application/json": raise OCPError("INVALID_UPSTREAM_RESPONSE")
                raw = response.read(1048577)
                if len(raw)>1048576: raise OCPError("INVALID_UPSTREAM_RESPONSE")
                try: value = parse_json(raw.decode())
                except OCPError: raise OCPError("INVALID_UPSTREAM_RESPONSE") from None
                if not isinstance(value,dict): raise OCPError("INVALID_UPSTREAM_RESPONSE")
                if response.status in (401,403): raise OCPError("UPSTREAM_AUTH_FAILED")
                if response.status>=300: raise OCPError("UPSTREAM_REJECTED")
                return value
        except (URLError,TimeoutError,ConnectionError,UnicodeError,HTTPException):
            raise OCPError("TRANSPORT_UNCERTAIN",message="Upstream outcome unavailable; do not resubmit automatically") from None

    def check_catalog(self):
        catalog = self._call("GET","/capabilities")
        if catalog.get("catalogDigest") != self.catalog_digest or document_hash(catalog) != self.catalog_document_sha256:
            raise OCPError("CATALOG_CHANGED")
        if any(catalog.get(k)!=v for k,v in {"contractVersion":"1","problemType":"standard-routing","apiVersion":"1.0","catalogVersion":self.catalog_version,"compilerVersion":"1.2.0","solver":"standard-vrp"}.items()):
            raise OCPError("UPSTREAM_VERSION_MISMATCH")
        return catalog

    @staticmethod
    def payload(problem, time_limit_ms):
        seconds = time_limit_ms // 1000
        if not 1 <= seconds <= 5: raise OCPError("LIMIT_EXCEEDED")
        return {"problem": {
            "depot":deepcopy(problem["depot"]),
            "vehicles":[{"id":v["id"],"vehicleType":"car","capacity":{"weight":v["capacity"],"volume":0,"extra":[]},
                         "costs":{"fixed":0,"unitDistance":1,"unitDuration":0},"skills":[],"preassignedVisitIds":[]} for v in problem["vehicles"]],
            "visits":[{"id":v["id"],"location":deepcopy(v["location"]),"demand":{"weight":v["demand"],"volume":0,"extra":[]},
                       "serviceDurationSeconds":0,"earlyDeliveryRequired":False,"earlyDeliveryPriority":0,"requiredSkills":[]} for v in problem["visits"]]},
            "formulation":{"objectives":[{"id":"minimize_total_route_cost","weight":1}],
                           "constraints":[{"instanceId":"weight:all","id":"weight_capacity","hardness":"hard"}]},
            "solverParameters":{"timeLimitSeconds":seconds,"distanceMethod":"euclidean","allowUnassignedVisits":False,
                                "useLargeSizeOptimizationAlgorithm":False,"includeDepartureCostFromDepot":True,"includeReturnCostToDepot":True,
                                "deliveryStartTime":"2000-01-01T00:00:00+00:00"}}

    def _stop(self, job):
        """Confirm termination, or retain the gateway's reservation as uncertain."""
        end = time.monotonic()+2
        try:
            self._call("DELETE","/jobs/"+job,timeout=.5)
            while time.monotonic()<end:
                response = self._call("GET","/jobs/"+job,timeout=min(.5,end-time.monotonic()))
                if response.get("jobId") != job: return False
                state = response.get("status")
                if state in {"cancelled","succeeded","failed","infeasible"}: return True
                time.sleep(.05)
        except OCPError: pass
        return False

    def solve(self, problem, time_limit_ms):
        if not self._tenant or not self._idem: raise OCPError("TRUSTED_CONTEXT_REQUIRED")
        self.check_catalog()  # Fail before any submission if the pinned contract changes.
        if not 2 <= len(problem["vehicles"]) <= 3 or len(problem["visits"])>20: raise OCPError("LIMIT_EXCEEDED")
        # Catalog/validation do not solve; the bounded deadline starts at job submission.
        payload = self.payload(problem,time_limit_ms)
        validated = self._call("POST","/validate",payload)
        if validated.get("valid") is not True: raise OCPError("UPSTREAM_REJECTED")
        end = time.monotonic()+(time_limit_ms+self.grace_ms)/1000
        job = None
        terminal = False
        try:
            accepted = self._call("POST","/jobs",payload,timeout=min(3,end-time.monotonic()))
            job = accepted.get("jobId")
            if not isinstance(job,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",job):
                raise OCPError("EXECUTION_UNCERTAIN")
            if self._record_job is not None:
                try: self._record_job(job)
                except Exception: raise OCPError("EXECUTION_UNCERTAIN") from None
            while time.monotonic()<end:
                status = self._call("GET","/jobs/"+job,timeout=min(1,end-time.monotonic()))
                if status.get("jobId") != job: raise OCPError("EXECUTION_UNCERTAIN")
                state = status.get("status")
                if state in {"succeeded","infeasible"}:
                    terminal = True
                    response = self._call("GET","/jobs/"+job+"/result",timeout=min(1,end-time.monotonic()))
                    if response.get("jobId") != job: raise OCPError("INVALID_ENGINE_RESULT")
                    return self.decode(problem,response.get("result"),job)
                if state == "cancelled": return Outcome(None,"cancelled",None)
                if state == "failed": raise OCPError("UPSTREAM_SOLVE_FAILED")
                if state not in {"queued","running"}: raise OCPError("EXECUTION_UNCERTAIN")
                time.sleep(.05)
            if self._stop(job): return Outcome(None,"time_limit",None)
            raise OCPError("EXECUTION_UNCERTAIN")
        except OCPError as error:
            if job and not terminal:
                if not self._stop(job): raise OCPError("EXECUTION_UNCERTAIN") from None
            # An ambiguous POST without a job ID cannot be retried or declared cancelled.
            if job is None and error.code not in {"UPSTREAM_AUTH_FAILED","UPSTREAM_REJECTED"}:
                raise OCPError("EXECUTION_UNCERTAIN") from None
            raise

    @staticmethod
    def decode(problem, result, job):
        if not isinstance(result,dict) or result.get("jobId")!=job: raise OCPError("INVALID_ENGINE_RESULT")
        if result.get("status") == "infeasible":
            # Native heuristic no-solution is not a mathematical certificate.
            return Outcome(None,"search_exhausted",None)
        if result.get("status") != "feasible" or result.get("unassignedVisitIds") != []:
            raise OCPError("INVALID_ENGINE_RESULT")
        ids = {v["id"] for v in problem["vehicles"]}
        seen, routes = set(),[]
        if not isinstance(result.get("routes"),list): raise OCPError("INVALID_ENGINE_RESULT")
        for route in result["routes"]:
            if not isinstance(route,dict): raise OCPError("INVALID_ENGINE_RESULT")
            vid = route.get("vehicleId")
            if not isinstance(vid,str) or vid not in ids or vid in seen or not isinstance(route.get("stopIds"),list): raise OCPError("INVALID_ENGINE_RESULT")
            seen.add(vid); routes.append({"vehicle_id":vid,"visits":route["stopIds"]})
        routes.extend({"vehicle_id":vid,"visits":[]} for vid in sorted(ids-seen))
        score = result.get("totalCost")
        if type(score) not in (int,float) or score<0: raise OCPError("INVALID_ENGINE_RESULT")
        objective = result.get("objectiveValues")
        if not isinstance(objective,list) or len(objective)!=1 or not isinstance(objective[0],dict) or objective[0].get("id")!="minimize_total_route_cost" or objective[0].get("value")!=score:
            raise OCPError("INVALID_ENGINE_RESULT")
        return Outcome({"routes":routes},"completed",score)


class FoundryCoordinatesAdapter(CoordinatesAdapter):
    def __init__(self, backend):
        super().__init__(backend,{"id":"routing.coordinates.omelet","version":"0.1.0"})

    def describe(self):
        value = super().describe()
        value["limitations"][1] = "2-3 vehicles, 1-20 visits, integer kg; solver budget 1000-5000 ms"
        value["limitations"] += ["Pinned upstream contract; 2-3 vehicles, at most 20 visits",
            "Budget floors to whole solver seconds; separate preparation grace <=3000 ms and cancellation confirmation <=2000 ms",
            "Native solver version unreported (0.0.0-unreported sentinel); catalog/compiler pinned separately",
            "Trusted gateway identity required; external signup and hosted deployment not included"]
        value["extensions"] = [{"id":"ocp.omelet.catalog","version":"0.1.0","required":False,
            "value":{"catalog_digest":self.backend.catalog_digest,"document_sha256":self.backend.catalog_document_sha256}}]
        return value

    def validate(self, request):
        checked = super().validate(request)
        if checked["valid"] and (len(request["input"]["vehicles"]) > 3 or len(request["input"]["visits"]) > 20):
            checked["valid"] = False
            checked["issues"] = [{"code":"LIMIT_EXCEEDED","path":"/input","message":"Pinned engine scope is 2-3 vehicles and at most 20 visits"}]
        return checked

    def execute(self, request):
        return failure(request.get("request_id") if isinstance(request,dict) else None,OCPError("TRUSTED_CONTEXT_REQUIRED"))

    def execute_scoped(self, request, owner, idempotency_key):
        return self.execute_tracked(request,owner,idempotency_key,None)

    def execute_tracked(self, request, owner, idempotency_key, record_job):
        checked = self.validate(request)
        if not checked["valid"]:
            issue = checked["issues"][0]
            return failure(checked["request_id"],OCPError(issue["code"],issue["path"],issue["message"]))
        backend = self.backend.scoped(owner,idempotency_key)
        backend._record_job = record_job
        scoped = CoordinatesAdapter(backend,deepcopy(self.identity))
        result = scoped.execute(request)
        if result["kind"] == "result":
            result["extensions"] = deepcopy(self.describe()["extensions"])
            result["provenance"]["limitations"].append("Native solver build version is unreported; 0.0.0-unreported is a sentinel. Catalog/compiler are pinned by the catalog extension.")
        return result

    def stop_recorded_job(self, owner, idempotency_key, job):
        """Operator recovery: GET before DELETE; never submit/retry a solve."""
        if not isinstance(job,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",job):
            raise OCPError("INVALID_REQUEST")
        backend = self.backend.scoped(owner,idempotency_key)
        status = backend._call("GET","/jobs/"+job)
        if status.get("jobId") != job: raise OCPError("EXECUTION_UNCERTAIN")
        if status.get("status") in {"cancelled","succeeded","failed","infeasible"}: return True
        if status.get("status") not in {"queued","running"}: raise OCPError("EXECUTION_UNCERTAIN")
        return backend._stop(job)
