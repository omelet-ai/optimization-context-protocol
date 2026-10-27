"""Fresh no-key MCP + Python/Node consumers and exact local evaluation package."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import zipfile

from prepare_evaluation import prepare
from build_invitation_kit import source_provenance
from isolated_candidate import clean_env
from build_typescript import NODE,NPM

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from safe_test_result import DiagnosticResult


class NoKeyJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="ocp-no-key-");cls.addClassCleanup(cls.temp.cleanup)
        cls.work=Path(cls.temp.name);cls.pack=cls.work/"evaluation"
        cls.manifest=prepare(cls.pack)
        cls.kit=cls.work/'fresh kit with spaces';cls.kit.mkdir()
        with zipfile.ZipFile(cls.pack/"ocp-developer-kit.zip") as archive:archive.extractall(cls.kit)
        cls.home=cls.work/"empty-home";cls.home.mkdir();cls.env=clean_env(cls.home)
        cls.env.update(PATH=str(NODE.parent)+os.pathsep+os.defpath,
                       PIP_NO_INDEX="1",PIP_FIND_LINKS=str(ROOT/".harness/work/wheels"),
                       npm_config_cache=os.environ["OCP_NPM_CACHE"],npm_config_offline="true")
        reviewed=json.loads((ROOT/"tools/dependency-wheels.json").read_text())["sha256"]
        for name,sha in reviewed.items():
            if hashlib.sha256((ROOT/".harness/work/wheels"/name).read_bytes()).hexdigest()!=sha:raise RuntimeError("Changed wheel")
        cls.base=Path(sys._base_executable).resolve();cls.venv=cls.work/'agent env "quoted"'
        cls.started=cls.run_process([cls.base,"-B","start.py","--mcp","--venv",cls.venv])
        if cls.started.returncode:raise RuntimeError(cls.started.stderr[-3000:])
        cls.python=cls.venv/"bin/python"
        cls.byo=cls.work/"byo"
        installed=cls.run_process([cls.base,"-B","install.py","--profile","byo","--venv",cls.byo])
        if installed.returncode:raise RuntimeError("BYO setup failed")
        npm=cls.run_process([NPM,"install","--no-save","--package-lock=false","--ignore-scripts","--no-audit","--no-fund","./ocp-candidate-0.1.0.tgz"])
        if npm.returncode:raise RuntimeError(npm.stderr[-2000:])
        compiled=cls.run_process([NPM,"run","build"])
        if compiled.returncode:raise RuntimeError(compiled.stdout[-2000:])
        cls.provider=subprocess.Popen([str(cls.python),"-I","-B","-m","ocp_runtime.http_server"],cwd=cls.work,env=cls.env,
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        cls.addClassCleanup(cls.stop_provider)
        with selectors.DefaultSelector() as selector:
            selector.register(cls.provider.stdout,selectors.EVENT_READ)
            if not selector.select(60):raise RuntimeError("Provider startup timeout")
        cls.url=json.loads(cls.provider.stdout.readline())["url"]

    @classmethod
    def stop_provider(cls):
        if cls.provider.poll() is None:
            cls.provider.terminate()
            try:cls.provider.wait(timeout=10)
            except subprocess.TimeoutExpired:cls.provider.kill();cls.provider.wait(timeout=5)
        cls.provider.stdout.close();cls.provider.stderr.close()

    @classmethod
    def run_process(cls,argv,cwd=None,env=None):
        return subprocess.run([str(x) for x in argv],cwd=cwd or cls.kit,env=env or cls.env,capture_output=True,text=True,timeout=180)

    def agent(self,*args,python=None,cwd=None,env=None):
        r=self.run_process([python or self.python,"-I","-B",self.kit/"local_agent.py",*args],cwd,env)
        return r,json.loads(r.stdout)

    def test_01_first_success_and_no_solve_doctor(self):
        self.assertEqual(json.loads(self.started.stdout)["status"],"PASS")
        r,d=self.agent("doctor",cwd=self.work,env=dict(self.env,PYTHONPATH="/nonexistent",OCP_TRIAL_TOKEN="synthetic-marker"))
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(d["execute_calls"],0)
        self.assertEqual(d["model_calls"],0);self.assertEqual(d["tool_calls"],["ocp_context"])
        self.assertEqual(len(d["tools"]),6);self.assertNotIn("synthetic-marker",r.stdout+r.stderr)

    def test_02_config_quotes_and_venv_are_preserved(self):
        r,c=self.agent("config","--format","json")
        self.assertEqual(r.returncode,0);config=c["mcpServers"]["ocp-local"]
        self.assertEqual(config["command"],str(self.python));self.assertEqual(config["args"][:2],["-I","-B"])
        r=self.run_process([self.python,"-I","-B",self.kit/"local_agent.py","config","--format","codex"])
        toml=tomllib.loads(r.stdout)["mcp_servers"]["ocp-local"]
        for key in config:self.assertEqual(toml[key],config[key])
        self.assertEqual(toml["startup_timeout_sec"],60);self.assertTrue(toml["required"])
        self.assertFalse((self.home/".codex").exists())

    def test_03_actual_mcp_solve_and_independent_check(self):
        r,d=self.agent("smoke","--input",self.kit/"basic-input.json","--request-id","h25-mcp",cwd=self.work)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertTrue(d["solution_found"])
        self.assertEqual(d["execute_calls"],1);self.assertEqual(d["independent_check"]["total_cost"],18)
        self.assertEqual(d["evaluation"]["kind"],"evaluation")
        self.assertEqual(d["tool_calls"],["ocp_context","ocp_validate","ocp_execute","ocp_evaluate"])

    def invalid(self,mode):
        data=json.loads((self.kit/"basic-input.json").read_text())
        if mode=="unit":data["matrix"]["unit"]="kilometer"
        else:del data["vehicles"][0]["capacity"]
        p=self.work/(mode+".json");p.write_text(json.dumps(data));return p

    def test_04_wrong_unit_never_executes(self):
        r,d=self.agent("smoke","--input",self.invalid("unit"),"--request-id","bad-unit")
        self.assertNotEqual(r.returncode,0);self.assertEqual(d["code"],"INPUT_REJECTED");self.assertEqual(d["execute_calls"],0)

    def test_05_missing_data_never_executes(self):
        r,d=self.agent("smoke","--input",self.invalid("capacity"),"--request-id","bad-capacity")
        self.assertNotEqual(r.returncode,0);self.assertEqual(d["execute_calls"],0);self.assertNotIn("ocp_execute",d["tool_calls"])

    def test_06_strict_json_and_size_limit(self):
        for raw in ('{"a":1,"a":2}', 'null', '{"x":NaN}', ' '*131073):
            p=self.work/"invalid.json";p.write_text(raw)
            r,d=self.agent("smoke","--input",p,"--request-id","invalid")
            self.assertNotEqual(r.returncode,0);self.assertEqual(d["code"],"INPUT_INVALID")

    def test_07_missing_extras_has_actionable_diagnostic(self):
        r,d=self.agent("doctor",python=self.byo/"bin/python")
        self.assertNotEqual(r.returncode,0);self.assertEqual(d["code"],"LOCAL_MCP_DEPENDENCIES_MISSING")
        self.assertIn("start.py --mcp",d["hint"]);self.assertNotIn("Traceback",r.stderr)

    def test_08_python_app_changed_input(self):
        data=json.loads((self.kit/"basic-input.json").read_text())
        data["matrix"]["values"]=[[v*2 for v in row] for row in data["matrix"]["values"]]
        p=self.work/"my-input.json";p.write_text(json.dumps(data))
        r=self.run_process([self.python,"-B","own_app.py","--input",p,"--request-id","h25-own-python"])
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(json.loads(r.stdout)["independent_check"]["total_cost"],36)

    def test_09_node_app_changed_input_and_independent_check(self):
        data=json.loads((self.kit/"basic-input.json").read_text());data["matrix"]["values"]=[[v*2 for v in row] for row in data["matrix"]["values"]]
        p=self.work/"node-input.json";p.write_text(json.dumps(data))
        r=self.run_process([NODE,"own_app.cjs",self.url,p,"h25-own-node"])
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);d=json.loads(r.stdout);self.assertEqual(d["evaluation"]["metrics"][0]["value"],36)
        trace=self.work/"node-trace.json";trace.write_text(r.stdout)
        checked=self.run_process([self.python,"-I","-B","-c","import json,sys;from conformance.routing import verify_result;v=json.load(open(sys.argv[1]));assert verify_result(v['request'],v['response'])['total_cost']==36",trace],cwd=self.work)
        self.assertEqual(checked.returncode,0,checked.stderr)

    def test_10_node_rejects_invalid_input_before_execute(self):
        r=self.run_process([NODE,"own_app.cjs",self.url,self.invalid("unit"),"h25-invalid-node"])
        self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)["execute_calls"],0)

    def test_11_typescript_build_and_actual_app(self):
        r=self.run_process([NODE,"dist/main.js",self.url,"basic-input.json","--request-id","h25-typescript"])
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(json.loads(r.stdout)["status"],"feasible")

    def test_12_frozen_package_provenance_and_tasks(self):
        for name,sha in self.manifest["files"].items():self.assertEqual(hashlib.sha256((self.pack/name).read_bytes()).hexdigest(),sha)
        source=json.loads((self.kit/"source-manifest.json").read_text());hashes=source["sources"]
        self.assertEqual(source["source_tree_sha256"],hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest())
        for name,sha in hashes.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),sha)
        for name in ("LLM_QUICKSTART.md","EVALUATION_TASKS.md","FEEDBACK_TEMPLATE.md"):
            self.assertTrue((self.kit/name).is_file())
        self.assertFalse(self.manifest["distribution_authorized"]);self.assertFalse(self.manifest["deployment_authorized"])
        self.assertEqual(self.manifest["human_acceptance"],"NOT_RUN")
        self.assertFalse(any((self.kit/name).exists() for name in (".private","reference","session.json")))

    def test_13_missing_git_preserves_content_identity(self):
        hashes={"synthetic.txt":hashlib.sha256(b"synthetic").hexdigest()}
        with patch.dict(os.environ,{"PATH":"/nonexistent"}):
            source=source_provenance(hashes)
        self.assertIsNone(source["base_commit"]);self.assertIsNone(source["selected_sources_differ_from_base_commit"])
        self.assertEqual(source["sources"],hashes)
        self.assertEqual(source["source_tree_sha256"],hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest())


if __name__=="__main__":
    result=unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(NoKeyJourney))
    passed=result.wasSuccessful() and result.testsRun>=13 and not result.skipped
    print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
        "skipped":len(result.skipped),"failure_diagnostics":result.diagnostics,
        "scope":"Fresh macOS kit MCP/Python/Node consumers and local evaluation package; no model call, human acceptance, Linux or publication"}))
    sys.exit(0 if passed else 1)
