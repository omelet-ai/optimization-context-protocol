"""Installed App A/B x real reference/Foundry on the same coordinates profile."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import unittest
import uuid

from check_h15 import ARTIFACT, FIXTURE, request, reference, WORK
from build_typescript import build as build_ts, command, NODE, NPM
from isolated_candidate import install
from conformance.coordinates import verify_result
from ocp_routing.foundry import FoundryCoordinatesAdapter
from ocp_runtime.trial import Policy, TrialGateway, digest
from ocp_runtime.http_server import create_server
from live_foundry import backend, settings, ROOT
from safe_test_result import DiagnosticResult

DIRECTORY=Path(WORK.name)
PYTHON,ENV=install(DIRECTORY,ARTIFACT["wheel"],"reference")
TS=build_ts(DIRECTORY/"ts-dist")
APP=DIRECTORY/"app-b";APP.mkdir()
(APP/"package.json").write_text(json.dumps({"name":"private-coordinate-consumer","version":"0.0.0","private":True,
    "dependencies":{"ocp-candidate":"file:"+TS["tarball"]},"devDependencies":{"typescript":"7.0.2","@types/node":"24.10.0"}}))
command([NPM,"install","--offline","--ignore-scripts","--no-audit","--no-fund"],APP)
shutil.copy2(ROOT/"examples/app-b/main.ts",APP/"main.ts")
command([NODE,APP/"node_modules/typescript/bin/tsc","--types","node","--target","ES2022","--module","Node16","--strict","--skipLibCheck","--outDir","dist","main.ts"],APP)
shutil.copy2(ROOT/"examples/app-a/main.py",DIRECTORY/"app-a.py")
(DIRECTORY/"input.json").write_text(json.dumps(FIXTURE["input"]))
REFERENCE=reference()
UPSTREAM=backend();OMELET=FoundryCoordinatesAdapter(UPSTREAM)
GATEWAY=TrialGateway(DIRECTORY/"trial.sqlite",OMELET,Policy(digest(OMELET.describe()),total_calls=4,global_reserved_ms=4000))
TOKEN=GATEWAY.issue("four-combinations-"+uuid.uuid4().hex)
SERVERS=[create_server(REFERENCE),create_server(OMELET,service=GATEWAY)]
THREADS=[threading.Thread(target=s.serve_forever,daemon=True) for s in SERVERS]
for thread in THREADS:thread.start()
URLS=["http://127.0.0.1:"+str(s.server_port) for s in SERVERS]
OUTPUTS=[]


def run(argv, env, cwd):
    result=subprocess.run([str(x) for x in argv],env=env,cwd=cwd,capture_output=True,text=True,timeout=20)
    if result.returncode: raise AssertionError("Consumer failed without a successful response: "+result.stderr[-1000:])
    return json.loads(result.stdout)


class MatrixTests(unittest.TestCase):
    def verify(self, result, adapter, rid):
        verified=verify_result(request(adapter,rid),result)
        self.assertEqual(verified["total_cost"],11358)
        self.assertEqual(result["domain_profile"],{"id":"routing.coordinates","version":"0.1.0"})
        OUTPUTS.append({"app":rid,"engine":result["provenance"]["engine"],"result":result})

    def test_01_app_a_local_reference(self):
        result=run([PYTHON,"-I","-B","app-a.py","--profile","coordinates","--input","input.json"],ENV,DIRECTORY)
        self.verify(result,REFERENCE,"app-a")

    def test_02_app_b_http_reference(self):
        result=run([NODE,APP/"dist/main.js",URLS[0],DIRECTORY/"input.json","--request-id","app-b"],dict(ENV,PATH=str(NODE.parent)+os.pathsep+os.defpath),APP)
        self.verify(result,REFERENCE,"app-b")

    def test_03_app_a_http_trial_real_foundry(self):
        result=run([PYTHON,"-I","-B","app-a.py","--endpoint",URLS[1],"--input","input.json"],dict(ENV,OCP_TRIAL_TOKEN=TOKEN),DIRECTORY)
        self.verify(result,OMELET,"app-a")

    def test_04_app_b_http_trial_real_foundry(self):
        result=run([NODE,APP/"dist/main.js",URLS[1],DIRECTORY/"input.json","--request-id","app-b"],dict(ENV,PATH=str(NODE.parent)+os.pathsep+os.defpath,OCP_TRIAL_TOKEN=TOKEN),APP)
        self.verify(result,OMELET,"app-b")

    def test_05_installed_module_origin(self):
        value=run([PYTHON,"-I","-B","-c","import json,ocp_candidate,ocp_routing;print(json.dumps([ocp_candidate.__file__,ocp_routing.__file__]))"],ENV,DIRECTORY)
        for path in value:self.assertTrue(Path(path).is_relative_to(DIRECTORY/"venv"))

    def test_06_typescript_trial_retry_is_single_upstream_execution(self):
        # Repeat the same App B request identity: replay must not solve or charge twice.
        before=len([c for c in UPSTREAM.calls if c["path"]=="/jobs" and c["method"]=="POST"])
        result=run([NODE,APP/"dist/main.js",URLS[1],DIRECTORY/"input.json","--request-id","app-b"],dict(ENV,PATH=str(NODE.parent)+os.pathsep+os.defpath,OCP_TRIAL_TOKEN=TOKEN),APP)
        self.assertEqual(result["kind"],"result")
        self.assertEqual(len([c for c in UPSTREAM.calls if c["path"]=="/jobs" and c["method"]=="POST"]),before)

    def test_07_unauthorized_typescript_client_is_rejected(self):
        result=subprocess.run([str(NODE),str(APP/"dist/main.js"),URLS[1],str(DIRECTORY/"input.json"),"--request-id","unauthorized"],env=ENV,cwd=APP,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0);self.assertNotIn(TOKEN,result.stdout+result.stderr)


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(MatrixTests))
        settings()
        passed=result.wasSuccessful() and result.testsRun>=7 and len(OUTPUTS)==4 and not result.skipped
        report={"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),"failure_diagnostics":result.diagnostics,
            "artifact_sha256":ARTIFACT["sha256"],"versions":{"typescript_tarball_sha256":TS["sha256"],"profile":"routing.coordinates@0.1.0","catalog":UPSTREAM.catalog_version,"combinations":4},
            "scope":"Clean installed Python/TypeScript apps x actual OR-Tools/loopback Foundry; same coordinate contract and independent evaluation; no external human acceptance or hosted release"}
        evidence=ROOT/".harness/work/coordinate-app-matrix";evidence.mkdir(parents=True,exist_ok=True)
        (evidence/(uuid.uuid4().hex+".json")).write_text(json.dumps({"report":report,"outputs":OUTPUTS},indent=2))
        print(json.dumps(report))
    finally:
        for server,thread in zip(SERVERS,THREADS):server.shutdown();server.server_close();thread.join()
        WORK.cleanup()
    sys.exit(0 if passed else 1)
