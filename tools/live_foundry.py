"""Explicit local integration settings and a durable test-run submission ceiling."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SETTINGS=ROOT/".private/local-foundry-api/adapter-settings.json"


def settings():
    value=json.loads(SETTINGS.read_text())
    if value["base_url"]!="http://127.0.0.1:8188" or value["scope"]!="user_authorized_local_synthetic_only":
        raise RuntimeError("Only the explicitly authorized local environment may run this check")
    identity=json.loads((SETTINGS.parent/value["source_identity_file"]).read_text())
    checkout=Path(value["source_checkout"])
    for name,sha in identity["loaded_source_sha256"].items():
        if hashlib.sha256((checkout/name).read_bytes()).hexdigest()!=sha:
            raise RuntimeError("Upstream source changed; review and restart before accepting evidence")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=checkout,text=True).strip()
    if head!=identity["head"]: raise RuntimeError("Upstream checkout identity changed")
    credential=SETTINGS.parent/value["credential_file"]
    if credential.is_symlink() or credential.stat().st_mode & 0o077: raise RuntimeError("Credential file must be private")
    secret=json.loads(credential.read_text())["service_token"]
    return value,secret,identity["aggregate_sha256"]


def backend():
    from ocp_routing.foundry import FoundryBackend
    value,secret,_=settings()
    ledger=ROOT/".harness/work/local-foundry-submissions.sqlite"
    ledger.parent.mkdir(parents=True,exist_ok=True)
    class ObservedBackend(FoundryBackend):
        # Observation is restricted to test tooling; production implementation is unchanged.
        calls=[]
        def _call(self, method, suffix, body=None, **kwargs):
            if method=="POST" and suffix=="/jobs":
                with sqlite3.connect(ledger,timeout=10) as db:
                    db.execute("CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, started TEXT DEFAULT CURRENT_TIMESTAMP)")
                    db.execute("BEGIN IMMEDIATE")
                    if db.execute("SELECT count(*) FROM submissions").fetchone()[0]>=value["max_additional_job_submissions"]:
                        raise RuntimeError("Local verification submission ceiling reached")
                    db.execute("INSERT INTO submissions DEFAULT VALUES")
            result=super()._call(method,suffix,body,**kwargs)
            self.calls.append({"method":method,"path":suffix,"tenant":self._tenant,
                               "job_id":result.get("jobId"),"status":result.get("status"),
                               "solver_seconds":body.get("solverParameters",{}).get("timeLimitSeconds") if isinstance(body,dict) else None})
            return result
    return ObservedBackend(value["base_url"],secret,value["catalog_digest"],value["catalog_document_sha256"])
