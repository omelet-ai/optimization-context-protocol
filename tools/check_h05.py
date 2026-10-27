"""H05 conformance runner fault detection and non-routing fixture coverage."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from conformance.core_contract import ContractError, validate_message
from conformance.runner import verify_bundle
from conformance.assignment import verify_result as assignment_result
from check_h02 import request, result

ASSIGNMENT = json.loads((ROOT / "cases/assignment/fixture.json").read_text())
ARTIFACT = b"synthetic-conformance-test-artifact-not-an-engine"


def bundle(req=None, output=None):
    output = result() if output is None else output
    return {"artifact_sha256":hashlib.sha256(ARTIFACT).hexdigest(),"implementation":output["provenance"]["implementation"],
            "cases":[{"id":"sample", "request":request() if req is None else req,"response":output}]}


class ConformanceTests(unittest.TestCase):
    def assert_rejected(self, data):
        try:
            self.assertEqual(verify_bundle(data, ARTIFACT)["status"], "FAIL")
        except ContractError:
            pass

    def test_01_valid_routing_and_bounded_report(self):
        output = verify_bundle(bundle(), ARTIFACT)
        self.assertEqual(output["status"], "PASS")
        validate_message(output["report"])
        self.assertEqual(output["report"]["checks"][-2]["status"], "NOT_TESTED")

    def test_02_second_domain_schema_requirements_and_result(self):
        for key in ("capability","requirements","request","result"): validate_message(ASSIGNMENT[key])
        self.assertEqual(assignment_result(ASSIGNMENT["request"], ASSIGNMENT["result"])["total_cost"],5)
        self.assertEqual(verify_bundle(bundle(ASSIGNMENT["request"],ASSIGNMENT["result"]), ARTIFACT)["status"],"PASS")

    def test_03_wrong_cost(self):
        out=result(); out["metrics"][0]["value"]=0; self.assert_rejected(bundle(output=out))

    def test_04_wrong_unit(self):
        out=result(); out["metrics"][0]["unit"]="km"; self.assert_rejected(bundle(output=out))

    def test_05_missing_visit(self):
        out=result(); out["solution"]["routes"][0]["visits"].pop(); self.assert_rejected(bundle(output=out))

    def test_06_over_capacity(self):
        out=result(); out["solution"]["routes"][0]["visits"]+=out["solution"]["routes"][1]["visits"]; out["solution"]["routes"][1]["visits"]=[]
        self.assert_rejected(bundle(output=out))

    def test_07_configuration_drift(self):
        out=result(); out["effective_configuration"]["objectives"][0]["weight"]=2; self.assert_rejected(bundle(output=out))

    def test_08_false_optimal(self):
        out=result(); out["status"]="optimal"; self.assert_rejected(bundle(output=out))

    def test_09_false_infeasible(self):
        out=result(); out.update(status="infeasible",solution=None,metrics=[],constraints=[],proof={"claim":"infeasible","method":"total-demand-exceeds-total-capacity","scope":"all","evidence":{"claimed":True}})
        self.assert_rejected(bundle(output=out))

    def test_10_timeout_is_not_infeasible(self):
        out=result(); out.update(status="infeasible",termination="time_limit",solution=None); self.assert_rejected(bundle(output=out))

    def test_11_null_as_zero(self):
        out=result(); out["metrics"][0].update(status="not_evaluated",value=0,reason="test"); self.assert_rejected(bundle(output=out))

    def test_12_unsupported_domain_fails(self):
        req=request(); req["domain_profile"]["id"]="new.domain"; self.assert_rejected(bundle(req))

    def test_13_artifact_mismatch(self):
        data=bundle(); data["artifact_sha256"]="0"*64; self.assert_rejected(data)

    def test_14_implementation_mismatch(self):
        data=bundle(); data["implementation"]={"id":"other","version":"0.1.0"}; self.assert_rejected(data)

    def test_15_empty_cases(self):
        data=bundle(); data["cases"]=[]; self.assert_rejected(data)

    def test_16_duplicate_case_ids(self):
        data=bundle(); data["cases"]*=2; self.assert_rejected(data)

    def test_17_unknown_optimized_metric(self):
        out=result(); metric=deepcopy(out["metrics"][0]); metric["id"]="ignored-objective"; out["metrics"].append(metric); self.assert_rejected(bundle(output=out))

    def test_18_unknown_enforced_constraint(self):
        out=result(); item=deepcopy(out["constraints"][0]); item["id"]="ignored-constraint"; out["constraints"].append(item); self.assert_rejected(bundle(output=out))

    def test_19_assignment_duplicate_worker(self):
        out=deepcopy(ASSIGNMENT["result"]); out["solution"]["assignments"][1][1]="y"
        self.assert_rejected(bundle(ASSIGNMENT["request"],out))

    def test_20_assignment_wrong_cost(self):
        out=deepcopy(ASSIGNMENT["result"]); out["metrics"][0]["value"]=17
        self.assert_rejected(bundle(ASSIGNMENT["request"],out))

    def test_21_assignment_matrix_dimensions(self):
        req=deepcopy(ASSIGNMENT["request"]); req["input"]["costs"][0].pop()
        self.assert_rejected(bundle(req,ASSIGNMENT["result"]))

    def test_22_cli_real_files_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); (path/"artifact").write_bytes(ARTIFACT)
            for expected,data in [(0,bundle()),(1,{})]:
                (path/"bundle.json").write_text(json.dumps(data))
                process=subprocess.run([sys.executable,"-B","-m","conformance.runner","--bundle",str(path/"bundle.json"),"--artifact",str(path/"artifact")],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(process.returncode,expected)
                self.assertEqual(json.loads(process.stdout)["status"],"PASS" if expected==0 else "FAIL")

    def test_23_runner_does_not_import_provider(self):
        for path in (ROOT/"conformance").glob("*.py"):
            for name in ("import ocp_routing","from ocp_routing","import ortools","from ortools","reference/imported-foundry"):
                self.assertNotIn(name,path.read_text())

    def test_24_total_capacity_proof_numbers_must_match_input(self):
        req=request()
        for vehicle in req["input"]["vehicles"]: vehicle["capacity"]=1
        out=result();out.update(status="infeasible",solution=None,metrics=[],constraints=[],
            proof={"claim":"infeasible","method":"total-demand-exceeds-total-capacity",
                   "scope":"all mandatory visits","evidence":{"total_demand":4,"total_capacity":2}})
        self.assertEqual(verify_bundle(bundle(req,out),ARTIFACT)["status"],"PASS")
        for evidence in ({"total_demand":999,"total_capacity":998},{"total_demand":4,"total_capacity":1},
                         {"total_capacity":2},{"total_demand":4.0,"total_capacity":2}):
            with self.subTest(evidence=evidence):
                bad=deepcopy(out);bad["proof"]["evidence"]=evidence;self.assert_rejected(bundle(req,bad))

    def test_25_individual_capacity_proof_numbers_must_match_input(self):
        req=request()
        for vehicle in req["input"]["vehicles"]: vehicle["capacity"]=1
        for visit in req["input"]["visits"]: visit["demand"]=0
        req["input"]["visits"][0]["demand"]=2
        out=result();out.update(status="infeasible",solution=None,metrics=[],constraints=[],
            proof={"claim":"infeasible","method":"individual-demand-exceeds-all-capacities",
                   "scope":"all mandatory visits","evidence":{"maximum_demand":2,"maximum_capacity":1}})
        self.assertEqual(verify_bundle(bundle(req,out),ARTIFACT)["status"],"PASS")
        for evidence in ({"maximum_demand":9,"maximum_capacity":8},{"maximum_demand":2,"maximum_capacity":True},
                         {"maximum_demand":2},{"maximum_demand":2,"maximum_capacity":1.0}):
            with self.subTest(evidence=evidence):
                bad=deepcopy(out);bad["proof"]["evidence"]=evidence;self.assert_rejected(bundle(req,bad))


if __name__ == "__main__":
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ConformanceTests))
    passed=result.wasSuccessful() and result.testsRun>=25 and not result.skipped
    print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
                      "versions":{"suite":"ocp.transcript@0.1.0","assignment.fixture":"0.1.0"},
                      "scope":"Independent transcript runner, intentional defective outputs and second-domain fixtures; no assignment engine execution"}))
    sys.exit(0 if passed else 1)
