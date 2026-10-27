"""Fresh three-domain kit, source provenance, checker-only and real consumers."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import tempfile
import unittest
import venv
import zipfile
from prepare_evaluation import prepare
from isolated_candidate import clean_env
from build_typescript import NODE,NPM
R=Path(__file__).resolve().parents[1]
PROFILES={'routing.basic':('basic-input.json',18),'worker.scheduling':('worker-input.json',7),'inventory.replenishment':('inventory-input.json',16)}
class FreshDomains(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='ocp-domain-kit-');cls.addClassCleanup(cls.temp.cleanup);cls.work=Path(cls.temp.name)
        cls.pack=cls.work/'evaluation';cls.manifest=prepare(cls.pack);cls.artifacts={p.name:p.read_bytes() for p in cls.pack.iterdir()};cls.kit=cls.work/'kit with spaces';cls.kit.mkdir()
        with zipfile.ZipFile(cls.pack/'ocp-developer-kit.zip') as z:z.extractall(cls.kit)
        cls.home=cls.work/'new-home';cls.home.mkdir();cls.env=clean_env(cls.home)
        cls.env.update(PATH=str(NODE.parent)+os.pathsep+os.defpath,PIP_NO_INDEX='1',PIP_FIND_LINKS=str(R/'.harness/work/wheels'),npm_config_cache=os.environ['OCP_NPM_CACHE'],npm_config_offline='true')
        hashes=json.loads((R/'tools/dependency-wheels.json').read_text())['sha256']
        for name,expected in hashes.items():
            if hashlib.sha256((R/'.harness/work/wheels'/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Changed dependency')
        cls.base=Path(sys._base_executable).resolve();cls.python=cls.work/'new agent/bin/python'
        cls.run_ok([cls.base,'-B','start.py','--mcp','--venv',cls.python.parent.parent])
        cls.checkpython=cls.work/'checker only/bin/python';venv.EnvBuilder(with_pip=True).create(cls.checkpython.parent.parent)
        cls.run_ok([cls.checkpython,'-B','-m','pip','install','--no-index','--no-cache-dir','--no-compile','--find-links',R/'.harness/work/wheels',cls.kit/'ocp_conformance_candidate-0.1.0-py3-none-any.whl'])
        cls.run_ok([NPM,'install','--offline','--no-save','--package-lock=false','--ignore-scripts','--no-audit','--no-fund','./ocp-candidate-0.1.0.tgz'])
    @classmethod
    def run_ok(cls,argv,expected=0):
        r=subprocess.run([str(x) for x in argv],cwd=cls.kit,env=cls.env,capture_output=True,text=True,timeout=180)
        if r.returncode!=expected:raise AssertionError(r.stdout[-2000:]+r.stderr[-2000:])
        return r.stdout
    def app(self,profile,path=None,rid='h30',expected=0):
        return json.loads(self.run_ok([self.python,'-I','-B','multi_app.py','--profile',profile,'--input',path or PROFILES[profile][0],'--request-id',rid],expected))
    def independent(self,report,fail=False):
        trace=self.kit/'trace.json';trace.write_text(json.dumps(report))
        code='''import importlib.util,json
assert all(importlib.util.find_spec(p) is None for p in ['ocp_candidate','ocp_planning','ocp_routing','ocp_runtime','ortools','mcp'])
from conformance.runner import CHECKERS
from conformance.core_contract import ContractError
x=json.load(open('trace.json'));p=x['request']['domain_profile']
try:
 CHECKERS[(p['id'],p['version'])](x['request'],x['response'])
except ContractError:
 raise SystemExit(3)
'''
        self.run_ok([self.checkpython,'-I','-B','-c',code],3 if fail else 0)
    def test_01_manifest_scope_and_files(self):
        for name,sha in self.manifest['files'].items():self.assertEqual(hashlib.sha256((self.pack/name).read_bytes()).hexdigest(),sha)
        self.assertFalse(self.manifest['distribution_authorized']);self.assertFalse(self.manifest['deployment_authorized']);self.assertEqual(self.manifest['model_calls'],0)
        src=json.loads((self.kit/'source-manifest.json').read_text())
        for name,sha in src['sources'].items():self.assertEqual(hashlib.sha256((R/name).read_bytes()).hexdigest(),sha)
        self.assertFalse(any(p.name.startswith(('.env','.private','session')) for p in self.kit.iterdir()))
    def test_02_same_python_app_three_domains(self):
        for profile,(_,cost) in PROFILES.items():
            report=self.app(profile);self.assertEqual(report['independent_check']['total_cost'],cost);self.assertEqual(report['execute_calls'],1);self.independent(report)
    def test_03_actual_mcp_each_profile(self):
        for profile,(name,cost) in PROFILES.items():
            report=json.loads(self.run_ok([self.python,'-I','-B','local_agent.py','smoke','--profile',profile,'--input',name,'--request-id','mcp-'+profile]))
            self.assertEqual(report['independent_check']['total_cost'],cost);self.assertEqual(report['model_calls'],0)
            self.assertEqual(report['tool_calls'],['ocp_context','ocp_validate','ocp_execute','ocp_evaluate'])
    def test_04_changed_input_scenarios(self):
        for profile in ('worker.scheduling','inventory.replenishment'):
            data=json.loads((self.kit/PROFILES[profile][0]).read_text())
            if profile=='worker.scheduling':data['tasks'][0]['costs']['alice']=9;expected=8
            else:data['products'][0]['holding_cost']=0;expected=14
            path=self.kit/'changed.json';path.write_text(json.dumps(data));r=self.app(profile,path,'changed-'+profile)
            self.assertEqual(r['independent_check']['total_cost'],expected);self.independent(r)
    def test_05_invalid_data_never_executes(self):
        for profile in ('worker.scheduling','inventory.replenishment'):
            data=json.loads((self.kit/PROFILES[profile][0]).read_text())
            if profile=='worker.scheduling':del data['workers'][0]['availability']
            else:del data['products'][0]['lead_time']
            path=self.kit/'missing.json';path.write_text(json.dumps(data));r=self.app(profile,path,expected=1)
            self.assertEqual(r['execute_calls'],0);self.assertFalse(r['validation']['valid'])
    def test_06_checker_only_rejects_corruption(self):
        for profile in ('worker.scheduling','inventory.replenishment'):
            report=self.app(profile);self.independent(report)
            for mutation in ('solution','cost','proof'):
                r=deepcopy(report)
                if mutation=='cost':r['response']['metrics'][0]['value']+=1
                elif mutation=='proof':r['response']['proof']['evidence']['objective']+=1
                elif profile=='worker.scheduling':r['response']['solution']['assignments'].pop()
                else:r['response']['solution']['plans'][0]['ending_inventory'][0]+=1
                self.independent(r,True)
    def test_07_kit_docs_and_unrun_model_tasks(self):
        guide=(self.kit/'MULTI_DOMAIN_QUICKSTART.md').read_text()
        for link in re.findall(r'\]\(([^)]+)\)',guide):self.assertTrue((self.kit/link).is_file(),link)
        tasks=json.loads((self.kit/'MULTI_DOMAIN_LLM_TASKS.json').read_text())
        self.assertEqual(len(tasks['scenarios']),8);self.assertEqual(tasks['status'],'PREPARED_NOT_MODEL_TESTED');self.assertFalse(tasks['execution_authorized'])
        self.assertEqual({x['profile'] for x in tasks['scenarios']},set(PROFILES))
    def test_08_installed_node_cli_profiles(self):
        for profile in ('worker.scheduling','inventory.replenishment'):
            child=subprocess.Popen([str(self.python),'-I','-B','-m','ocp_runtime.http_server','--profile',profile],cwd=self.kit,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout,selectors.EVENT_READ)
                    if not selector.select(60):raise AssertionError('provider startup timeout')
                url=json.loads(child.stdout.readline())['url']
                report=json.loads(self.run_ok([NODE,'own_app.cjs',url,PROFILES[profile][0],'node-'+profile]));self.assertEqual(report['status'],'PASS');self.independent(report)
            finally:
                child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
                child.stdout.close()
    def test_09_planning_without_routing_or_mcp_dependencies(self):
        path=self.work/'base planning';self.run_ok([self.base,'-B','install.py','--profile','byo','--venv',path]);python=path/'bin/python'
        self.run_ok([python,'-I','-B','-c','import importlib.util;assert importlib.util.find_spec("ortools") is None;assert importlib.util.find_spec("mcp") is None'])
        for profile in ('worker.scheduling','inventory.replenishment'):
            r=json.loads(self.run_ok([python,'-I','-B','multi_app.py','--profile',profile,'--input',PROFILES[profile][0],'--request-id','base-'+profile]));self.assertEqual(r['status'],'PASS')
if __name__=='__main__':
    r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(FreshDomains));ok=r.wasSuccessful() and not r.skipped
    if ok:
        saved=R/'.harness/work/multidomain-evaluation'/FreshDomains.manifest['files']['ocp-developer-kit.zip'];saved.mkdir(parents=True,exist_ok=True)
        for name,data in FreshDomains.artifacts.items():(saved/name).write_bytes(data)
    print(json.dumps({'artifact_sha256':getattr(FreshDomains,'manifest',{}).get('files',{}).get('ocp-developer-kit.zip'),'status':'PASS' if ok else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'scope':'Fresh macOS three-domain kit Python/Node/MCP and checker-only; no model, external human, sharing or deployment'}));sys.exit(0 if ok else 1)
