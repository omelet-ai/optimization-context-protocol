"""H04: clean installed App A, real no-key solves, independent oracle and evaluation."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_candidate import build
from isolated_candidate import install
from conformance.routing import CONFIGURATION, exhaustive_optimum, verify_result

FIXTURE = json.loads((ROOT / "cases/routing/basic-matrix.json").read_text())
WORK = tempfile.TemporaryDirectory(prefix="ocp-h04-clean-")
DIRECTORY = Path(WORK.name)
ARTIFACT = build(DIRECTORY / "dist")
PYTHON, ENV = install(DIRECTORY, ARTIFACT["wheel"])
shutil.copy2(ROOT / "examples/app-a/main.py", DIRECTORY / "app.py")
(DIRECTORY / "run.py").write_text('''import runpy, socket, sys
def denied(*args, **kwargs):
    raise RuntimeError("Network forbidden during no-key execution")
socket.socket = denied
socket.create_connection = denied
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
    output = subprocess.run([str(PYTHON), "-I", "-B", "run.py", "--input", "input.json", "--time-limit-ms", str(budget)],
                            cwd=DIRECTORY, env=ENV, capture_output=True, text=True, timeout=15)
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


if __name__ == "__main__":
    try:
        result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(InstalledAppTests))
        passed = result.wasSuccessful() and not result.skipped and result.testsRun >= 12
        print(json.dumps({"status":"PASS" if passed else "FAIL", "tests_run":result.testsRun,
                          "failures":len(result.failures), "errors":len(result.errors), "skipped":len(result.skipped),
                          "artifact_sha256":ARTIFACT["sha256"], "versions":{"core":"0.1.0","routing.basic":"0.1.0","ortools":"9.15.6755","seed":"20261024"},
                          "scope":"Clean offline wheel install, App A with caller inputs, socket-denied no-key OR-Tools and tiny oracle; no remote engine or external-user acceptance"}))
    finally:
        WORK.cleanup()
    sys.exit(0 if passed else 1)
