"""One installed MCP/HTTP interface, three real domains and common consumers."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from build_candidate import build
from isolated_candidate import install,clean_env
from build_typescript import build as build_ts,NODE,NPM
from conformance.runner import CHECKERS
from conformance.core_contract import ContractError
WORK=tempfile.TemporaryDirectory(prefix='ocp-three-domains-');BASE=Path(WORK.name)
WHEEL=build(BASE/'dist');PYTHON,ENV=install(BASE,WHEEL['wheel'],'reference,mcp');sys.path.insert(0,WHEEL['wheel'])
ENV.update(PATH=str(NODE.parent)+os.pathsep+os.defpath,npm_config_cache=os.environ['OCP_NPM_CACHE'],npm_config_offline='true')
from ocp_runtime.providers import make_provider,PROVIDERS
from ocp_runtime.http_server import create_server
from ocp_candidate import Client
from ocp_candidate.contract import OCPError,schema
from ocp_candidate.profiles import packaged_registry,ProfileRegistry
from mcp import Client as MCPClient,StdioServerParameters
from jsonschema import Draft202012Validator
INPUTS={id:json.loads((R/path).read_text())['input'] for id,path in [('routing.basic','cases/routing/basic-matrix.json'),('worker.scheduling','cases/worker/small.json'),('inventory.replenishment','cases/inventory/small.json')]}
async def session(callback):
    params=StdioServerParameters(command=str(PYTHON),args=['-I','-B','-m','ocp_runtime.mcp_server','--profile','all'],env=ENV,cwd=str(BASE))
    async with MCPClient(params,read_timeout_seconds=60) as host:return await callback(host)
class Integration(unittest.TestCase):
    def test_01_mcp_all_profiles_actual_solve(self):
        async def run(host):
            self.assertEqual(len((await host.list_tools()).tools),6)
            for id,p in INPUTS.items():
                v=await host.call_tool('ocp_context',{'profile':id});self.assertFalse(v.is_error);g=v.structured_content
                self.assertEqual(len(g['available_profiles']),3);Draft202012Validator(g['input_schema']).validate(p)
                self.assertTrue(g['profile_semantics']);r=deepcopy(g['request_template']);r.update(input=p,request_id='h29-'+id)
                valid=await host.call_tool('ocp_validate',{'request':r});self.assertTrue(valid.structured_content['valid'])
                out=(await host.call_tool('ocp_execute',{'request':r})).structured_content
                self.assertIsNotNone(CHECKERS[(id,'0.1.0')](r,out))
                e=(await host.call_tool('ocp_evaluate',{'request':r,'solution':out['solution']})).structured_content
                self.assertEqual(e['kind'],'evaluation');self.assertEqual(e['metrics'][0]['value'],out['metrics'][0]['value'])
        asyncio.run(session(run))
    def test_02_mcp_reject_unknown_profile_and_version(self):
        async def run(host):
            x=await host.call_tool('ocp_context',{'profile':'unknown'});self.assertTrue(x.is_error)
            g=(await host.call_tool('ocp_context',{'profile':'worker.scheduling'})).structured_content
            r=g['request_template'];r.update(input=INPUTS['worker.scheduling'],request_id='bad-version');r['domain_profile']['version']='2.0.0'
            x=await host.call_tool('ocp_execute',{'request':r});self.assertTrue(x.is_error)
        asyncio.run(session(run))
    def test_03_mcp_missing_inputs_rejected(self):
        async def run(host):
            for id in INPUTS:
                g=(await host.call_tool('ocp_context',{'profile':id})).structured_content;r=g['request_template'];r['request_id']='missing'
                v=(await host.call_tool('ocp_validate',{'request':r})).structured_content;self.assertFalse(v['valid'])
        asyncio.run(session(run))
    def test_04_node_same_application_three_providers(self):
        artifact=build_ts(BASE/'node-dist')
        subprocess.run([str(NPM),'install','--offline','--no-save','--package-lock=false','--ignore-scripts','--no-audit','--no-fund',artifact['tarball']],cwd=BASE,env=ENV,capture_output=True,check=True,timeout=60)
        app=BASE/'own_app.cjs';app.write_text((R/'examples/app-b/own_app.cjs').read_text())
        for id,p in INPUTS.items():
            server=create_server(make_provider(id));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                path=BASE/(id+'.json');path.write_text(json.dumps(p))
                r=subprocess.run([str(NODE),str(app),'http://127.0.0.1:'+str(server.server_port),str(path),'node-'+id],cwd=BASE,env=ENV,capture_output=True,text=True,timeout=60)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr);o=json.loads(r.stdout);CHECKERS[(id,'0.1.0')](o['request'],o['response'])
            finally:server.shutdown();server.server_close();thread.join(timeout=5)
    def test_05_registry_no_network_or_overwrite(self):
        registry=packaged_registry();cap=make_provider('worker.scheduling').describe();value=registry.resolve(cap)
        value['input_schema']['properties'].clear();self.assertTrue(registry.resolve(cap)['input_schema']['properties'])
        cap['input_schema_id']='urn:wrong'
        with self.assertRaises(OCPError):registry.resolve(cap)
        external={'$id':'urn:example','$ref':'https://example.invalid/schema'}
        with self.assertRaises(OCPError):ProfileRegistry().register({'id':'custom','version':'1'},external,external,['example'])
    def test_06_custom_profile_registration(self):
        registry=ProfileRegistry();ref={'id':'external.example','version':'0.1.0'};inp={'$id':'urn:external:input','type':'object'};sol={'$id':'urn:external:solution','type':'object'}
        registry.register(ref,inp,sol,['Explicit external semantics'])
        cap={'domain_profile':ref,'input_schema_id':inp['$id'],'solution_schema_id':sol['$id']}
        self.assertEqual(registry.resolve(cap)['input_schema'],inp)
        with self.assertRaises(OCPError):registry.register(ref,inp,sol,['duplicate'])
    def test_07_transcript_dispatch_covers_domains(self):
        from conformance.runner import verify_bundle
        import hashlib
        for id in INPUTS:
            c=Client(make_provider(id));r=c.request(INPUTS[id],request_id='transcript');o=c.execute(INPUTS[id],request_id='transcript')
            b={'artifact_sha256':hashlib.sha256(b'test-artifact').hexdigest(),'implementation':o['provenance']['implementation'],'cases':[{'id':'normal','request':r,'response':o}]}
            self.assertEqual(verify_bundle(b,b'test-artifact')['status'],'PASS')
    def test_09_multiserver_provider_failure_is_sanitized(self):
        from ocp_runtime.mcp_server import create_mcp
        class Broken:
            def describe(self):raise RuntimeError('synthetic-private-canary')
        adapter=make_provider('worker.scheduling');request=Client(adapter).request(INPUTS['worker.scheduling'],request_id='failed-context')
        calls=[]
        adapter.execute=lambda r:calls.append(r)
        async def probe():
            async with MCPClient(create_mcp([adapter,Broken()])) as host:
                for tool,args in [('ocp_context',{'profile':'worker.scheduling'}),('ocp_execute',{'request':request})]:
                    value=await host.call_tool(tool,args)
                    self.assertTrue(value.is_error);self.assertEqual(value.structured_content['error']['code'],'CONTEXT_UNAVAILABLE')
                    self.assertNotIn('synthetic-private-canary',json.dumps(value.structured_content))
                    if tool=='ocp_execute':self.assertEqual(value.structured_content['request_id'],'failed-context')
        asyncio.run(probe());self.assertEqual(calls,[])
    def test_08_registry_does_not_import_solvers(self):
        r=subprocess.run([str(PYTHON),'-I','-B','-c','from ocp_candidate.profiles import packaged_registry;import sys;packaged_registry();assert "ortools" not in sys.modules;assert "ocp_planning" not in sys.modules'],cwd=BASE,env=ENV,capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':
    r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Integration));ok=r.wasSuccessful() and not r.skipped
    print(json.dumps({'artifact_sha256':WHEEL['sha256'],'status':'PASS' if ok else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'scope':'Installed actual MCP three domains, Node/HTTP and registry; no LLM call'}));WORK.cleanup();sys.exit(0 if ok else 1)
