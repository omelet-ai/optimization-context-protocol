"""Private local policy candidate. Identity provisioning and upstream integration are external gates."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from ocp_candidate.contract import OCPError, envelope, failure
from .service import Service


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Policy:
    catalog_sha256: str
    version: str = "0.1.0-local-candidate"
    min_vehicles: int = 2
    max_vehicles: int = 3
    max_visits: int = 20
    max_time_ms: int = 5000
    daily_calls: int = 30
    total_calls: int = 420
    daily_reserved_ms: int = 150000
    total_reserved_ms: int = 2100000
    global_reserved_ms: int = 2100000
    concurrent: int = 1
    lifetime_seconds: int = 14 * 86400
    result_retention_seconds: int = 86400

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{64}",self.catalog_sha256): raise ValueError("Invalid catalog digest")
        for name,value in asdict(self).items():
            if name not in {"catalog_sha256","version"} and (type(value) is not int or value<1):
                raise ValueError("Positive integer policy limits required")
        if self.min_vehicles>self.max_vehicles or self.max_vehicles>3 or self.max_visits>20 or self.max_time_ms>5000:
            raise ValueError("Local policy candidate exceeds verified trial proposal scope")


class TrialGateway:
    """Atomic organization budgets survive key rotation, retries, restarts and UTC rollover."""
    def __init__(self, path, adapter, policy, clock=time.time):
        self.path=Path(path); self.adapter=adapter; self.policy=policy; self.clock=clock
        if digest(adapter.describe())!=policy.catalog_sha256:
            raise ValueError("Policy catalog digest differs from actual provider descriptor")
        if not self.path.exists():
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
        if self.path.is_symlink(): raise ValueError("Policy database cannot be a symlink")
        os.chmod(self.path,0o600)
        with self.transaction() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, policy TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS principals (id TEXT PRIMARY KEY, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS keys (hash TEXT PRIMARY KEY, owner TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS runs (owner TEXT NOT NULL, idem TEXT NOT NULL, request_digest TEXT NOT NULL,
                day INTEGER NOT NULL, created REAL NOT NULL, reserved_ms INTEGER NOT NULL,
                state TEXT NOT NULL, response TEXT, elapsed_ms INTEGER, PRIMARY KEY(owner,idem));
            ''')
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute("SELECT policy FROM settings WHERE id=1").fetchone()
            encoded=canonical(asdict(policy))
            if existing and existing[0]!=encoded: raise ValueError("Explicit policy migration required; budgets cannot reset")
            db.execute("INSERT OR IGNORE INTO settings VALUES(1,?)",(encoded,))

    @contextmanager
    def transaction(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            if db.in_transaction: db.execute("COMMIT")
        except BaseException:
            if db.in_transaction: db.execute("ROLLBACK")
            raise
        finally: db.close()

    def issue(self, owner):
        """Trusted operator API only, never exposed as a public signup endpoint."""
        if not isinstance(owner,str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",owner): raise ValueError("Invalid principal")
        token="ocp_trial_"+secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO principals(id,expires) VALUES(?,?)",(owner,self.clock()+self.policy.lifetime_seconds))
            principal=db.execute("SELECT * FROM principals WHERE id=?",(owner,)).fetchone()
            if principal["revoked"] or principal["expires"]<=self.clock(): raise OCPError("TRIAL_EXPIRED")
            db.execute("INSERT INTO keys(hash,owner) VALUES(?,?)",(hashlib.sha256(token.encode()).hexdigest(),owner))
        return token

    def revoke(self, token):
        with self.transaction() as db:
            db.execute("UPDATE keys SET revoked=1 WHERE hash=?",(hashlib.sha256(token.encode()).hexdigest(),))

    def revoke_principal(self, owner):
        with self.transaction() as db: db.execute("UPDATE principals SET revoked=1 WHERE id=?",(owner,))

    def _owner(self, db, token):
        if not isinstance(token,str) or not re.fullmatch(r"ocp_trial_[A-Za-z0-9_-]{43}",token): raise OCPError("UNAUTHORIZED")
        row=db.execute("SELECT k.owner,k.revoked AS key_revoked,p.revoked,p.expires FROM keys k JOIN principals p ON p.id=k.owner WHERE k.hash=?",(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None or row["key_revoked"] or row["revoked"]: raise OCPError("UNAUTHORIZED")
        if row["expires"]<=self.clock(): raise OCPError("TRIAL_EXPIRED")
        return row["owner"]

    def _entitled(self, request):
        envelope(request)
        if request["kind"]!="request": raise OCPError("INVALID_REQUEST")
        checked=self.adapter.validate(deepcopy(request)); envelope(checked)
        if checked["kind"]!="validation" or checked["request_id"]!=request["request_id"]: raise OCPError("INVALID_RESPONSE")
        if not checked["valid"]:
            issue=checked["issues"][0]; raise OCPError(issue["code"],issue["path"],issue["message"])
        data=request["input"]
        if not self.policy.min_vehicles<=len(data["vehicles"])<=self.policy.max_vehicles or len(data["visits"])>self.policy.max_visits or request["budget"]["time_limit_ms"]>self.policy.max_time_ms:
            raise OCPError("ENTITLEMENT_EXCEEDED")
        if digest(self.adapter.describe())!=self.policy.catalog_sha256: raise OCPError("CATALOG_CHANGED")

    def _reserve(self, token, request, idem):
        if not isinstance(idem,str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",idem): raise OCPError("IDEMPOTENCY_KEY_REQUIRED")
        with self.transaction() as db:
            owner=self._owner(db,token)
            self._entitled(request)
            previous=db.execute("SELECT * FROM runs WHERE owner=? AND idem=?",(owner,idem)).fetchone()
            if previous:
                if previous["request_digest"]!=digest(request): raise OCPError("IDEMPOTENCY_CONFLICT")
                if previous["state"]=="expired": raise OCPError("RESULT_EXPIRED")
                if previous["state"]=="uncertain" and previous["response"] is not None:
                    return owner,json.loads(previous["response"])
                if previous["state"]!="done": raise OCPError("EXECUTION_UNCERTAIN",message="Execution reserved; never automatically resubmit")
                if previous["created"]+self.policy.result_retention_seconds<=self.clock(): raise OCPError("RESULT_EXPIRED")
                return owner,json.loads(previous["response"])
            active=db.execute("SELECT count(*) FROM runs WHERE owner=? AND state IN ('running','uncertain')",(owner,)).fetchone()[0]
            if active>=self.policy.concurrent: raise OCPError("CONCURRENCY_LIMIT")
            day=int(self.clock()//86400)
            row=db.execute("SELECT count(*) AS calls,coalesce(sum(reserved_ms),0) AS budget FROM runs WHERE owner=?",(owner,)).fetchone()
            daily=db.execute("SELECT count(*) AS calls,coalesce(sum(reserved_ms),0) AS budget FROM runs WHERE owner=? AND day=?",(owner,day)).fetchone()
            global_budget=db.execute("SELECT coalesce(sum(reserved_ms),0) FROM runs").fetchone()[0]
            amount=request["budget"]["time_limit_ms"]
            if daily["calls"]>=self.policy.daily_calls or row["calls"]>=self.policy.total_calls: raise OCPError("QUOTA_EXCEEDED")
            if daily["budget"]+amount>self.policy.daily_reserved_ms or row["budget"]+amount>self.policy.total_reserved_ms or global_budget+amount>self.policy.global_reserved_ms:
                raise OCPError("COST_LIMIT")
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,'running',NULL,NULL)",(owner,idem,digest(request),day,self.clock(),amount))
            return owner,None

    def execute(self, token, request, idem):
        request=deepcopy(request)
        rid=request.get("request_id") if isinstance(request,dict) else None
        try:
            owner,replay=self._reserve(token,request,idem)
            if replay is not None: return replay
            start=time.monotonic()
            try:
                response=self.adapter.execute(deepcopy(request)); envelope(response)
                if response["kind"] not in {"result","failure"} or response["request_id"]!=rid: raise OCPError("INVALID_RESPONSE")
                if response["kind"]=="result":
                    for field in ("capability","domain_profile","execution_profile"):
                        if response[field]!=request[field]: raise OCPError("INVALID_RESPONSE")
                    if response["effective_configuration"]!=request["configuration"]: raise OCPError("INVALID_RESPONSE")
            except Exception:
                response=failure(rid,OCPError("EXECUTION_UNCERTAIN",message="Engine response unavailable; reservation retained and no automatic retry"))
            # Full requested budget is reserved even for failures; wall latency is not a monetary bill.
            state="uncertain" if response["kind"]=="failure" and response["error"]["code"] in {"EXECUTION_UNCERTAIN","TRANSPORT_UNCERTAIN","EXECUTION_ERROR"} else "done"
            with self.transaction() as db:
                db.execute("UPDATE runs SET state=?,response=?,elapsed_ms=? WHERE owner=? AND idem=?",(state,canonical(response),int((time.monotonic()-start)*1000),owner,idem))
            return response
        except OCPError as error:
            return failure(rid,error)

    def lookup(self, token, idem):
        """Owner-scoped replay only. No async job or foreign principal lookup."""
        with self.transaction() as db:
            owner=self._owner(db,token)
            row=db.execute("SELECT * FROM runs WHERE owner=? AND idem=?",(owner,idem)).fetchone()
            if row is None: raise OCPError("NOT_FOUND")
            if row["state"]=="expired": raise OCPError("RESULT_EXPIRED")
            if row["state"]=="uncertain" and row["response"] is not None: return json.loads(row["response"])
            if row["state"]!="done": raise OCPError("EXECUTION_UNCERTAIN")
            if row["created"]+self.policy.result_retention_seconds<=self.clock(): raise OCPError("RESULT_EXPIRED")
            return json.loads(row["response"])

    def purge_results(self):
        """Operator maintenance: retain counts/digests, erase expired solution payloads."""
        with self.transaction() as db:
            db.execute("UPDATE runs SET response=NULL,state='expired' WHERE state='done' AND created<=?",(self.clock()-self.policy.result_retention_seconds,))

    def dispatch(self, operation, payload=None, binding="binding.http", token=None, idempotency_key=None):
        try:
            with self.transaction() as db: self._owner(db,token)
            if operation=="execute": return self.execute(token,payload,idempotency_key)
            if operation in {"validate","evaluate"}:
                # Evaluation input belongs to this request; no lookup by arbitrary tenant/job ID.
                self._entitled(payload if operation=="validate" else payload["request"])
            if operation not in {"describe","requirements","validate","evaluate"}: raise OCPError("UNSUPPORTED_OPERATION")
            response=Service(self.adapter).dispatch(operation,payload,binding)
            if operation=="describe":
                response["environments"]=[{"id":"environment.trial_local_candidate","version":"0.1.0"}]
                response["extensions"]=[{"id":"ocp.trial.policy","version":"0.1.0","required":False,
                    "value":{"source_catalog_sha256":self.policy.catalog_sha256,"policy":asdict(self.policy)}}]
                response["limitations"].append("Local trial policy candidate with separate limits; not a hosted Omelet trial")
                envelope(response)
            return response
        except OCPError as error:
            return failure(payload.get("request_id") if isinstance(payload,dict) else None,error)
        except (KeyError,TypeError):
            return failure(None,OCPError("INVALID_REQUEST"))
