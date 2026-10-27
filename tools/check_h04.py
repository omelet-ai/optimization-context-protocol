"""H04: clean installed App A, real no-key solves, independent oracle and evaluation."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import build
from build_site import run_example
from isolated_candidate import install
from conformance.routing import CONFIGURATION, exhaustive_optimum, verify_result
from conformance.core_contract import ContractError
from safe_test_result import DiagnosticResult

FIXTURE = json.loads((ROOT / "cases/routing/basic-matrix.json").read_text())
WORK = tempfile.TemporaryDirectory(prefix="ocp-h04-clean-")
DIRECTORY = Path(WORK.name)
ARTIFACT = build(DIRECTORY / "dist")
TIMINGS=[]
PYTHON, ENV = install(DIRECTORY, ARTIFACT["wheel"])
shutil.copy2(ROOT / "examples/app-a/main.py", DIRECTORY / "app.py")
(DIRECTORY / "run.py").write_text('''import runpy, socket, sys
def denied(*args, **kwargs):
    raise RuntimeError("Network forbidden during no-key execution")
socket.socket = denied
socket.create_connection = denied
import ocp_routing
class ObservedBackend(ocp_routing.ORToolsBackend):
    def __init__(self):
        super().__init__()
        print("OCP_APP_ENGINE_READY",flush=True)
ocp_routing.ORToolsBackend=ObservedBackend
sys.argv = ["app.py"] + sys.argv[1:]
runpy.run_path("app.py", run_name="__main__")
''')


def request(problem, budget=1000):
    return {"core_version":"0.1.0", "kind":"request", "request_id":"app-a",
            "capability":{"id":"routing.reference", "version":"0.1.0"},
            "domain_profile":{"id":"routing.basic", "version":"0.1.0"},
            "execution_profile":{"id":"execution.sync", "version":"0.1.0"},
            "configuration":deepcopy(CONFIGURATION), "input":problem, "budget":{"time_limit_ms":budget}}


def run(problem, budget=1000, raw=None):
    (DIRECTORY / "input.json").write_text(json.dumps(problem) if raw is None else raw)
    argv=[str(PYTHON), "-I", "-B", "run.py", "--input", "input.json", "--time-limit-ms", str(budget)]
    if raw is not None:
        # Malformed JSON is rejected before backend construction, so it has no readiness line.
        output=subprocess.run(argv,cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=15)
    else:
        output,timing=run_example(argv,cwd=DIRECTORY,env=ENV,startup_timeout=60,execution_timeout=15,
                                 ready_line=b"OCP_APP_ENGINE_READY\n",phase_prefix="app")
        TIMINGS.append(timing)
    if output.returncode not in (0, 2):
        raise AssertionError(output.stderr)
    result = json.loads(output.stdout)
    if (result["kind"] == "failure") != (output.returncode == 2):
        raise AssertionError("CLI failure exit code mismatch")
    return result


class InstalledAppTests(unittest.TestCase):
    def test_01_clean_package_origin(self):
        command = "import json, sys, ocp_candidate, ocp_routing, ortools; print(json.dumps({'prefix':sys.prefix,'origins':[m.__file__ for m in (ocp_candidate,ocp_routing,ortools)]}))"
        out = subprocess.check_output([str(PYTHON), "-I", "-B", "-c", command], cwd=DIRECTORY, env=ENV, text=True)
        data = json.loads(out)
        self.assertEqual(Path(data["prefix"]), DIRECTORY / "venv")
        self.assertTrue(all(Path(p).is_relative_to(DIRECTORY / "venv") for p in data["origins"]))
        self.assertIn("include-system-site-packages = false", (DIRECTORY / "venv/pyvenv.cfg").read_text())

    def test_02_offline_no_key_sample(self):
        problem = FIXTURE["input"]
        result = run(problem)
        self.assertEqual(verify_result(request(problem), result)["total_cost"], 18)

    def test_03_user_supplied_directed_matrix(self):
        problem = deepcopy(FIXTURE["input"])
        problem["matrix"]["values"][0][1] = 91
        problem["matrix"]["values"][2][0] = 17
        result = run(problem)
        measured = verify_result(request(problem), result)
        self.assertTrue(measured["feasible"])
        self.assertGreaterEqual(measured["total_cost"], exhaustive_optimum(problem)["optimal_cost"])

    def test_04_matrix_index_permutation(self):
        problem = deepcopy(FIXTURE["input"])
        old = deepcopy(problem["matrix"]); order = [4, 2, 0, 1, 3]
        problem["matrix"]["node_ids"] = [old["node_ids"][i] for i in order]
        problem["matrix"]["values"] = [[old["values"][i][j] for j in order] for i in order]
        self.assertEqual(verify_result(request(problem), run(problem))["total_cost"], 18)

    def test_05_single_vehicle_capacity_real(self):
        problem = deepcopy(FIXTURE["input"])
        problem["vehicles"] = [{"id":"single", "capacity":4}]
        measured = verify_result(request(problem), run(problem))
        self.assertEqual(measured["loads"], {"single":4})

    def test_06_single_vehicle_overload_proven(self):
        problem = deepcopy(FIXTURE["input"])
        problem["vehicles"] = [{"id":"single", "capacity":3}]
        result = run(problem)
        self.assertEqual(result["status"], "infeasible")
        verify_result(request(problem), result)

    def test_07_greedy_counterexample_real_solver(self):
        visits = [{"id":str(i), "demand":d} for i, d in enumerate([3,3,2,2,2])]
        nodes = ["hub"] + [v["id"] for v in visits]
        problem = {"depot":"hub", "load_unit":"kg", "visits":visits, "vehicles":[{"id":str(i),"capacity":6} for i in range(2)],
                   "matrix":{"node_ids":nodes,"unit":"meter","model":"explicit_matrix","rounding":"none",
                             "values":[[int(i != j) for j in range(6)] for i in range(6)]}}
        self.assertEqual(verify_result(request(problem), run(problem))["total_cost"], 7)

    def test_08_seeded_tiny_instances_against_oracle(self):
        rng = random.Random(20261024)
        for _ in range(8):
            problem = deepcopy(FIXTURE["input"])
            problem["matrix"]["values"] = [[0 if i==j else rng.randint(1,99) for j in range(5)] for i in range(5)]
            result = run(problem)
            measured = verify_result(request(problem), result)
            oracle = exhaustive_optimum(problem)
            self.assertGreaterEqual(measured["total_cost"], oracle["optimal_cost"])
            self.assertEqual(result["status"], "feasible")
            self.assertIsNone(result["proof"])

    def test_09_packing_failure_is_unknown_not_infeasible(self):
        problem = deepcopy(FIXTURE["input"])
        problem["visits"] = problem["visits"][:3]
        for visit in problem["visits"]: visit["demand"] = 2
        problem["vehicles"] = [{"id":"v1","capacity":3},{"id":"v2","capacity":3}]
        problem["matrix"]["node_ids"] = problem["matrix"]["node_ids"][:4]
        problem["matrix"]["values"] = [row[:4] for row in problem["matrix"]["values"][:4]]
        result = run(problem, 30)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["solution"])
        self.assertFalse(exhaustive_optimum(problem)["feasible"])
        verify_result(request(problem, 30), result)

    def test_10_invalid_own_input_fails(self):
        problem = deepcopy(FIXTURE["input"]); del problem["matrix"]
        self.assertEqual(run(problem)["error"]["code"], "INVALID_DATA")

    def test_11_duplicate_json_does_not_overwrite(self):
        self.assertEqual(run(None, raw='{"depot":"a","depot":"b"}')["kind"], "failure")

    def test_12_real_one_ms_budget_no_false_proof(self):
        problem = deepcopy(FIXTURE["input"])
        result = run(problem, 1)
        self.assertIn(result["status"], {"feasible", "unknown"})
        self.assertIsNone(result["proof"])
        verify_result(request(problem, 1), result)

    def test_14_native_backend_ready_before_first_request(self):
        command = "import sys; from ocp_routing import ORToolsBackend; assert 'ortools.constraint_solver.pywrapcp' not in sys.modules; backend=ORToolsBackend(); assert 'ortools.constraint_solver.pywrapcp' in sys.modules; print('ready')"
        result=subprocess.run([str(PYTHON),"-I","-B","-c",command],cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.strip(),"ready")

    def test_13_failure_diagnostics_preserve_location_without_data(self):
        marker="synthetic-sensitive-input"
        class Faults(unittest.TestCase):
            def test_01_assertion(self):self.fail(marker)
            def test_02_timeout(self):
                with patch(__name__+".run_example",side_effect=subprocess.TimeoutExpired(marker,15)):
                    run(FIXTURE["input"])
            def test_03_json(self):
                response=subprocess.CompletedProcess([],0,marker,"")
                with patch(__name__+".run_example",return_value=(response,{})):run(FIXTURE["input"])
            def test_04_contract(self):raise ContractError(marker)
        result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=DiagnosticResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Faults))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual([(d["test_number"],d["kind"],d["category"]) for d in result.diagnostics],
                         [(1,"failure","assertion"),(2,"error","subprocess_timeout"),
                          (3,"error","invalid_json"),(4,"error","contract")])
        self.assertNotIn(marker,json.dumps(result.diagnostics))
        self.assertTrue(all(type(d["elapsed_ms"]) is int and d["elapsed_ms"]>=0 for d in result.diagnostics))
        class FixtureFault(unittest.TestCase):
            @classmethod
            def setUpClass(cls):raise subprocess.TimeoutExpired(marker,30)
            def test_01_never_runs(self):self.fail("Fixture failure must prevent execution")
        fixture=unittest.TextTestRunner(stream=io.StringIO(),resultclass=DiagnosticResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(FixtureFault))
        self.assertEqual(fixture.testsRun,0)
        self.assertEqual(len(fixture.errors),1)
        self.assertEqual(fixture.diagnostics[0]["test_number"],10000)
        self.assertEqual(fixture.diagnostics[0]["category"],"subprocess_timeout")
        self.assertNotIn(marker,json.dumps(fixture.diagnostics))

    def test_15_cold_start_and_execution_limits_remain_distinct(self):
        for phase,code in (("app_engine_startup","import time;time.sleep(10)"),
                           ("app_example_execution","import time;print('OCP_APP_ENGINE_READY',flush=True);time.sleep(10)")):
            with self.subTest(phase=phase):
                children=[];original=subprocess.Popen
                def observe(*args,**kwargs):
                    child=original(*args,**kwargs);children.append(child);return child
                with patch.object(subprocess,"Popen",side_effect=observe),self.assertRaises(subprocess.TimeoutExpired) as caught:
                    run_example([sys.executable,"-B","-c",code],env=ENV,cwd=DIRECTORY,
                                startup_timeout=2 if phase.endswith("execution") else .2,execution_timeout=.2,
                                ready_line=b"OCP_APP_ENGINE_READY\n",phase_prefix="app")
                self.assertEqual(len(children),1);self.assertIsNotNone(children[0].poll())
                self.assertEqual(caught.exception.ocp_phase,phase)
                diagnostics=DiagnosticResult(io.StringIO(),True,1)
                diagnostics.record(self,(type(caught.exception),caught.exception,caught.exception.__traceback__),"error")
                self.assertEqual(diagnostics.diagnostics[0]["phase"],phase)

    def test_16_ready_is_not_a_successful_result(self):
        with self.assertRaises(RuntimeError):
            run_example([sys.executable,"-c","raise SystemExit(2)"],env=ENV,cwd=DIRECTORY,
                        ready_line=b"OCP_APP_ENGINE_READY\n",phase_prefix="app")
        output,_=run_example([sys.executable,"-c","print('OCP_APP_ENGINE_READY',flush=True);raise SystemExit(9)"],
                             env=ENV,cwd=DIRECTORY,ready_line=b"OCP_APP_ENGINE_READY\n",phase_prefix="app")
        self.assertEqual(output.returncode,9)


if __name__ == "__main__":
    try:
        result = unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstalledAppTests))
        passed = result.wasSuccessful() and not result.skipped and result.testsRun >= 16
        print(json.dumps({"status":"PASS" if passed else "FAIL", "tests_run":result.testsRun,
                          "failures":len(result.failures), "errors":len(result.errors), "skipped":len(result.skipped),
                          "failure_diagnostics":result.diagnostics,
                          "cold_process_timings":[value for value in TIMINGS if value],
                          "artifact_sha256":ARTIFACT["sha256"], "versions":{"core":"0.1.0","routing.basic":"0.1.0","ortools":"9.15.6755","seed":"20261024"},
                          "scope":"Clean offline wheel install, App A with caller inputs, socket-denied no-key OR-Tools, tiny oracle and injected diagnostic failures; no remote engine or external-user acceptance"}))
    finally:
        WORK.cleanup()
    sys.exit(0 if passed else 1)
