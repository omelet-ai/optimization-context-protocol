"""Fresh first success, real engine substitution and isolated checker rejection."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv

from build_invitation_kit import build
from isolated_candidate import clean_env

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from safe_test_result import DiagnosticResult


class FirstSuccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="ocp-first-success-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work=Path(cls.temp.name);cls.kit=cls.work/"fresh kit with spaces"
        cls.built=build(cls.kit)
        cls.home=cls.work/"empty-home";cls.home.mkdir();cls.env=clean_env(cls.home)
        cls.wheels=ROOT/".harness/work/wheels"
        reviewed=json.loads((ROOT/"tools/dependency-wheels.json").read_text())["sha256"]
        for name,sha in reviewed.items():
            if hashlib.sha256((cls.wheels/name).read_bytes()).hexdigest()!=sha:raise RuntimeError("Changed dependency wheel")
        cls.base=cls.work/"python3.12";cls.base.symlink_to(Path(sys._base_executable).resolve())
        cls.env.update(PIP_NO_INDEX="1",PIP_FIND_LINKS=str(cls.wheels))
        cls.local=cls.work/"local environment"
        cls.started=cls.run_process([cls.base,"-B","start.py","--venv",cls.local])
        if cls.started.returncode:raise RuntimeError(cls.started.stderr[-3000:]+cls.started.stdout[-1000:])
        cls.report=json.loads(cls.started.stdout);cls.python=cls.local/"bin/python"
        cls.byo=cls.work/"byo"
        result=cls.run_process([cls.base,"-B","install.py","--profile","byo","--venv",cls.byo])
        if result.returncode:raise RuntimeError(result.stderr[-1000:])
        cls.checker=cls.work/"checker-only"
        venv.EnvBuilder(with_pip=True,symlinks=True).create(cls.checker)
        cls.checkpython=cls.checker/"bin/python"
        result=cls.run_process([cls.checkpython,"-m","pip","install","--no-index","--no-compile","--find-links",cls.wheels,cls.kit/"ocp_conformance_candidate-0.1.0-py3-none-any.whl"])
        if result.returncode:raise RuntimeError(result.stderr[-1000:])

    @classmethod
    def run_process(cls,argv,cwd=None,env=None):
        return subprocess.run([str(x) for x in argv],cwd=cwd or cls.kit,env=cls.env if env is None else env,
                              capture_output=True,text=True,timeout=120)

    def test_01_first_command_runs_two_real_engines(self):
        self.assertEqual(self.report["status"],"PASS")
        self.assertEqual(set(self.report["runs"]),{"reference","own"})
        for name,trace in self.report["runs"].items():
            self.assertEqual(trace["response"]["status"],"feasible")
            self.assertTrue(trace["independent_check"]["feasible"])
            self.assertEqual(trace["independent_check"]["total_cost"],18)
            self.assertEqual(trace["evaluation"]["kind"],"evaluation")
        self.assertNotEqual(self.report["runs"]["reference"]["response"]["provenance"]["engine"],
                            self.report["runs"]["own"]["response"]["provenance"]["engine"])
        self.assertFalse((self.kit/"session.json").exists())

    def test_02_same_input_and_semantics(self):
        a,b=[self.report["runs"][k]["request"] for k in ("reference","own")]
        for field in ("input","domain_profile","configuration","budget"):
            self.assertEqual(a[field],b[field])
        self.assertNotEqual(a["capability"],b["capability"])

    def test_03_changed_input_is_recalculated(self):
        problem=json.loads((self.kit/"basic-input.json").read_text())
        problem["matrix"]["values"]=[[2*v for v in row] for row in problem["matrix"]["values"]]
        path=self.work/"changed.json";path.write_text(json.dumps(problem))
        result=self.run_process([self.python,"-B","demo.py","--input",path])
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertNotEqual(report["input_sha256"],self.report["input_sha256"])
        for trace in report["runs"].values():self.assertEqual(trace["independent_check"]["total_cost"],36)

    def test_04_unsupported_unit_is_rejected(self):
        result=self.report["diagnostics"]["unsupported_unit"]
        self.assertTrue(result["rejected"]);self.assertTrue(result["issues"])

    def test_05_damaged_results_are_rejected(self):
        for name,code in (("capacity_violation","INFEASIBLE_SOLUTION"),("missing_visit","INFEASIBLE_SOLUTION"),("wrong_objective","EVALUATION_MISMATCH")):
            self.assertEqual(self.report["diagnostics"][name],{"rejected":True,"code":code})

    def test_06_real_deadline_does_not_claim_impossibility(self):
        value=self.report["diagnostics"]["deadline"]
        self.assertEqual(value["budget_ms"],1)
        self.assertEqual(value["termination"],"time_limit")
        self.assertEqual(value["status"],"feasible" if value["has_solution"] else "unknown")
        if value["has_solution"]:self.assertTrue(value["independent_check"]["feasible"])
        else:self.assertIsNone(value["independent_check"])

    def test_07_checker_only_environment_accepts_then_rejects(self):
        trace=self.report["runs"]["reference"]
        path=self.work/"real-trace.json";path.write_text(json.dumps(trace))
        code='''import importlib.util,json,sys
from copy import deepcopy
from conformance.routing import verify_result
from conformance.core_contract import ContractError
for name in ('ocp_candidate','ocp_routing','ocp_runtime','ortools'):
    assert importlib.util.find_spec(name) is None, name
trace=json.load(open(sys.argv[1]));request=trace['request'];result=trace['response']
assert verify_result(request,result)['feasible']
for mode in ('capacity','missing','cost'):
    bad=deepcopy(result)
    if mode=='capacity':
        bad['solution']['routes'][0]['visits']=[v['id'] for v in request['input']['visits']]
        for route in bad['solution']['routes'][1:]:route['visits']=[]
    elif mode=='missing':next(r for r in bad['solution']['routes'] if r['visits'])['visits'].pop()
    else:bad['metrics'][0]['value']+=1
    try:verify_result(request,bad)
    except ContractError:pass
    else:raise AssertionError(mode)
print('independent-checker-rejected-all-three')
'''
        result=self.run_process([self.checkpython,"-I","-B","-c",code,path],cwd=self.work)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("independent-checker-rejected-all-three",result.stdout)

    def test_08_byo_needs_no_bundled_solver_or_mcp(self):
        python=self.byo/"bin/python"
        absent=self.run_process([python,"-I","-c","import importlib.util; assert importlib.util.find_spec('ortools') is None; assert importlib.util.find_spec('mcp') is None"])
        self.assertEqual(absent.returncode,0,absent.stderr)
        result=self.run_process([python,"-B","demo.py","--engine","own"])
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["runs"]["own"]["independent_check"]["total_cost"],18)

    def test_09_tamper_fails_before_creating_environment(self):
        changed=self.work/"damaged-kit";shutil.copytree(self.kit,changed)
        with (changed/"demo.py").open("a") as stream:stream.write("\n# changed\n")
        target=self.work/"tampered-env"
        result=self.run_process([self.base,"-B","start.py","--venv",target],cwd=changed)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("KIT_CHECKSUM_MISMATCH",result.stderr)
        self.assertFalse(target.exists())

    def test_10_existing_environment_is_preserved(self):
        before=(self.local/"pyvenv.cfg").read_bytes()
        result=self.run_process([self.base,"-B","start.py","--venv",self.local])
        self.assertNotEqual(result.returncode,0);self.assertIn("ENVIRONMENT_EXISTS",result.stderr)
        self.assertEqual(before,(self.local/"pyvenv.cfg").read_bytes())
        link=self.work/"dangling";link.symlink_to(self.work/"absent")
        result=self.run_process([self.base,"-B","start.py","--venv",link])
        self.assertNotEqual(result.returncode,0);self.assertIn("ENVIRONMENT_EXISTS",result.stderr)
        self.assertTrue(link.is_symlink());self.assertFalse((self.work/"absent").exists())

    def test_11_offline_mode_never_falls_back_to_network(self):
        env=dict(self.env);env.pop("PIP_FIND_LINKS")
        target=self.work/"missing-offline"
        result=self.run_process([self.base,"-B","start.py","--venv",target],env=env)
        self.assertNotEqual(result.returncode,0);self.assertIn("OFFLINE_WHEELHOUSE_REQUIRED",result.stderr)
        self.assertFalse(target.exists())

    def test_12_engine_limit_is_actionable(self):
        problem=json.loads((self.kit/"basic-input.json").read_text())
        for i in range(3):
            problem["visits"].append({"id":"extra-"+str(i),"demand":0})
            problem["matrix"]["node_ids"].append("extra-"+str(i))
        problem["matrix"]["values"]=[[0 if i==j else 1 for j in range(8)] for i in range(8)]
        path=self.work/"too-many.json";path.write_text(json.dumps(problem))
        result=self.run_process([self.python,"-B","demo.py","--engine","own","--input",path])
        self.assertNotEqual(result.returncode,0)
        value=json.loads(result.stdout);self.assertEqual(value["status"],"FAIL")
        self.assertIn("LIMIT_EXCEEDED",value["detail"])


if __name__=="__main__":
    result=unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(FirstSuccess))
    passed=result.wasSuccessful() and result.testsRun>=12 and not result.skipped
    print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),
        "errors":len(result.errors),"skipped":len(result.skipped),"failure_diagnostics":result.diagnostics,
        "scope":"Fresh macOS installation, two actual local routing engines and checker-only corruption probes; no human acceptance, Linux/Windows or publication"}))
    sys.exit(0 if passed else 1)
