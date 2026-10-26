"""Real HTTP/TypeScript App B and MCP stdio subprocess integration."""

import asyncio
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_candidate import build
from build_typescript import build as build_ts, command, NODE, NPM
from isolated_candidate import install
from conformance.core_contract import validate_message
from conformance.routing import verify_result
from check_h02 import request, FIXTURE

WORK=tempfile.TemporaryDirectory(prefix="ocp-h06-")
DIRECTORY=Path(WORK.name)
ARTIFACT=build(DIRECTORY/"dist")
TS=build_ts(DIRECTORY/"dist")
PYTHON,ENV=install(DIRECTORY,ARTIFACT["wheel"],"reference,mcp")
sys.path.insert(0,ARTIFACT["wheel"])
from ocp_candidate import Client
from ocp_candidate.http_adapter import HTTPAdapter
from mcp import Client as MCPClient, StdioServerParameters

APP=DIRECTORY/"app-b"; APP.mkdir()
(APP/"package.json").write_text(json.dumps({"name":"private-app-b-test","version":"0.0.0","private":True,
    "dependencies":{"ocp-candidate":"file:"+TS["tarball"]},"devDependencies":{"typescript":"7.0.2","@types/node":"24.10.0"}}))
command([NPM,"install","--offline","--ignore-scripts","--no-audit","--no-fund"],APP)
shutil.copy2(ROOT/"examples/app-b/main.ts",APP/"main.ts")
command([NODE,APP/"node_modules/typescript/bin/tsc","--types","node","--target","ES2022","--module","Node16","--strict","--skipLibCheck","--outDir","dist","main.ts"],APP)
(APP/"input.json").write_text(json.dumps(FIXTURE["input"]))

