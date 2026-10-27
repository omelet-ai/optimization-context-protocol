"""Installed invitation operations and MCP bridge; external hosting is not certified."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_candidate import build
from isolated_candidate import install
from check_h02 import request
from conformance.routing import verify_result
from conformance.core_contract import validate_message

WORK=tempfile.TemporaryDirectory(prefix="ocp-invitation-check-")
DIRECTORY=Path(WORK.name)
ARTIFACT=build(DIRECTORY)
PYTHON,ENV=install(DIRECTORY,ARTIFACT["wheel"],"reference,mcp")
sys.path.insert(0,ARTIFACT["wheel"])
from ocp_candidate import OCPError
from ocp_runtime.trial_ops import InvitationGateway, InvitationPolicy, operation_lock, read_private_json, write_private_json
from ocp_runtime.trial import TrialGateway, Policy, digest
from ocp_runtime.trial_client import InvitationClient
from ocp_runtime.http_server import create_server
from ocp_routing import RoutingAdapter, ORToolsBackend
from ocp_routing.foundry import FoundryCoordinatesAdapter
from mcp import Client as MCPClient, StdioServerParameters


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix="ocp-invited-")
        self.root=Path(self.directory.name);self.now=1800000000.
        self.adapter=RoutingAdapter(ORToolsBackend())
        self.policy=InvitationPolicy(digest(self.adapter.describe()))
        self.gateway=InvitationGateway(self.root/"trial.sqlite",self.adapter,self.policy,clock=lambda:self.now)
        self.token=self.gateway.issue("tester-1")
        self.server=create_server(self.adapter,service=self.gateway)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url="http://127.0.0.1:"+str(self.server.server_port)
        self.session=self.root/"session.json"
        write_private_json(self.session,{"endpoint":self.url,"token":self.token,
            "catalog_sha256":digest(self.gateway.dispatch("describe",token=self.token))})

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.directory.cleanup()

    def req(self,rid="same"):
        value=request();value["request_id"]=rid;value["budget"]["time_limit_ms"]=1;return value

    def execute(self,idem="same",token=None):
        return self.gateway.execute(token or self.token,self.req(idem),idem)

    def code(self,value,code):
        validate_message(value);self.assertEqual(value["kind"],"failure");self.assertEqual(value["error"]["code"],code)

    def test_01_five_principals_rotation_revocation_never_resets_capacity(self):
        for n in range(2,6): self.gateway.issue("tester-"+str(n))
        self.gateway.issue("tester-1");self.gateway.revoke_principal("tester-2")
        with self.assertRaises(OCPError) as error:self.gateway.issue("sixth")
        self.assertEqual(error.exception.code,"INVITATION_LIMIT")
        self.assertEqual(self.gateway.summary()["principals"],5)

    def test_02_global_call_count_independent_of_short_compute_budget(self):
        gate=InvitationGateway(self.root/"small.sqlite",self.adapter,replace(self.policy,global_calls=2))
        a,b=gate.issue("a"),gate.issue("b")
        for key,token in [("one",a),("two",b)]:self.assertEqual(gate.execute(token,self.req(key),key)["kind"],"result")
        self.code(gate.execute(b,self.req("third"),"third"),"QUOTA_EXCEEDED")
        self.assertEqual(gate.summary()["reserved_ms"],2)

    def test_03_pause_blocks_new_execution_but_preserves_replay(self):
        first=self.execute();self.gateway.pause()
        self.assertEqual(first,self.execute());self.code(self.execute("new"),"TRIAL_PAUSED")
        self.gateway.pause(False);self.assertEqual(self.execute("new")["kind"],"result")

    def test_04_restart_keeps_pause_usage_and_pins(self):
        self.execute();self.gateway.pause()
        reopened=InvitationGateway(self.gateway.path,self.adapter,self.policy,clock=lambda:self.now)
        self.assertEqual(reopened.summary(),self.gateway.summary())
        with self.assertRaises(ValueError):InvitationGateway(self.gateway.path,self.adapter,replace(self.policy,global_calls=49))

    def test_05_private_session_permissions_symlink_and_overwrite(self):
        os.chmod(self.session,0o644)
        with self.assertRaises(ValueError):read_private_json(self.session)
        os.chmod(self.session,0o600)
        alias=self.root/"alias";alias.symlink_to(self.session)
        with self.assertRaises(OSError):read_private_json(alias)
        with self.assertRaises(FileExistsError):write_private_json(self.session,{"token":"overwrite"})
        self.assertEqual(read_private_json(self.session)["token"],self.token)

    def test_06_malformed_invitation_and_insecure_nonloopback_rejected(self):
        original=read_private_json(self.session)
        for changes in [{"endpoint":"http://example.invalid"},{"endpoint":"https://"},{"token":"internal-service-token"},{"catalog_sha256":"bad"}]:
            path=self.root/(str(len(list(self.root.iterdir())))+".json")
            write_private_json(path,dict(original,**changes))
            with self.assertRaises((ValueError,OCPError)):InvitationClient(path)

    def test_07_descriptor_drift_rejected_before_execution(self):
        value=read_private_json(self.session);value["catalog_sha256"]="0"*64
        path=self.root/"drift.json";write_private_json(path,value)
        with self.assertRaises(OCPError) as error:InvitationClient(path).execute(self.req())
        self.assertEqual(error.exception.code,"CATALOG_CHANGED");self.assertEqual(self.gateway.summary()["calls"],0)

    def test_08_installed_doctor_authenticates_without_spending_or_printing_key(self):
        result=subprocess.run([str(PYTHON),"-I","-B","-m","ocp_runtime.trial_client","--session",str(self.session),"doctor"],
            env=ENV,cwd=DIRECTORY,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["scope"],"authenticated_discovery_only_no_solve")
        self.assertNotIn(self.token,result.stdout+result.stderr);self.assertEqual(self.gateway.summary()["calls"],0)

    def test_09_revoked_invitation_blocks_discovery_and_replay(self):
        self.execute();self.gateway.revoke_principal("tester-1")
        with self.assertRaises(OCPError) as error:InvitationClient(self.session).describe()
        self.assertEqual(error.exception.code,"UNAUTHORIZED");self.code(self.execute(),"UNAUTHORIZED")

    def test_10_exclusive_operator_lock_survives_stale_file(self):
        with operation_lock(self.gateway.path):
            code="from ocp_runtime.trial_ops import operation_lock;\nwith operation_lock("+repr(str(self.gateway.path))+"): pass"
            result=subprocess.run([str(PYTHON),"-I","-B","-c",code],env=ENV,cwd=DIRECTORY,capture_output=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
        with operation_lock(self.gateway.path):pass

    def crashed(self,record=True,confirmed=True):
        def crash(req,owner,idem,record_job):
            if record:record_job("job-123")
            raise SystemExit("injected process death")
        self.adapter.execute_tracked=crash
        with self.assertRaises(SystemExit):self.execute()
        seen=[]
        def stop(owner,idem,job):seen.append((owner,idem,job));return confirmed
        self.adapter.stop_recorded_job=stop
        return seen

    def test_11_recovery_after_crash_confirms_bound_job_and_never_refunds(self):
        seen=self.crashed()
        reopened=InvitationGateway(self.gateway.path,self.adapter,self.policy,clock=lambda:self.now)
        with operation_lock(self.gateway.path):reopened.recover("tester-1","same")
        self.assertEqual(seen,[("tester-1","same","job-123")])
        self.assertEqual(reopened.summary()["held"],[]);self.assertEqual(reopened.summary()["calls"],1)
        self.code(self.execute(),"RESULT_EXPIRED")
        del self.adapter.execute_tracked
        self.assertEqual(self.execute("new")["kind"],"result")

    def test_12_ambiguous_post_without_job_stays_held(self):
        seen=self.crashed(record=False)
        with self.assertRaises(OCPError):self.gateway.recover("tester-1","same")
        self.assertEqual(seen,[]);self.assertEqual(len(self.gateway.summary()["held"]),1)

    def test_13_unconfirmed_stop_or_foreign_owner_never_releases(self):
        self.crashed(confirmed=False)
        for owner in ("tester-1","foreign"):
            with self.assertRaises(OCPError):self.gateway.recover(owner,"same")
        self.assertEqual(len(self.gateway.summary()["held"]),1)

    def test_14_backup_and_payload_expiry_preserve_quota(self):
        self.execute();copy=self.root/"backup.sqlite";self.gateway.backup(copy)
        self.assertEqual(copy.stat().st_mode & 0o777,0o600)
        other=InvitationGateway(copy,self.adapter,self.policy,clock=lambda:self.now)
        self.assertEqual(other.summary(),self.gateway.summary())
        self.now+=86400;self.gateway.purge_results()
        self.code(self.execute(),"RESULT_EXPIRED");self.assertEqual(self.gateway.summary()["calls"],1)
        with sqlite3.connect(self.gateway.path) as db:self.assertIsNone(db.execute("SELECT response FROM runs").fetchone()[0])

    def test_15_duplicate_auth_and_host_are_rejected(self):
        for header in ("Host","Authorization","Idempotency-Key"):
            conn=HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
            conn.putrequest("GET","/v1/capability",skip_host=True)
            conn.putheader("Host","127.0.0.1:"+str(self.server.server_port))
            conn.putheader("Authorization","Bearer "+self.token)
            conn.putheader("Idempotency-Key","a")
            conn.putheader(header,"extra");conn.endheaders()
            response=conn.getresponse();self.assertEqual(response.status,403);response.read();conn.close()

    def test_16_connection_threads_bounded_before_reading_headers(self):
        sockets=[]
        try:
            for _ in range(8):
                sock=socket.create_connection(("127.0.0.1",self.server.server_port),timeout=2)
                sock.sendall(b"GET /v1/capability HTTP/1.1\r\n");sockets.append(sock)
            # Accept loop is FIFO; ninth is closed before allocating a worker.
            extra=socket.create_connection(("127.0.0.1",self.server.server_port),timeout=2)
            try:self.assertEqual(extra.recv(1),b"")
            finally:extra.close()
        finally:
            for sock in sockets:sock.close()

    def test_17_legacy_policy_database_requires_no_migration(self):
        path=self.root/"legacy.sqlite";policy=Policy(digest(self.adapter.describe()))
        gate=TrialGateway(path,self.adapter,policy);token=gate.issue("legacy")
        first=gate.execute(token,self.req(),"same")
        self.assertEqual(first,TrialGateway(path,self.adapter,policy).execute(token,self.req(),"same"))

    def test_18_foundry_recovery_only_scoped_get_delete_never_submit(self):
        class Backend:
            def scoped(inner,owner,idem):
                self.assertEqual((owner,idem),("tester-1","same"));return inner
            def _call(inner,method,path):
                self.assertEqual((method,path),("GET","/jobs/job-123"));return {"jobId":"job-123","status":"running"}
            def _stop(inner,job):self.assertEqual(job,"job-123");return True
        adapter=FoundryCoordinatesAdapter(Backend())
        self.assertTrue(adapter.stop_recorded_job("tester-1","same","job-123"))
        with self.assertRaises(OCPError):adapter.stop_recorded_job("tester-1","same","../foreign")

    def test_19_installed_mcp_bridge_executes_evaluates_replays(self):
        async def scenario():
            async with MCPClient(StdioServerParameters(command=str(PYTHON),args=["-I","-B","-m","ocp_runtime.trial_client","--session",str(self.session),"mcp"],env=ENV,cwd=str(DIRECTORY)),read_timeout_seconds=15) as client:
                tools=await client.list_tools();self.assertEqual(len(tools.tools),6)
                result=await client.call_tool("ocp_describe",{});self.assertEqual(result.structured_content["kind"],"capability")
                req=request()
                first=await client.call_tool("ocp_execute",{"request":req})
                self.assertEqual(verify_result(req,first.structured_content)["total_cost"],18)
                second=await client.call_tool("ocp_execute",{"request":req})
                self.assertEqual(first.structured_content,second.structured_content)
                evaluated=await client.call_tool("ocp_evaluate",{"request":req,"solution":first.structured_content["solution"]})
                self.assertEqual(evaluated.structured_content["metrics"][0]["value"],18)
                invalid=deepcopy(req);invalid["configuration"]["objectives"][0]["weight"]=2
                rejected=await client.call_tool("ocp_execute",{"request":invalid});self.assertTrue(rejected.is_error)
                self.assertEqual(self.gateway.summary()["calls"],1)
        asyncio.run(scenario())


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(InvitationTests))
        passed=result.wasSuccessful() and result.testsRun>=19 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),
            "errors":len(result.errors),"skipped":len(result.skipped),"artifact_sha256":ARTIFACT["sha256"],
            "scope":"Installed invitation operations and MCP/HTTP with real OR-Tools, injected crash/recovery. No external hosting, Claude Code host, money billing or external users"}))
    finally:WORK.cleanup()
    sys.exit(0 if passed else 1)
