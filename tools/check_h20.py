"""Clean installed consumer regressions for U01-U09; no external human acceptance."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

from build_invitation_kit import build
from build_typescript import NODE, NPM, command
from isolated_candidate import clean_env, install

ROOT=Path(__file__).resolve().parents[1]
WORK=tempfile.TemporaryDirectory(prefix="ocp-onboarding-")
DIRECTORY=Path(WORK.name)
KIT=DIRECTORY/"kit"
BUILT=build(KIT)
WHEEL=KIT/"ocp_candidate-0.1.0-py3-none-any.whl"
CHECKER=KIT/"ocp_conformance_candidate-0.1.0-py3-none-any.whl"
ENV=clean_env(DIRECTORY)
ENV["PATH"]=str(NODE.parent)+os.pathsep+os.defpath
WHEELHOUSE=ROOT/".harness/work/wheels"


def run(argv,cwd=KIT,env=None):
    return subprocess.run([str(x) for x in argv],cwd=cwd,env=ENV if env is None else env,capture_output=True,text=True,timeout=60)


BOOTSTRAP=DIRECTORY/"python3.12"
BOOTSTRAP.symlink_to(Path(sys._base_executable).resolve())
installed=run([BOOTSTRAP,"-B",KIT/"install.py","--venv",DIRECTORY/"client","--offline-wheelhouse",WHEELHOUSE])
if installed.returncode:raise RuntimeError(installed.stderr)
PYTHON=DIRECTORY/"client/bin/python"
BYO=DIRECTORY/"byo";BYO.mkdir()
BYOPYTHON,BYOENV=install(BYO,WHEEL,"")
check_install=run([BYOPYTHON,"-m","pip","install","--no-index","--no-compile","--find-links",WHEELHOUSE,CHECKER],env=BYOENV)
if check_install.returncode:raise RuntimeError(check_install.stderr)
command([NPM,"install","--offline","--no-save","--package-lock=false","--ignore-scripts","--no-audit","--no-fund",KIT/"ocp-candidate-0.1.0.tgz"],KIT)
command([NPM,"run","build"],KIT)
sys.path.insert(0,str(WHEEL))
sys.path.insert(0,str(ROOT))
from ocp_candidate import Client
from ocp_routing import ORToolsBackend
from ocp_routing.coordinates import CoordinatesAdapter, CoordinateLibraryBackend
from ocp_runtime.http_server import create_server
from ocp_runtime.trial_ops import InvitationGateway, InvitationPolicy, write_private_json
from ocp_runtime.trial import digest
from ocp_runtime.service import Service
from conformance.coordinates import verify_result
from mcp import Client as MCPClient, StdioServerParameters

ADAPTER=CoordinatesAdapter(CoordinateLibraryBackend(ORToolsBackend()))
GATEWAY=InvitationGateway(DIRECTORY/"quota.sqlite",ADAPTER,InvitationPolicy(digest(ADAPTER.describe())))
TOKEN=GATEWAY.issue("python-and-mcp")
TSTOKEN=GATEWAY.issue("typescript")
SERVER=create_server(ADAPTER,service=GATEWAY)
THREAD=threading.Thread(target=SERVER.serve_forever,daemon=True);THREAD.start()
URL="http://127.0.0.1:"+str(SERVER.server_port)
SESSION=KIT/"session.json"
write_private_json(SESSION,{"endpoint":URL,"token":TOKEN,"catalog_sha256":digest(GATEWAY.dispatch("describe",token=TOKEN))})
INPUT=json.loads((KIT/"input.json").read_text())


class DeveloperJourney(unittest.TestCase):
    def cli(self,*args,expected=0,env=None):
        value=run(args,env=env)
        self.assertEqual(value.returncode,expected,value.stderr+value.stdout)
        self.assertNotIn(TOKEN,value.stdout+value.stderr)
        self.assertNotIn(TSTOKEN,value.stdout+value.stderr)
        return value

    def test_01_ambiguous_input_rejected_before_contact(self):
        before=GATEWAY.summary()["calls"]
        for i,value in enumerate(['{"load_unit":"lb","load_unit":"kg"}','{"capacity":NaN}','{"broken":']):
            path=KIT/("invalid-%s.json"%i);path.write_text(value)
            result=self.cli(PYTHON,"-B","main.py","--session","missing-session.json","--input",path,"--request-id","invalid",expected=1)
            self.assertEqual(json.loads(result.stdout)["error"]["code"],"INVALID_REQUEST")
            self.assertNotIn("Traceback",result.stdout+result.stderr)
        self.assertEqual(GATEWAY.summary()["calls"],before)

    def test_02_installer_preflight_and_safe_rerun(self):
        self.cli(sys.executable,"-B","install.py","--check")
        result=self.cli(sys.executable,"-B","install.py","--venv",DIRECTORY/"client",expected=1)
        self.assertEqual(json.loads(result.stderr)["code"],"ENVIRONMENT_EXISTS")
        for i,links in enumerate([None,'https://invalid.example/wheels']):
            env=dict(ENV,PIP_NO_INDEX='true')
            if links:env['PIP_FIND_LINKS']=links
            destination=DIRECTORY/('invalid-offline-'+str(i))
            result=self.cli(BOOTSTRAP,'-B','install.py','--venv',destination,expected=1,env=env)
            self.assertEqual(json.loads(result.stderr)['code'],
                             'OFFLINE_WHEELHOUSE_INVALID' if links else 'OFFLINE_WHEELHOUSE_REQUIRED')
            self.assertFalse(destination.exists())
        empty=DIRECTORY/'empty-python-wheels';empty.mkdir()
        result=self.cli(BOOTSTRAP,'-B','install.py','--venv',DIRECTORY/'offline-missing-dependency',expected=1,
                        env=dict(ENV,PIP_NO_INDEX='1',PIP_FIND_LINKS=str(empty)))
        self.assertEqual(json.loads(result.stderr.splitlines()[-1])['code'],'INSTALL_FAILED')
        self.assertIn('Looking in links:',result.stdout)
        self.assertNotIn('Looking in indexes:',result.stdout)

    def test_03_session_diagnosis_and_recovery(self):
        before=GATEWAY.summary()["calls"]
        checks=[(KIT/"missing.json","INVITATION_NOT_FOUND"),(SESSION,"INVITATION_PERMISSIONS")]
        SESSION.chmod(0o644)
        try:
            for path,code in checks:
                result=self.cli(PYTHON,"-B","-m","ocp_runtime.trial_client","--session",path,"doctor",expected=1)
                message=json.loads(result.stderr);self.assertEqual(message["code"],code);self.assertTrue(message["hint"])
        finally:SESSION.chmod(0o600)
        bad=KIT/"broken-session.json";bad.write_text('{bad}');bad.chmod(0o600)
        result=self.cli(PYTHON,"-B","-m","ocp_runtime.trial_client","--session",bad,"doctor",expected=1)
        self.assertEqual(json.loads(result.stderr)["code"],"INVITATION_JSON_INVALID")
        self.cli(PYTHON,"-B","-m","ocp_runtime.trial_client","--session",SESSION,"doctor")
        self.assertEqual(GATEWAY.summary()["calls"],before)

    def test_04_installed_invited_example_and_replay(self):
        before=GATEWAY.summary()["calls"]
        args=[PYTHON,"-B","main.py","--session",SESSION,"--input","input.json","--request-id","invited-first"]
        first=json.loads(self.cli(*args).stdout);again=json.loads(self.cli(*args).stdout)
        self.assertEqual(first,again);self.assertEqual(first["independent_check"]["total_cost"],11358)
        self.assertEqual(GATEWAY.summary()["calls"],before+1)

    def test_05_typescript_explicit_ids_for_two_inputs_and_replay(self):
        env=dict(ENV,OCP_TRIAL_TOKEN=TSTOKEN)
        before=GATEWAY.summary()["calls"]
        self.cli(NODE,"dist/main.js",URL,"input.json",expected=2,env=env)
        self.assertEqual(GATEWAY.summary()["calls"],before)
        args=[NODE,"dist/main.js",URL,"input.json","--request-id","ts-first"]
        first=json.loads(self.cli(*args,env=env).stdout)
        self.assertEqual(first,json.loads(self.cli(*args,env=env).stdout))
        own=deepcopy(INPUT);own["visits"][0]["location"]["latitude"]+=.001
        (KIT/"own-coordinate.json").write_text(json.dumps(own))
        conflict=json.loads(self.cli(NODE,"dist/main.js",URL,"own-coordinate.json","--request-id","ts-first",env=env,expected=2).stdout)
        self.assertEqual(conflict["error"]["code"],"IDEMPOTENCY_CONFLICT")
        result=json.loads(self.cli(NODE,"dist/main.js",URL,"own-coordinate.json","--request-id","ts-second",env=env).stdout)
        req=Client(ADAPTER).request(own,request_id="ts-second")
        verify_result(req,result)
        self.assertEqual(GATEWAY.summary()["calls"],before+2)

    def test_06_typescript_auth_error_is_actionable(self):
        result=self.cli(NODE,"dist/main.js",URL,"input.json","--request-id","unauthorized",expected=2)
        error=json.loads(result.stderr);self.assertEqual(error["code"],"UNAUTHORIZED");self.assertIn("inviter",error["hint"])

    def test_07_typescript_evaluate_without_spend(self):
        # Reuse the existing job, then call the new public evaluation method.
        script='''const fs=require('node:fs');const {Client}=require('ocp-candidate');
(async()=>{const c=await Client.connect(process.argv[2],{token:process.env.OCP_TRIAL_TOKEN});const r=c.request(JSON.parse(fs.readFileSync('input.json')),undefined,'ts-first');
const s=await c.execute(r);const e=await c.evaluate(r,s.solution);console.log(JSON.stringify(e));})().catch(()=>process.exitCode=1);'''
        (KIT/"evaluate.cjs").write_text(script)
        before=GATEWAY.summary()["calls"]
        value=json.loads(self.cli(NODE,"evaluate.cjs",URL,env=dict(ENV,OCP_TRIAL_TOKEN=TSTOKEN)).stdout)
        self.assertEqual(value["kind"],"evaluation");self.assertEqual(value["metrics"][0]["value"],11358)
        self.assertEqual(GATEWAY.summary()["calls"],before)

    def test_08_evaluate_rejects_response_identity_drift(self):
        class Drift:
            def dispatch(self,operation,payload=None,**kwargs):
                result=Service(ADAPTER).dispatch(operation,payload,**kwargs)
                if operation=="evaluate":result["request_id"]="foreign"
                return result
        server=create_server(ADAPTER,service=Drift());thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        script='''const fs=require('node:fs');const {Client}=require('ocp-candidate');
(async()=>{const c=await Client.connect(process.argv[2]);const r=c.request(JSON.parse(fs.readFileSync('input.json')),undefined,'drift');const s=await c.execute(r);
try{await c.evaluate(r,s.solution);process.exitCode=1}catch(e){if(e.message!=='INVALID_RESPONSE')throw e;console.log('rejected')}})().catch(()=>process.exitCode=1);'''
        (KIT/"drift.cjs").write_text(script)
        try:self.cli(NODE,"drift.cjs","http://127.0.0.1:"+str(server.server_port))
        finally:server.shutdown();server.server_close();thread.join()

    def test_09_byo_without_ortools_or_mcp(self):
        self.cli(BYOPYTHON,"-I","-B","-c","import importlib.util;assert importlib.util.find_spec('ortools') is None;assert importlib.util.find_spec('mcp') is None",env=BYOENV)
        result=json.loads(self.cli(BYOPYTHON,"-B","byo_library.py","basic-input.json","--trace","byo-trace.json",env=BYOENV).stdout)
        self.assertEqual(result["status"],"feasible")
        self.cli(BYOPYTHON,"-B","export_transcript.py","--trace","byo-trace.json","--artifact","byo_library.py","--out","byo-transcript.json",env=BYOENV)
        report=json.loads(self.cli(BYOPYTHON,"-I","-B","-m","conformance.runner","--bundle","byo-transcript.json","--artifact","byo_library.py",env=BYOENV).stdout)
        self.assertEqual(report["status"],"PASS")
        bundle=json.loads((KIT/"byo-transcript.json").read_text());bundle["implementation"]={"id":"wrong-engine","version":"0.1.0"}
        (KIT/"wrong-transcript.json").write_text(json.dumps(bundle))
        self.cli(BYOPYTHON,"-I","-B","-m","conformance.runner","--bundle","wrong-transcript.json","--artifact","byo_library.py",expected=1,env=BYOENV)

    def test_10_byo_failure_exit(self):
        problem=json.loads((KIT/"basic-input.json").read_text());problem["load_unit"]="lb"
        (KIT/"bad-basic.json").write_text(json.dumps(problem))
        result=self.cli(BYOPYTHON,"-B","byo_library.py","bad-basic.json",expected=2,env=BYOENV)
        self.assertEqual(json.loads(result.stdout)["kind"],"failure")

    def test_11_own_app_and_trace(self):
        result=json.loads(self.cli(PYTHON,"-B","own_app.py","--session",SESSION,"--input","input.json","--request-id","own-app","--trace","app-trace.json").stdout)
        self.assertEqual(result["independent_check"]["total_cost"],11358)
        self.assertEqual(result["metrics"][0]["status"],"evaluated")
        self.assertIsInstance(result["evaluation"],dict)

    def test_12_mcp_resource_to_solve_without_internal_contract_knowledge(self):
        async def scenario():
            before=GATEWAY.summary()["calls"]
            async with MCPClient(StdioServerParameters(command=str(PYTHON),args=["-I","-B","-m","ocp_runtime.trial_client","--session",str(SESSION),"mcp"],env=ENV,cwd=str(KIT)),read_timeout_seconds=20) as host:
                self.assertEqual(len((await host.list_tools()).tools),5)
                resources=await host.list_resources();self.assertIn("ocp://request-guide/0.1.0",[str(r.uri) for r in resources.resources])
                content=await host.read_resource("ocp://request-guide/0.1.0")
                guide=json.loads(content.contents[0].text)
                self.assertEqual(GATEWAY.summary()["calls"],before)
                self.assertNotIn(TOKEN,json.dumps(guide))
                req=guide["request_template"];req["input"]=INPUT;req["request_id"]="mcp-guide"
                from jsonschema import Draft202012Validator
                Draft202012Validator(guide["request_schema"]).validate(req)
                Draft202012Validator(guide["input_schema"]).validate(INPUT)
                self.assertTrue((await host.call_tool("ocp_validate",{"request":req})).structured_content["valid"])
                result=(await host.call_tool("ocp_execute",{"request":req})).structured_content
                self.assertEqual(verify_result(req,result)["total_cost"],11358)
                self.assertEqual(result,(await host.call_tool("ocp_execute",{"request":req})).structured_content)
                self.assertEqual((await host.call_tool("ocp_evaluate",{"request":req,"solution":result["solution"]})).structured_content["kind"],"evaluation")
            self.assertEqual(GATEWAY.summary()["calls"],before+1)
        asyncio.run(scenario())

    def test_13_source_build_uses_path_and_explicit_cache(self):
        env=dict(ENV)
        for key in ("OCP_NODE","OCP_NPM"):env.pop(key,None)
        output=DIRECTORY/"rebuilt-ts"
        result=self.cli(sys.executable,"-B",ROOT/"tools/build_typescript.py","--offline","--output",output,env=env)
        self.assertTrue(Path(json.loads(result.stdout)["tarball"]).resolve().is_relative_to(output.resolve()))
        empty=dict(env,OCP_NPM_CACHE=str(DIRECTORY/"empty-cache"))
        result=self.cli(sys.executable,"-B",ROOT/"tools/build_typescript.py","--offline","--output",DIRECTORY/"must-fail",expected=1,env=empty)
        self.assertIn("ENOTCACHED",result.stderr)

    def test_14_trace_errors_do_not_contact_provider_or_overwrite_output(self):
        before=GATEWAY.summary()["calls"]
        existing=KIT/"preserved-trace.json";existing.write_text("preserve this evidence")
        alias=KIT/"dangling-trace.json";alias.symlink_to(KIT/"absent-target.json")
        for session in [[],["--session",str(SESSION)]]:
            for target,code in [(existing,"TRACE_EXISTS"),(alias,"TRACE_EXISTS"),
                                (KIT/"absent-directory/trace.json","TRACE_DIRECTORY_MISSING")]:
                result=self.cli(PYTHON,"-B","own_app.py",*session,"--input","input.json",
                                "--request-id","trace-preflight","--trace",target,expected=1)
                value=json.loads(result.stdout);self.assertEqual(value["code"],code)
                self.assertNotIn("session.json",value["hint"])
        self.assertEqual(existing.read_text(),"preserve this evidence")
        self.assertFalse((KIT/"absent-target.json").exists())
        self.assertEqual(GATEWAY.summary()["calls"],before)


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(DeveloperJourney))
        passed=result.wasSuccessful() and result.testsRun>=14 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "findings":["U%02d"%i for i in range(1,10)],"artifact_sha256":BUILT["files"][WHEEL.name],
            "scope":"Fresh kit, real reference engine, Python/TypeScript/MCP/BYO consumer regression; no external humans, Claude host or new deployment"}))
    finally:SERVER.shutdown();SERVER.server_close();THREAD.join();WORK.cleanup()
    sys.exit(0 if passed else 1)
