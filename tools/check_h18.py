"""Real main-based catalog + frozen installed Foundry consumers; no external trial claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import unittest
import uuid

from check_h15 import ARTIFACT, FIXTURE, request, WORK
from conformance.coordinates import verify_result
from ocp_candidate import OCPError
from ocp_routing.foundry import FoundryBackend, FoundryCoordinatesAdapter
from ocp_runtime.trial import Policy, TrialGateway, digest
from ocp_runtime.http_server import create_server
from live_foundry import ROOT, backend, settings

CONFIG_PATH=ROOT/".private/foundry-main-compatibility/consumer-settings.json"
LEGACY_SETTINGS=ROOT/".private/local-foundry-api/adapter-settings.json"


def consumer_identity():
    value=json.loads(CONFIG_PATH.read_text())
    if value["repository"]!="omelet-ai/oi-foundry": raise RuntimeError("Wrong consumer repository")
    checkout=Path(value["checkout"])
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=checkout,text=True).strip()
    if head!=value["head"]: raise RuntimeError("Consumer head changed")
    # Verify the reviewed sources, including uncommitted tracked changes.
    subprocess.run(["git","diff","--exit-code","HEAD","--","shared/ocp-contracts/ocp-candidate-consumer",
                    "verticals/tms/application-builder/backend/src/routing-curation-client.ts",
                    value["consumer_probe"]],cwd=checkout,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    artifact=Path(value["package"])
    if artifact.is_symlink() or hashlib.sha256(artifact.read_bytes()).hexdigest()!=value["package_sha256"]:
        raise RuntimeError("Installed consumer artifact changed")
    return value


CONFIG=consumer_identity()
DIRECTORY=Path(WORK.name)
NODE=Path(CONFIG["node"])
ENV={"PATH":str(NODE.parent)+os.pathsep+os.defpath,"HOME":str(DIRECTORY),"TMPDIR":"/private/tmp",
     "npm_config_cache":CONFIG["npm_cache"],"npm_config_update_notifier":"false"}
INSTALLED=DIRECTORY/"installed-consumer";INSTALLED.mkdir()
shutil.copy2(CONFIG["package"],INSTALLED/"consumer.tgz")
(INSTALLED/"package.json").write_text(json.dumps({"name":"private-consumer-check","version":"0.0.0","private":True,
    "type":"module","dependencies":{"@omelet/ocp-candidate-consumer":"file:consumer.tgz"}}))


def command(argv, cwd, env=ENV):
    result=subprocess.run(list(map(str,argv)),cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
    if result.returncode:
        detail=result.stderr
        if globals().get("TOKEN"): detail=detail.replace(TOKEN,"[redacted]")
        raise RuntimeError("Consumer verification command failed; exit="+str(result.returncode)+"\n"+detail[-1800:])
    return result.stdout


command([NODE.parent/"npm","install","--offline","--ignore-scripts","--no-audit","--no-fund"],INSTALLED)
(INSTALLED/"probe.mjs").write_text('''
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {CoordinateCandidateClient} from '@omelet/ocp-candidate-consumer';
const [configPath,inputPath,outputPath]=process.argv.slice(2);
const config=JSON.parse(readFileSync(configPath,'utf8'));
const client=await CoordinateCandidateClient.connect(config);
await client.resolve();
const request=client.request(JSON.parse(readFileSync(inputPath,'utf8')),randomUUID(),1000);
const outcome=await client.execute(request);
assert.equal(outcome.result.status,'feasible');
assert.equal(outcome.result.metrics[0].value,11358);
assert.deepEqual(await client.execute(request),outcome);
await assert.rejects(CoordinateCandidateClient.connect({...config,capabilitySha256:'0'.repeat(64)}));
await assert.rejects(CoordinateCandidateClient.connect({...config,token:'invalid-canary'}));
assert.ok(!JSON.stringify(outcome).includes(config.token));
writeFileSync(outputPath,JSON.stringify({request,...outcome}),{mode:0o600});
console.log(JSON.stringify({installed:true,profile:outcome.result.domain_profile,status:outcome.result.status}));
''')
(DIRECTORY/"input.json").write_text(json.dumps(FIXTURE["input"]))

MAIN=backend();LEGACY=backend(LEGACY_SETTINGS)
ADAPTER=FoundryCoordinatesAdapter(MAIN)
GATEWAY=TrialGateway(DIRECTORY/"trial.sqlite",ADAPTER,Policy(digest(ADAPTER.describe()),total_calls=4,global_reserved_ms=4000))
TOKEN=GATEWAY.issue("main-consumers-"+uuid.uuid4().hex)
SERVER=create_server(ADAPTER,service=GATEWAY)
THREAD=threading.Thread(target=SERVER.serve_forever,daemon=True);THREAD.start()
CONNECTION=DIRECTORY/"connection.json"
descriptor=GATEWAY.dispatch("describe",token=TOKEN)
CONNECTION.write_text(json.dumps({"origin":"http://127.0.0.1:"+str(SERVER.server_port),"token":TOKEN,
                                 "capabilitySha256":digest(descriptor)}))
CONNECTION.chmod(0o600)
EVIDENCE={}


def submissions(upstream):
    return sum(c["method"]=="POST" and c["path"]=="/jobs" for c in upstream.calls)


class MainCompatibilityTests(unittest.TestCase):
    def test_01_main_engine_is_unchanged_from_recorded_base(self):
        value,_,_=settings()
        self.assertEqual(value["unchanged_engine_base"],CONFIG["engine_base"])
        self.assertEqual(MAIN.catalog_version,"1.3.0")
        self.assertEqual(LEGACY.catalog_version,"1.4.0")

    def test_02_selected_native_meanings_are_equal(self):
        a=MAIN.check_catalog();b=LEGACY.check_catalog()
        self.assertNotEqual(a["catalogDigest"],b["catalogDigest"])
        for area,selected in (("objectives","minimize_total_route_cost"),("constraints","weight_capacity")):
            one=[v for v in a[area] if v["id"]==selected]
            two=[v for v in b[area] if v["id"]==selected]
            self.assertEqual(len(one),1);self.assertEqual(one,two)
            one=[v for v in a["evaluation"][area] if v["capabilityId"]==selected]
            two=[v for v in b["evaluation"][area] if v["capabilityId"]==selected]
            self.assertEqual(len(one),1);self.assertEqual(one,two)
        self.assertEqual(a["solverParameters"],b["solverParameters"])

    def test_03_installed_private_consumer_main_solve_evaluate_replay(self):
        output=DIRECTORY/"installed.json";before=submissions(MAIN)
        command([NODE,"probe.mjs",CONNECTION,DIRECTORY/"input.json",output],INSTALLED)
        result=json.loads(output.read_text())
        self.assertEqual(verify_result(result["request"],result["result"])["total_cost"],11358)
        self.assertEqual(result["evaluation"]["metrics"][0]["value"],11358)
        self.assertEqual(submissions(MAIN)-before,1)
        EVIDENCE["installed_foundry_consumer"]=result

    def test_04_existing_tms_resolver_and_shared_client(self):
        output=DIRECTORY/"tms.json";before=submissions(MAIN)
        probe=Path(CONFIG["checkout"])/CONFIG["consumer_probe"]
        command([NODE,"--import","tsx",probe],probe.parent.parent,
                dict(ENV,OCP_CANDIDATE_LIVE_CONFIG=str(CONNECTION),OCP_CANDIDATE_LIVE_EVIDENCE=str(output)))
        result=json.loads(output.read_text())
        self.assertEqual(verify_result(result["request"],result["result"])["total_cost"],11358)
        self.assertEqual(submissions(MAIN)-before,1)
        EVIDENCE["tms"]=result

    def test_05_original_default_1_4_path_still_solves(self):
        adapter=FoundryCoordinatesAdapter(LEGACY)
        req=request(adapter,"legacy-"+uuid.uuid4().hex)
        result=adapter.execute_scoped(req,"compatibility-legacy",uuid.uuid4().hex)
        self.assertEqual(verify_result(req,result)["total_cost"],11358)
        self.assertEqual(result["status"],"feasible")
        EVIDENCE["legacy"]={"request":req,"result":result}

    def test_06_default_does_not_guess_live_main_version(self):
        value,secret,_=settings();before=submissions(MAIN)
        with self.assertRaises(OCPError) as error:
            FoundryBackend(value["base_url"],secret,value["catalog_digest"],value["catalog_document_sha256"])
        self.assertEqual(error.exception.code,"UPSTREAM_VERSION_MISMATCH")
        self.assertEqual(submissions(MAIN),before)

    def test_07_new_path_keeps_foreign_profiles_and_objectives_rejected(self):
        before=submissions(MAIN)
        req=request(ADAPTER);req["configuration"]["objectives"][0]["weight"]=2
        response=GATEWAY.execute(TOKEN,req,"invalid-weight")
        self.assertEqual(response["kind"],"failure")
        req=request(ADAPTER);req["domain_profile"]={"id":"routing.basic","version":"0.1.0"}
        self.assertEqual(GATEWAY.execute(TOKEN,req,"invalid-profile")["kind"],"failure")
        self.assertEqual(submissions(MAIN),before)

    def test_08_pins_and_source_identity_hold_after_calls(self):
        settings();settings(LEGACY_SETTINGS);consumer_identity()
        self.assertEqual(MAIN.check_catalog()["catalogVersion"],"1.3.0")
        self.assertNotIn(TOKEN,json.dumps(EVIDENCE))
        self.assertEqual(len(EVIDENCE),3)


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MainCompatibilityTests))
        passed=result.wasSuccessful() and result.testsRun==8 and not result.skipped
        report={"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),
                "errors":len(result.errors),"skipped":len(result.skipped),"artifact_sha256":ARTIFACT["sha256"],
                "versions":{"catalogs":["1.3.0","1.4.0"],"consumer_head":CONFIG["head"],
                            "consumer_package_sha256":CONFIG["package_sha256"]},
                "scope":"Real loopback main-based engine, offline installed Foundry public client and existing TMS resolver; legacy default smoke. No external trial, main merge, Studio browser or H10 promotion"}
        root=ROOT/".harness/work/main-catalog-compatibility";root.mkdir(exist_ok=True,parents=True)
        (root/(uuid.uuid4().hex+".json")).write_text(json.dumps({"report":report,"evidence":EVIDENCE},indent=2))
        print(json.dumps(report))
    finally:
        SERVER.shutdown();SERVER.server_close();THREAD.join();WORK.cleanup()
    sys.exit(0 if passed else 1)
