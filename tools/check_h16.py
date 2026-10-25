"""Real local Foundry through trial keys and HTTP; no substituted solver outcomes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from http.client import HTTPConnection
import json
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import uuid

from check_h15 import ARTIFACT, FIXTURE, request, WORK
from conformance.coordinates import verify_result
from conformance.core_contract import validate_message
from ocp_candidate import Client, OCPError
from ocp_candidate.http_adapter import HTTPAdapter
from ocp_routing.foundry import FoundryCoordinatesAdapter, FoundryBackend
from ocp_runtime.trial import TrialGateway, Policy, digest
from ocp_runtime.http_server import create_server
from live_foundry import backend, settings, ROOT

def idem(value): return hashlib.sha256(value.encode()).hexdigest()

UPSTREAM=backend()
ADAPTER=FoundryCoordinatesAdapter(UPSTREAM)


class LiveTrialTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix="ocp-h16-policy-")
        self.path=Path(self.directory.name)/"trial.sqlite"
        self.now=1800000000.
        self.policy=Policy(digest(ADAPTER.describe()),daily_calls=2,total_calls=3,global_reserved_ms=10000)
        self.gateway=TrialGateway(self.path,ADAPTER,self.policy,clock=lambda:self.now)
        self.owner="local-"+uuid.uuid4().hex
        self.token=self.gateway.issue(self.owner)
        self.server=create_server(ADAPTER,service=self.gateway)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.endpoint="http://127.0.0.1:"+str(self.server.server_port)
        self.client=Client(HTTPAdapter(self.endpoint,token=self.token))
        self.initial=len([c for c in UPSTREAM.calls if c["method"]=="POST" and c["path"]=="/jobs"])

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.directory.cleanup()

    def count(self): return len([c for c in UPSTREAM.calls if c["method"]=="POST" and c["path"]=="/jobs"])-self.initial
    def req(self,rid="live",budget=1000): return request(ADAPTER,rid,budget)
    def run_job(self,rid="live",budget=1000):
        result=self.client.execute(deepcopy(FIXTURE["input"]),request_id=rid,time_limit_ms=budget)
        verify_result(self.req(rid,budget),result)
        return result
    def code(self,value,code):
        validate_message(value);self.assertEqual(value["kind"],"failure");self.assertEqual(value["error"]["code"],code)
    def rows(self):
        with sqlite3.connect(self.path) as db:return db.execute("SELECT owner,idem,reserved_ms,state,response FROM runs").fetchall()

    def test_01_real_key_to_engine_and_independent_evaluation(self):
        result=self.run_job(rid="좌표\n검증",budget=1999)
        self.assertEqual(result["status"],"feasible")
        self.assertEqual(result["metrics"][0]["value"],11358)
        self.assertEqual(result["provenance"]["engine"]["id"],"omelet.standard-vrp")
        self.assertEqual(self.count(),1);self.assertEqual(self.rows()[0][2],1999)
        self.assertEqual([c for c in UPSTREAM.calls if c["path"]=="/jobs"][-1]["solver_seconds"],1)
        result2=self.gateway.dispatch("evaluate",{"request":self.req("좌표\n검증",budget=1999),"solution":result["solution"]},token=self.token)
        self.assertEqual(result2["metrics"][0]["value"],11358)

    def test_02_missing_internal_and_unknown_tokens_rejected(self):
        _,internal,_=settings()
        for token in [None,internal,"ocp_trial_"+"z"*43]:
            self.code(self.gateway.execute(token,self.req(),"a"),"UNAUTHORIZED")
        self.assertEqual(self.count(),0);self.assertEqual(self.rows(),[])

    def test_03_feature_size_budget_and_forged_identity_before_submit(self):
        requests=[]
        for count in [1,4]:
            req=self.req();req["input"]["vehicles"]=[{"id":"v"+str(i),"capacity":100} for i in range(count)];requests.append(req)
        req=self.req();req["input"]["visits"]=[dict(deepcopy(req["input"]["visits"][0]),id="v"+str(i)) for i in range(21)];requests.append(req)
        req=self.req(budget=5001);requests.append(req)
        req=self.req();req["configuration"]["objectives"][0]["weight"]=2;requests.append(req)
        req=self.req();req["tenant"]="forged";requests.append(req)
        for req in requests:self.assertEqual(self.gateway.execute(self.token,req,"rejected")["kind"],"failure")
        self.assertEqual(self.count(),0);self.assertEqual(self.rows(),[])

    def test_04_real_concurrent_duplicate_and_global_slot(self):
        other=self.gateway.issue("other-"+self.owner)
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(self.run_job)
            end=time.monotonic()+5
            while not self.rows() and time.monotonic()<end:time.sleep(.01)
            self.assertEqual(self.rows()[0][3],"running")
            self.code(self.gateway.execute(self.token,self.req(),idem("live")),"EXECUTION_UNCERTAIN")
            self.code(self.gateway.execute(other,self.req(),"different"),"CONCURRENCY_LIMIT")
            result=future.result(timeout=12)
        self.assertEqual(self.gateway.execute(self.token,self.req(),idem("live")),result)
        self.assertEqual(self.count(),1)

    def test_05_rotation_and_daily_quota_use_same_owner(self):
        self.run_job("a");self.run_job("b")
        replacement=self.gateway.issue(self.owner)
        self.code(self.gateway.execute(replacement,self.req("c"),"c"),"QUOTA_EXCEEDED")
        self.assertEqual(self.count(),2)

    def test_06_revoke_and_expire_replay(self):
        self.run_job()
        replacement=self.gateway.issue(self.owner)
        self.gateway.revoke(self.token)
        self.code(self.gateway.execute(self.token,self.req(),idem("live")),"UNAUTHORIZED")
        self.now+=self.policy.lifetime_seconds
        self.code(self.gateway.execute(replacement,self.req(),idem("live")),"TRIAL_EXPIRED")
        self.assertEqual(self.count(),1)

    def test_07_compute_reservation_rejects_before_submit(self):
        for field in ["daily_reserved_ms","total_reserved_ms","global_reserved_ms"]:
            gateway=TrialGateway(Path(self.directory.name)/(field+".sqlite"),ADAPTER,replace(self.policy,**{field:1000}))
            token=gateway.issue("limited")
            self.code(gateway.execute(token,self.req(budget=2000),"over"),"COST_LIMIT")
        self.assertEqual(self.count(),0)

    def test_08_restart_replay_and_other_owner_lookup(self):
        result=self.run_job()
        restarted=TrialGateway(self.path,ADAPTER,self.policy,clock=lambda:self.now)
        self.assertEqual(restarted.execute(self.token,self.req(),idem("live")),result)
        token=restarted.issue("other-"+self.owner)
        with self.assertRaises(OCPError) as error:restarted.lookup(token,idem("live"))
        self.assertEqual(error.exception.code,"NOT_FOUND");self.assertEqual(self.count(),1)

    def test_09_real_deadline_cancels_upstream_process(self):
        bounded=backend();bounded.grace_ms=0
        adapter=FoundryCoordinatesAdapter(bounded)
        gateway=TrialGateway(Path(self.directory.name)/"deadline.sqlite",adapter,Policy(digest(adapter.describe())))
        token=gateway.issue(self.owner+"-deadline")
        start=time.monotonic()
        result=gateway.execute(token,request(adapter),"deadline")
        verify_result(request(adapter),result)
        self.assertEqual(result["status"],"unknown");self.assertEqual(result["termination"],"time_limit")
        self.assertLess(time.monotonic()-start,4)
        self.assertTrue(any(c["method"]=="DELETE" and c["path"].startswith("/jobs/") for c in bounded.calls))
        self.assertTrue(any(c["status"]=="cancelled" for c in bounded.calls))

    def test_10_live_catalog_and_bad_service_credential_fail_closed(self):
        value,secret,_=settings()
        with self.assertRaises(OCPError) as error:
            FoundryBackend(value["base_url"],secret,value["catalog_digest"],"b"*64)
        self.assertEqual(error.exception.code,"CATALOG_CHANGED")
        with self.assertRaises(OCPError) as error:
            FoundryBackend(value["base_url"],"wrong-local-service-key",value["catalog_digest"],value["catalog_document_sha256"])
        self.assertEqual(error.exception.code,"UPSTREAM_AUTH_FAILED");self.assertEqual(self.count(),0)

    def test_11_http_forged_tenant_cannot_choose_upstream_owner(self):
        connection=HTTPConnection("127.0.0.1",self.server.server_port,timeout=10)
        connection.request("POST","/v1/execute",json.dumps(self.req()),headers={"Content-Type":"application/json",
            "Authorization":"Bearer "+self.token,"Idempotency-Key":"forged","X-OIP-Tenant-Id":"victim","X-Tenant-ID":"victim"})
        response=json.loads(connection.getresponse().read());connection.close()
        verify_result(self.req(),response)
        self.assertEqual(self.rows()[0][0],self.owner)
        job=[c for c in UPSTREAM.calls if c["method"]=="POST" and c["path"]=="/jobs"][-1]
        self.assertNotEqual(job["tenant"],"victim")
        with self.assertRaises(OCPError):UPSTREAM.scoped("victim","forged")._call("GET","/jobs/"+job["job_id"])

    def test_12_secret_not_exposed_or_stored_in_policy_database(self):
        _,secret,_=settings()
        descriptor=self.gateway.dispatch("describe",token=self.token)
        self.assertNotIn(secret,json.dumps(descriptor));self.assertNotIn(self.token,json.dumps(descriptor))
        self.assertNotIn(self.token.encode(),self.path.read_bytes());self.assertNotIn(secret.encode(),self.path.read_bytes())
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_13_real_maximum_trial_size_and_budget(self):
        req=self.req("boundary",5000)
        req["input"]["vehicles"].append({"id":"van-c","capacity":20})
        req["input"]["visits"]=[{"id":"point-"+str(i),"demand":1,
            "location":{"latitude":37.5+i*.0001,"longitude":127+i*.0002}} for i in range(20)]
        result=self.gateway.execute(self.token,req,"boundary")
        self.assertEqual(result.get("status"),"feasible",result)
        self.assertTrue(verify_result(req,result)["feasible"])
        self.assertEqual(self.count(),1)


if __name__=="__main__":
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(LiveTrialTests))
    settings() # Recheck external source identity after the actual calls.
    passed=result.wasSuccessful() and result.testsRun>=13 and not result.skipped
    report={"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "artifact_sha256":ARTIFACT["sha256"],"versions":{"profile":"routing.coordinates@0.1.0","catalog":"1.4.0","catalog_digest":UPSTREAM.catalog_digest},
            "scope":"Actual loopback Foundry + separate issued trial keys + durable policy and real HTTP; synthetic operator-provisioned principals, injected expiry clock; no public signup, monetary billing or external-user acceptance"}
    evidence=ROOT/".harness/work/live-trial";evidence.mkdir(parents=True,exist_ok=True)
    (evidence/(uuid.uuid4().hex+".json")).write_text(json.dumps({"report":report,"calls":UPSTREAM.calls},indent=2))
    print(json.dumps(report));WORK.cleanup();sys.exit(0 if passed else 1)
