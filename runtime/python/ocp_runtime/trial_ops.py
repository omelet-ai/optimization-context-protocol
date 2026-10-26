"""Single-host invitation operations. Never expose these commands over HTTP."""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import threading

from ocp_candidate.contract import OCPError, failure, parse_json
from .trial import Policy, TrialGateway, canonical, digest


@dataclass(frozen=True)
class InvitationPolicy(Policy):
    version: str = "0.1.0-invitation-candidate"
    daily_calls: int = 5
    total_calls: int = 10
    daily_reserved_ms: int = 25000
    total_reserved_ms: int = 50000
    global_reserved_ms: int = 250000
    global_calls: int = 50
    max_principals: int = 5

    def __post_init__(self):
        super().__post_init__()
        if self.global_calls > 50 or self.max_principals > 5:
            raise ValueError("Invitation campaign exceeds verified scope")


class PrivateFileError(ValueError):
    def __init__(self,code):
        super().__init__(code)
        self.code=code


def read_private_json(path):
    """No symlinks, non-regular files, group/world access, or oversized secrets."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode): raise PrivateFileError("INVITATION_UNSAFE_FILE")
        if info.st_mode & 0o077: raise PrivateFileError("INVITATION_PERMISSIONS")
        if info.st_size>65536: raise PrivateFileError("INVITATION_TOO_LARGE")
        value=parse_json(stream.read(65537))
        if not isinstance(value,dict): raise ValueError("Object required")
        return value


def write_private_json(path, value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as stream:
        stream.write(canonical(value)+"\n"); stream.flush(); os.fsync(stream.fileno())


@contextmanager
def operation_lock(database, *, serving=False):
    """Mutating/recovery operators require the serving process to be stopped.

    Multiple read/issuance operators are deliberately serialized too. A crashed
    process releases the OS lock; stale lock files do not grant permission.
    """
    fd=os.open(str(database)+".lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally: os.close(fd)


class InvitationGateway(TrialGateway):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not isinstance(self.policy,InvitationPolicy): raise ValueError("Invitation policy required")
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS admission (id INTEGER PRIMARY KEY, paused INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO admission VALUES(1,0)")
            db.execute("CREATE TABLE IF NOT EXISTS upstream_jobs (owner TEXT NOT NULL, idem TEXT NOT NULL, job TEXT NOT NULL, PRIMARY KEY(owner,idem))")
            db.execute("CREATE TABLE IF NOT EXISTS recoveries (owner TEXT NOT NULL, idem TEXT NOT NULL, confirmed REAL NOT NULL, PRIMARY KEY(owner,idem))")

    def _check_admission(self,db):
        if db.execute("SELECT paused FROM admission WHERE id=1").fetchone()[0]: raise OCPError("TRIAL_PAUSED")
        if db.execute("SELECT count(*) FROM runs").fetchone()[0]>=self.policy.global_calls: raise OCPError("QUOTA_EXCEEDED")

    def pause(self, paused=True):
        with self.transaction() as db: db.execute("UPDATE admission SET paused=? WHERE id=1",(int(paused),))

    def record_job(self,owner,idem,job):
        if not isinstance(job,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",job): raise OCPError("INVALID_UPSTREAM_RESPONSE")
        with self.transaction() as db:
            row=db.execute("SELECT state FROM runs WHERE owner=? AND idem=?",(owner,idem)).fetchone()
            if row is None or row["state"]!="running": raise OCPError("EXECUTION_UNCERTAIN")
            db.execute("INSERT INTO upstream_jobs VALUES(?,?,?)",(owner,idem,job))

    def recover(self,owner,idem):
        """Call only offline under operation_lock. Never accept an arbitrary job ID.

        Terminal confirmation releases concurrency, never spent quota. The prior
        request remains a failure on replay; no invented successful solution.
        A lost submission response without a recorded ID stays held.
        """
        with self.transaction() as db:
            row=db.execute("SELECT state FROM runs WHERE owner=? AND idem=?",(owner,idem)).fetchone()
            job=db.execute("SELECT job FROM upstream_jobs WHERE owner=? AND idem=?",(owner,idem)).fetchone()
            if row is None: raise OCPError("NOT_FOUND")
            if row["state"] not in {"running","uncertain"}: raise OCPError("RECOVERY_NOT_REQUIRED")
            if job is None or not hasattr(self.adapter,"stop_recorded_job"): raise OCPError("EXECUTION_UNCERTAIN")
        if self.adapter.stop_recorded_job(owner,idem,job["job"]) is not True: raise OCPError("EXECUTION_UNCERTAIN")
        # Original request ID is not stored if the process died before returning.
        # A separate terminal marker avoids inventing it in a replay response.
        with self.transaction() as db:
            changed=db.execute("UPDATE runs SET state='expired',response=NULL WHERE owner=? AND idem=? AND state IN ('running','uncertain')",(owner,idem)).rowcount
            if changed!=1: raise OCPError("EXECUTION_UNCERTAIN")
            db.execute("INSERT INTO recoveries VALUES(?,?,?)",(owner,idem,self.clock()))

    def summary(self):
        with self.transaction() as db:
            return {"paused":bool(db.execute("SELECT paused FROM admission WHERE id=1").fetchone()[0]),
                "principals":db.execute("SELECT count(*) FROM principals").fetchone()[0],
                "calls":db.execute("SELECT count(*) FROM runs").fetchone()[0],
                "reserved_ms":db.execute("SELECT coalesce(sum(reserved_ms),0) FROM runs").fetchone()[0],
                "held":[dict(r) for r in db.execute("SELECT r.owner,r.idem,r.state,u.job FROM runs r LEFT JOIN upstream_jobs u ON r.owner=u.owner AND r.idem=u.idem WHERE r.state IN ('running','uncertain')")]}

    def backup(self,path):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
        with sqlite3.connect(self.path) as source, sqlite3.connect(path) as target: source.backup(target)

    def dispatch(self,*args,**kwargs):
        response=super().dispatch(*args,**kwargs)
        if response["kind"]=="capability":
            response["limitations"]=[s for s in response["limitations"] if s!="Local trial policy candidate with separate limits; not a hosted Omelet trial"]
            response["limitations"].append("Invitation candidate: five principals, fifty total executions; single-host operation; hosting and external acceptance require separate verification")
        return response


def load_gateway(config):
    from ocp_routing.foundry import FoundryBackend, FoundryCoordinatesAdapter
    value=read_private_json(config)
    required={"database","upstream","service_token_file","catalog_version","catalog_digest","catalog_document_sha256"}
    if set(value)!=required or any(not isinstance(v,str) or not v for v in value.values()): raise ValueError("Invalid operator configuration")
    for field in ("database","service_token_file"):
        if not Path(value[field]).is_absolute(): raise ValueError("Absolute private paths required")
    secret=read_private_json(value["service_token_file"])
    if set(secret)!={"token"}: raise ValueError("Invalid credential file")
    adapter=FoundryCoordinatesAdapter(FoundryBackend(value["upstream"],secret["token"],value["catalog_digest"],
        value["catalog_document_sha256"],catalog_version=value["catalog_version"]))
    return InvitationGateway(value["database"],adapter,InvitationPolicy(digest(adapter.describe())))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",required=True)
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("status");sub.add_parser("pause");sub.add_parser("resume");sub.add_parser("purge")
    issue=sub.add_parser("issue");issue.add_argument("--principal",required=True);issue.add_argument("--endpoint",required=True);issue.add_argument("--out",required=True)
    revoke=sub.add_parser("revoke");revoke.add_argument("--principal",required=True)
    recover=sub.add_parser("recover");recover.add_argument("--principal",required=True);recover.add_argument("--idempotency-key",required=True)
    backup=sub.add_parser("backup");backup.add_argument("--out",required=True)
    serve=sub.add_parser("serve");serve.add_argument("--port",type=int,default=8190)
    args=parser.parse_args()
    try:
        value=read_private_json(args.config)
        # Lock before network calls or database creation; operator and service never overlap.
        with operation_lock(value["database"]):
            gateway=load_gateway(args.config)
            if args.action=="issue":
                from ocp_candidate.http_adapter import HTTPAdapter
                HTTPAdapter(args.endpoint)
                if Path(args.out).exists(): raise ValueError("Output already exists")
                token=gateway.issue(args.principal)
                try:
                    descriptor=gateway.dispatch("describe",token=token)
                    write_private_json(args.out,{"endpoint":args.endpoint,"token":token,"catalog_sha256":digest(descriptor)})
                except BaseException:
                    gateway.revoke(token);raise
            elif args.action=="revoke": gateway.revoke_principal(args.principal)
            elif args.action=="pause": gateway.pause()
            elif args.action=="resume": gateway.pause(False)
            elif args.action=="purge": gateway.purge_results()
            elif args.action=="recover": gateway.recover(args.principal,args.idempotency_key)
            elif args.action=="backup": gateway.backup(args.out)
            elif args.action=="serve":
                from .http_server import create_server
                server=create_server(gateway.adapter,args.port,service=gateway)
                server.daemon_threads=False
                stop=threading.Event()
                def maintenance():
                    while not stop.wait(60):
                        try: gateway.purge_results()
                        except Exception:
                            gateway.pause(); return
                gateway.purge_results()
                worker=threading.Thread(target=maintenance,daemon=True);worker.start()
                print(json.dumps({"listening":"http://127.0.0.1:"+str(server.server_port),"scope":"invitation_candidate"}),flush=True)
                try: server.serve_forever()
                finally: stop.set();server.server_close();worker.join()
            print(json.dumps({"status":"OK","summary":gateway.summary()}))
    except KeyboardInterrupt: return 0
    except Exception as error:
        # Never echo credentials, upstream responses, or arbitrary exception messages.
        code=error.code if isinstance(error,OCPError) else "OPERATOR_ACTION_FAILED"
        print(json.dumps({"status":"FAIL","code":code}),file=sys.stderr);return 1
    return 0


if __name__=="__main__": sys.exit(main())
