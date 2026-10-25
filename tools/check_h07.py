"""H07 local durable policy, real reference solve and explicitly injected failures."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_candidate import build
from conformance.core_contract import validate_message
from conformance.routing import verify_result
from check_h02 import request, FIXTURE

WORK=tempfile.TemporaryDirectory(prefix="ocp-h07-")
ARTIFACT=build(WORK.name); sys.path.insert(0,ARTIFACT["wheel"])
from ocp_candidate import OCPError
from ocp_routing import RoutingAdapter, ORToolsBackend
from ocp_runtime.trial import Policy, TrialGateway, digest
from ocp_runtime.http_server import create_server


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix="ocp-policy-")
        self.path=Path(self.directory.name)/"policy.sqlite"
        self.now=1800000000.0
        self.adapter=RoutingAdapter(ORToolsBackend())
        self.policy=Policy(digest(self.adapter.describe()),daily_calls=2,total_calls=3,global_reserved_ms=100000)
        self.gateway=TrialGateway(self.path,self.adapter,self.policy,clock=lambda:self.now)
        self.token=self.gateway.issue("org-a")

    def tearDown(self): self.directory.cleanup()

    def execute(self,key="a",token=None,req=None):
        return self.gateway.execute(self.token if token is None else token,request() if req is None else req,key)

    def code(self,output,code):
        validate_message(output); self.assertEqual(output["kind"],"failure"); self.assertEqual(output["error"]["code"],code)

    def rows(self):
        with sqlite3.connect(self.path) as db: return db.execute("SELECT * FROM runs").fetchall()

    def test_01_valid_real_engine_and_reserved_budget(self):
        output=self.execute(); self.assertEqual(verify_result(request(),output)["total_cost"],18)
        self.assertEqual(len(self.rows()),1); self.assertEqual(self.rows()[0][5],1000)
        self.assertGreaterEqual(self.rows()[0][8],0)

    def test_02_invalid_and_internal_tokens_rejected(self):
        for token in ["internal-service-test-token","",None,"ocp_trial_"+"a"*43]:
            output=self.gateway.execute(token,request(),"a"); self.code(output,"UNAUTHORIZED")
        self.assertEqual(self.rows(),[])

    def test_03_key_revocation_blocks_replay(self):
        self.execute(); self.gateway.revoke(self.token); self.code(self.execute(),"UNAUTHORIZED")

    def test_04_expiry_blocks_new_and_replay(self):
        self.execute(); self.now+=self.policy.lifetime_seconds
        self.code(self.execute(),"TRIAL_EXPIRED")
        with self.assertRaises(OCPError): self.gateway.issue("org-a")

    def test_05_daily_quota(self):
        self.execute("a"); self.execute("b"); self.code(self.execute("c"),"QUOTA_EXCEEDED")
        self.assertEqual(len(self.rows()),2)

    def test_06_key_rotation_keeps_organization_quota(self):
        self.execute("a"); self.execute("b"); replacement=self.gateway.issue("org-a")
        self.code(self.execute("c",replacement),"QUOTA_EXCEEDED")

    def test_07_day_rollover_keeps_lifetime_quota(self):
        self.execute("a"); self.execute("b"); self.now+=86400
        self.assertEqual(self.execute("c")["kind"],"result")
        self.code(self.execute("d"),"QUOTA_EXCEEDED")

    def test_08_replay_is_one_execution(self):
        calls=[]; execute=self.adapter.execute
        def tracked(req): calls.append(1); return execute(req)
        self.adapter.execute=tracked
        first=self.execute(); self.assertEqual(first,self.execute()); self.assertEqual(len(calls),1)
        self.assertEqual(len(self.rows()),1)

    def test_09_idempotency_conflict(self):
        self.execute(); req=request(); req["budget"]["time_limit_ms"]=999
        self.code(self.execute(req=req),"IDEMPOTENCY_CONFLICT")

    def test_10_concurrent_duplicates_single_dispatch(self):
        entered,release=threading.Event(),threading.Event(); execute=self.adapter.execute; calls=[]
        def blocked(req): calls.append(1); entered.set(); release.wait(10); return execute(req)
        self.adapter.execute=blocked
        with ThreadPoolExecutor(max_workers=8) as pool:
            first=pool.submit(self.execute)
            try:
                self.assertTrue(entered.wait(5))
                values=list(pool.map(lambda _:self.execute(),range(6)))
                for value in values: self.code(value,"EXECUTION_UNCERTAIN")
                self.code(self.execute("other"),"CONCURRENCY_LIMIT")
            finally: release.set()
            self.assertEqual(first.result()["kind"],"result")
        self.assertEqual(len(calls),1); self.assertEqual(len(self.rows()),1)

    def test_11_owner_lookup_isolated(self):
        self.execute(); other=self.gateway.issue("org-b")
        with self.assertRaises(OCPError) as error: self.gateway.lookup(other,"a")
        self.assertEqual(error.exception.code,"NOT_FOUND")
        self.assertEqual(self.gateway.lookup(self.token,"a")["kind"],"result")

    def test_12_untrusted_tenant_in_body_rejected(self):
        req=request(); req["tenant"]="org-b"
        self.assertEqual(self.execute(req=req)["kind"],"failure"); self.assertEqual(self.rows(),[])

    def test_13_single_vehicle_trial_rejected(self):
        req=request(); req["input"]["vehicles"]=[{"id":"single","capacity":4}]
        self.code(self.execute(req=req),"ENTITLEMENT_EXCEEDED")

    def test_14_budget_and_function_entitlement(self):
        req=request(); req["budget"]["time_limit_ms"]=5001
        self.code(self.execute(req=req),"LIMIT_EXCEEDED")
        req=request(); req["configuration"]["objectives"][0]["weight"]=2
        self.code(self.execute(req=req),"UNSUPPORTED_CONFIGURATION")
        self.assertEqual(self.rows(),[])

    def test_15_global_budget_shared_across_principals(self):
        policy=replace(self.policy,global_reserved_ms=1000)
        other_path=Path(self.directory.name)/"limited.sqlite"
        gateway=TrialGateway(other_path,self.adapter,policy,clock=lambda:self.now)
        one,two=gateway.issue("a"),gateway.issue("b")
        gateway.execute(one,request(),"one")
        self.code(gateway.execute(two,request(),"two"),"COST_LIMIT")

    def test_16_catalog_change_fails_closed(self):
        describe=self.adapter.describe
        def changed():
            value=describe(); value["limitations"].append("changed"); return value
        self.adapter.describe=changed
        self.code(self.execute(),"CATALOG_CHANGED"); self.assertEqual(self.rows(),[])

    def test_17_policy_change_cannot_reset_database(self):
        with self.assertRaises(ValueError): TrialGateway(self.path,self.adapter,replace(self.policy,daily_calls=100))

    def test_18_restart_preserves_replay_and_quota(self):
        value=self.execute(); self.gateway=TrialGateway(self.path,self.adapter,self.policy,clock=lambda:self.now)
        self.assertEqual(self.execute(),value); self.assertEqual(len(self.rows()),1)

    def test_19_orphan_reservation_never_auto_retried(self):
        self.gateway._reserve(self.token,request(),"a")  # Inject crash after durable reservation, before response.
        self.gateway=TrialGateway(self.path,self.adapter,self.policy,clock=lambda:self.now)
        self.code(self.execute(),"EXECUTION_UNCERTAIN"); self.code(self.execute("b"),"CONCURRENCY_LIMIT")

    def test_20_engine_failure_charged_once_and_sanitized(self):
        def crash(req): raise RuntimeError("test-upstream-token-do-not-return")
        self.adapter.execute=crash
        value=self.execute(); self.code(value,"EXECUTION_UNCERTAIN")
        self.assertNotIn("test-upstream-token",json.dumps(value))
        self.assertEqual(value,self.execute()); self.assertEqual(len(self.rows()),1)
        self.code(self.execute("fresh-id"),"CONCURRENCY_LIMIT")

    def test_21_plaintext_token_not_persisted(self):
        self.execute(); self.assertNotIn(self.token.encode(),self.path.read_bytes())
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_22_result_retention_preserves_accounting(self):
        self.execute(); self.now+=self.policy.result_retention_seconds+1
        self.gateway.purge_results(); self.assertIsNone(self.rows()[0][7])
        self.code(self.execute(),"RESULT_EXPIRED"); self.assertEqual(len(self.rows()),1)

    def test_23_public_projection_separates_catalog_and_policy(self):
        value=self.gateway.dispatch("describe",token=self.token); validate_message(value)
        self.assertEqual(value["extensions"][0]["value"]["source_catalog_sha256"],self.policy.catalog_sha256)
        self.assertNotEqual(digest(value),self.policy.catalog_sha256)

    def test_24_missing_idempotency_key(self):
        self.code(self.execute(key=None),"IDEMPOTENCY_KEY_REQUIRED"); self.assertEqual(self.rows(),[])

    def test_25_principal_revocation_all_keys(self):
        another=self.gateway.issue("org-a"); self.gateway.revoke_principal("org-a")
        for token in [self.token,another]: self.code(self.execute(token=token),"UNAUTHORIZED")

    def test_26_actual_http_auth_and_idempotency(self):
        server=create_server(self.adapter,service=self.gateway)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        def call(token=None,tenant=None):
            connection=HTTPConnection("127.0.0.1",server.server_port,timeout=10)
            headers={"Content-Type":"application/json","Idempotency-Key":"http-test"}
            if token: headers["Authorization"]="Bearer "+token
            if tenant: headers["X-Tenant-ID"]=tenant
            connection.request("POST","/v1/execute",body=json.dumps(request()),headers=headers)
            response=connection.getresponse(); result=json.loads(response.read()); connection.close(); return result
        try:
            self.code(call(),"UNAUTHORIZED")
            self.code(call("internal-service-test-token"),"UNAUTHORIZED")
            value=call(self.token,"org-b")
            self.assertEqual(verify_result(request(),value)["total_cost"],18)
            self.assertEqual(value,call(self.token)); self.assertEqual(len(self.rows()),1)
            self.assertEqual(self.rows()[0][0],"org-a")
        finally: server.shutdown(); server.server_close(); thread.join()

    def test_27_daily_and_total_compute_budgets(self):
        for field in ["daily_reserved_ms","total_reserved_ms"]:
            gateway=TrialGateway(Path(self.directory.name)/(field+".sqlite"),self.adapter,replace(self.policy,**{field:1000}),clock=lambda:self.now)
            token=gateway.issue("org"); gateway.execute(token,request(),"a")
            self.code(gateway.execute(token,request(),"b"),"COST_LIMIT")

    def test_28_eval_and_cancel_boundary(self):
        self.code(self.gateway.dispatch("evaluate",{"request":request(),"solution":FIXTURE["witness"]},token="invalid"),"UNAUTHORIZED")
        value=self.gateway.dispatch("evaluate",{"request":request(),"solution":FIXTURE["witness"]},token=self.token)
        self.assertEqual(value["kind"],"evaluation")
        self.code(self.gateway.dispatch("cancel",{},token=self.token),"UNSUPPORTED_OPERATION")


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(PolicyTests))
        passed=result.wasSuccessful() and result.testsRun>=28 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
                          "artifact_sha256":ARTIFACT["sha256"],"versions":{"policy":"0.1.0-local-candidate","engine":"ortools@9.15.6755"},
                          "scope":"Local SQLite policy and loopback auth with real reference solver; injected clocks/crash/concurrency. No real identity issuer, Omelet API, monetary billing or distributed deployment"}))
    finally: WORK.cleanup()
    sys.exit(0 if passed else 1)