SERVER=subprocess.Popen([str(PYTHON),"-I","-B","-m","ocp_runtime.http_server"],cwd=DIRECTORY,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
if not select.select([SERVER.stdout],[],[],30)[0]:
    SERVER.terminate(); raise RuntimeError("HTTP server did not start")
line=SERVER.stdout.readline()
if not line:
    raise RuntimeError(SERVER.stderr.read())
URL=json.loads(line)["url"]
PORT=urlparse(URL).port


def http(method,path,payload=None,headers=None,raw=None):
    connection=HTTPConnection("127.0.0.1",PORT,timeout=10)
    body=raw if raw is not None else None if payload is None else json.dumps(payload)
    connection.request(method,path,body=body,headers={"Content-Type":"application/json",**(headers or {})})
    response=connection.getresponse(); status=response.status; result=json.loads(response.read()); connection.close()
    return status,result


class BindingTests(unittest.TestCase):
    def test_01_http_capability(self):
        status,value=http("GET","/v1/capability"); self.assertEqual(status,200); validate_message(value)
        self.assertEqual(value["bindings"],[{"id":"binding.http","version":"0.1.0"}])

    def test_02_python_http_client_real_solve(self):
        client=Client(HTTPAdapter(URL)); req=client.request(FIXTURE["input"],request_id="http-real")
        result=client.execute(FIXTURE["input"],request_id="http-real")
        self.assertEqual(result["kind"],"result",result.get("error",{}).get("code"))
        self.assertEqual(verify_result(req,result)["total_cost"],18)

    def test_03_http_requirements(self):
        _,value=http("POST","/v1/requirements",{"configuration":FIXTURE["configuration"]})
        self.assertEqual(value["kind"],"requirements"); validate_message(value)

    def test_04_http_invalid_data_validation(self):
        req=request(); del req["input"]["matrix"]
        _,value=http("POST","/v1/validate",req); self.assertFalse(value["valid"])

    def test_05_http_execute_unsupported_configuration(self):
        req=request(); req["configuration"]["objectives"][0]["weight"]=2
        _,value=http("POST","/v1/execute",req); self.assertEqual(value["error"]["code"],"UNSUPPORTED_CONFIGURATION")

    def test_06_http_evaluation(self):
        _,value=http("POST","/v1/evaluate",{"request":request(),"solution":FIXTURE["witness"]})
        self.assertEqual(value["metrics"][0]["value"],18); validate_message(value)

    def test_07_http_async_not_faked(self):
        req=request(); req["execution_profile"]["id"]="execution.async"
        _,value=http("POST","/v1/execute",req); self.assertEqual(value["error"]["code"],"UNSUPPORTED_EXECUTION")
        self.assertEqual(http("POST","/v1/jobs",req)[0],404)

    def test_08_http_duplicate_json(self):
        self.assertEqual(http("POST","/v1/execute",raw='{"input":{},"input":{}}')[0],400)

    def test_09_http_content_type(self):
        self.assertEqual(http("POST","/v1/execute",request(),{"Content-Type":"text/plain"})[0],415)

    def test_10_http_body_limit(self):
        self.assertEqual(http("POST","/v1/execute",raw="x"*131073)[0],413)

    def test_11_http_origin(self):
        self.assertEqual(http("POST","/v1/execute",request(),{"Origin":"https://example.invalid"})[0],403)

    def test_12_http_host(self):
        self.assertEqual(http("GET","/v1/capability",headers={"Host":"example.invalid"})[0],403)

    def test_13_http_version_mismatch(self):
        req=request(); req["capability"]["version"]="0.2.0"
        _,value=http("POST","/v1/execute",req); self.assertEqual(value["error"]["code"],"VERSION_MISMATCH")

    def test_14_typescript_app_b_real_solve(self):
        out=command([NODE,"dist/main.js",URL,"input.json","--request-id","app-b"],APP)
        value=json.loads(out); req=request(); req["request_id"]="app-b"
        self.assertEqual(verify_result(req,value)["total_cost"],18)

    def test_15_typescript_core_fixture_parity_and_negatives(self):
        shutil.copy2(ROOT/"cases/core/messages.json",APP/"messages.json")
        (APP/"checks.cjs").write_text('''const assert=require('node:assert/strict');
const {envelope,strictParse}=require('ocp-candidate');
const fixtures=require('./messages.json').positive;
for(const item of fixtures) envelope(item.message);
for(const raw of ['{"a":1,"a":2}','{"a":{"x":1,"x":2}}','{"x":NaN}','{"x":1e999}','{"x":9007199254740992}','{"a":1,}','{/*comment*/"a":1}']) assert.throws(()=>strictParse(raw));
let value=structuredClone(fixtures.find(f=>f.message.kind==='result').message);
value.metrics[0].status='not_evaluated';value.metrics[0].value=0;assert.throws(()=>envelope(value));
value=structuredClone(fixtures[0].message);value.core_version='0.2.0';assert.throws(()=>envelope(value));
value=structuredClone(fixtures[0].message);value.extensions=[{id:'new',version:'1',required:true,value:{}}];assert.throws(()=>envelope(value));
console.log(JSON.stringify({passed:true}));
''')
        self.assertTrue(json.loads(command([NODE,"checks.cjs"],APP))["passed"])

    def test_16_typescript_schema_matches_canonical(self):
        bundled=APP/"node_modules/ocp-candidate/dist/schemas/core-0.1.schema.json"
        self.assertEqual(bundled.read_bytes(),(ROOT/"spec/schemas/core-0.1.schema.json").read_bytes())

    def test_21_typescript_bounds_untrusted_response_stream(self):
        (APP/"response-limit.cjs").write_text('''const assert=require('node:assert/strict');
const {Client}=require('ocp-candidate');
(async()=>{
  for(const declared of [true,false]) {
    let cancelled=false,pulls=0;
    global.fetch=async()=>new Response(new ReadableStream({
      pull(controller){pulls++;controller.enqueue(new Uint8Array(65536));},
      cancel(){cancelled=true;}
    }),{headers:{'content-type':'application/json',...(declared?{'content-length':'1048577'}:{})}});
    await assert.rejects(()=>Client.connect('https://example.invalid'),/RESPONSE_TOO_LARGE/);
    assert.equal(cancelled,true);assert.ok(pulls<=18);
  }
  global.fetch=async()=>new Response(new Uint8Array([0xff]),{headers:{'content-type':'application/json'}});
  await assert.rejects(()=>Client.connect('https://example.invalid'),TypeError);
  console.log(JSON.stringify({passed:true}));
})().catch(e=>{console.error(e);process.exitCode=1;});
''')
        self.assertTrue(json.loads(command([NODE,"response-limit.cjs"],APP))["passed"])


def mcp_session(test):
    async def wrapped(self):
        async with MCPClient(StdioServerParameters(command=str(PYTHON),args=["-I","-B","-m","ocp_runtime.mcp_server"],env=ENV,cwd=str(DIRECTORY)),read_timeout_seconds=30) as client:
            self.client=client
            await test(self)
    return wrapped


class MCPTests(unittest.IsolatedAsyncioTestCase):

    async def call(self,name,args=None):
        output=await self.client.call_tool(name,args or {})
        validate_message(output.structured_content)
        self.assertEqual(output.is_error,output.structured_content["kind"]=="failure")
        return output.structured_content

    @mcp_session
    async def test_17_mcp_discovery_and_describe(self):
        tools=await self.client.list_tools()
        self.assertEqual({t.name for t in tools.tools},{"ocp_describe","ocp_requirements","ocp_validate","ocp_execute","ocp_evaluate"})
        value=await self.call("ocp_describe")
        self.assertEqual(value["bindings"],[{"id":"binding.mcp_stdio","version":"0.1.0"}])
        self.assertEqual(self.client.protocol_version,"2026-07-28")

    @mcp_session
    async def test_18_mcp_requirements_validate_execute_evaluate(self):
        await self.call("ocp_requirements",{"configuration":FIXTURE["configuration"]})
        checked=await self.call("ocp_validate",{"request":request()}); self.assertTrue(checked["valid"])
        value=await self.call("ocp_execute",{"request":request()})
        self.assertEqual(verify_result(request(),value)["total_cost"],18)
        evaluation=await self.call("ocp_evaluate",{"request":request(),"solution":value["solution"]})
        self.assertEqual(evaluation["metrics"][0]["value"],18)

    @mcp_session
    async def test_19_mcp_unsupported_is_core_failure(self):
        req=request(); req["configuration"]["objectives"][0]["weight"]=2
        value=await self.call("ocp_execute",{"request":req})
        self.assertEqual(value["error"]["code"],"UNSUPPORTED_CONFIGURATION")

    @mcp_session
    async def test_20_mcp_missing_tool_and_invalid_arguments(self):
        for name,args in [("ocp_cancel",{}),("ocp_execute",{"request":"bad"})]:
            output=await self.client.call_tool(name,args); self.assertTrue(output.is_error)


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
        passed=result.wasSuccessful() and result.testsRun>=21 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
                          "artifact_sha256":ARTIFACT["sha256"],"versions":{"python":"3.12","mcp":"2.3.0","mcp_protocol":"2026-07-28","typescript":"7.0.2","typescript_tarball_sha256":TS["sha256"],"http_binding":"0.1.0"},
                          "scope":"Installed loopback HTTP, Python/TypeScript consumers, official MCP SDK subprocess host; not Claude Desktop, remote trial or async execution"}))
    finally:
        SERVER.terminate(); SERVER.wait(timeout=10); WORK.cleanup()
    sys.exit(0 if passed else 1)
