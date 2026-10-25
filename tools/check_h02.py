"""H02 domain schema, independent evaluation, oracle and negative fixtures."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from conformance.core_contract import ContractError
from conformance.routing import CONFIGURATION, EXECUTION, PROFILE, evaluate, exhaustive_optimum, validate_problem, validate_request, verify_result


FIXTURE = json.loads((ROOT / "cases/routing/basic-matrix.json").read_text())


def request(problem=None):
    return {"core_version":"0.1.0","kind":"request","request_id":"routing-fixture-1",
            "capability":{"id":"routing.reference","version":"0.1.0"},"domain_profile":deepcopy(PROFILE),
            "execution_profile":deepcopy(EXECUTION),"configuration":deepcopy(CONFIGURATION),
            "input":deepcopy(FIXTURE["input"] if problem is None else problem),"budget":{"time_limit_ms":1000}}


def result(req=None):
    req = request() if req is None else req
    return {"core_version":"0.1.0","kind":"result","request_id":req["request_id"],
            "capability":deepcopy(req["capability"]),"domain_profile":deepcopy(PROFILE),"execution_profile":deepcopy(EXECUTION),
            "effective_configuration":deepcopy(CONFIGURATION),"status":"feasible","termination":"completed",
            "solution":deepcopy(FIXTURE["witness"]),"proof":None,
            "metrics":[{"id":"minimize_total_route_cost","role":"optimized","definition":"routing.basic.total_distance.v1",
                        "unit":"meter","source":"engine","status":"evaluated","value":18,"reason":None}],
            "constraints":[{"id":cid,"role":"enforced","definition":"routing.basic."+cid+".v1","unit":unit,
                            "source":"engine","status":"evaluated","violation":0,"satisfied":True,"reason":None}
                           for cid,unit in [("weight_capacity","kg"),("all_visits_once","count")]],
            "provenance":{"implementation":{"id":"fixture","version":"0.1.0"},"engine":{"id":"fixture","version":"0.1.0"},
                          "request_id":req["request_id"],"limitations":["Synthetic result; no real engine execution"]}}


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.problem, self.solution = deepcopy(FIXTURE["input"]), deepcopy(FIXTURE["witness"])

    def assert_code(self, code, function, *args):
        with self.assertRaises(ContractError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_01_known_witness_has_cost_18(self):
        value = evaluate(self.problem, self.solution)
        self.assertTrue(value["feasible"])
        for key in ("total_cost","route_costs","loads"):
            self.assertEqual(value[key], FIXTURE["expected"][key])

    def test_02_exhaustive_oracle_matches_manual_optimum(self):
        self.assertEqual(exhaustive_optimum(self.problem)["optimal_cost"], 18)

    def test_03_greedy_counterexample_is_feasible(self):
        old = json.loads((ROOT / "cases/failure-semantics/greedy-feasible.json").read_text())
        self.problem["visits"] = [{"id":v["id"],"demand":v["amount"]} for v in old["demands"]]
        self.problem["vehicles"] = [{"id":v["id"],"capacity":v["max_capacity"]} for v in old["resources"]]
        ids = ["hub"] + [v["id"] for v in self.problem["visits"]]
        self.problem["matrix"].update(node_ids=ids,values=[[int(i!=j) for j in range(len(ids))] for i in range(len(ids))])
        witness = {"routes":[{"vehicle_id":vid,"visits":vs} for vid,vs in old["witness"].items()]}
        self.assertTrue(evaluate(self.problem,witness)["feasible"])
        self.assertEqual(exhaustive_optimum(self.problem)["optimal_cost"],7)

    def test_04_missing_demand(self):
        del self.problem["visits"][0]["demand"]
        self.assert_code("INVALID_DATA",validate_problem,self.problem)

    def test_05_negative_demand(self):
        self.problem["visits"][0]["demand"]=-1
        self.assert_code("INVALID_DATA",validate_problem,self.problem)

    def test_06_unit_mismatch(self):
        self.problem["matrix"]["unit"]="km"
        self.assert_code("INVALID_DATA",validate_problem,self.problem)

    def test_07_non_integer_distance(self):
        self.problem["matrix"]["values"][0][1]=1.5
        self.assert_code("INVALID_DATA",validate_problem,self.problem)

    def test_08_negative_distance(self):
        self.problem["matrix"]["values"][0][1]=-1
        self.assert_code("INVALID_DATA",validate_problem,self.problem)

    def test_09_duplicate_visit(self):
        self.problem["visits"][1]["id"]="a"
        self.assert_code("DUPLICATE_ID",validate_problem,self.problem)

    def test_10_duplicate_vehicle(self):
        self.problem["vehicles"][1]["id"]="v1"
        self.assert_code("DUPLICATE_ID",validate_problem,self.problem)

    def test_11_missing_matrix_node(self):
        self.problem["matrix"]["node_ids"][-1]="other"
        self.assert_code("MATRIX_NODE_MISMATCH",validate_problem,self.problem)

    def test_12_matrix_shape(self):
        self.problem["matrix"]["values"][0].pop()
        self.assert_code("MATRIX_SHAPE",validate_problem,self.problem)

    def test_13_matrix_diagonal(self):
        self.problem["matrix"]["values"][0][0]=1
        self.assert_code("MATRIX_DIAGONAL",validate_problem,self.problem)

    def test_14_asymmetric_edges_preserved(self):
        self.problem["matrix"]["values"][1][0]=200
        self.solution["routes"][0]["visits"]=["b","a"]
        self.assertEqual(evaluate(self.problem,self.solution)["total_cost"],216)

    def test_15_missing_visit_not_feasible(self):
        self.solution["routes"][0]["visits"].pop()
        value=evaluate(self.problem,self.solution)
        self.assertFalse(value["feasible"])
        self.assertEqual(value["violations"]["all_visits_once"],1)

    def test_16_duplicate_visit_not_feasible(self):
        self.solution["routes"][0]["visits"]=["a","a"]
        self.assertEqual(evaluate(self.problem,self.solution)["violations"]["all_visits_once"],2)

    def test_17_over_capacity_not_feasible(self):
        self.problem["vehicles"][0]["capacity"]=1
        value=evaluate(self.problem,self.solution)
        self.assertFalse(value["feasible"])
        self.assertEqual(value["violations"]["weight_capacity"],1)

    def test_18_unknown_visit_is_not_zero(self):
        self.solution["routes"][0]["visits"]=["missing"]
        self.assert_code("UNKNOWN_VISIT",evaluate,self.problem,self.solution)

    def test_19_missing_vehicle_route(self):
        self.solution["routes"].pop()
        self.assert_code("SOLUTION_VEHICLES",evaluate,self.problem,self.solution)

    def test_20_unsupported_objective_weight(self):
        req=request(); req["configuration"]["objectives"][0]["weight"]=2
        self.assert_code("UNSUPPORTED_CONFIGURATION",validate_request,req)

    def test_21_time_window_is_rejected(self):
        req=request(); req["input"]["visits"][0]["time_window"]=[0,1]
        self.assert_code("INVALID_DATA",validate_request,req)

    def test_22_unsupported_combination(self):
        req=request(); req["configuration"]["constraints"]+=['time_windows']
        self.assert_code("UNSUPPORTED_CONFIGURATION",validate_request,req)

    def test_23_version_mismatch(self):
        req=request(); req["domain_profile"]["version"]="0.2.0"
        self.assert_code("VERSION_MISMATCH",validate_request,req)

    def test_24_fake_async_rejected(self):
        req=request(); req["execution_profile"]["id"]="execution.async"
        self.assert_code("UNSUPPORTED_EXECUTION",validate_request,req)

    def test_25_result_recomputed(self):
        self.assertEqual(verify_result(request(),result())["total_cost"],18)

    def test_26_wrong_engine_objective_caught(self):
        output=result(); output["metrics"][0]["value"]=0
        self.assert_code("EVALUATION_MISMATCH",verify_result,request(),output)

    def test_27_enforced_constraint_not_downgraded(self):
        output=result(); output["constraints"][0]["role"]="evaluated"
        self.assert_code("EVALUATION_MISMATCH",verify_result,request(),output)

    def test_28_result_identity_mismatch(self):
        output=result(); output["capability"]["version"]="0.2.0"
        self.assert_code("RESULT_MISMATCH",verify_result,request(),output)

    def test_29_false_infeasible_proof_caught(self):
        output=result(); output.update(status="infeasible",solution=None,metrics=[],constraints=[],proof={"claim":"infeasible","method":"total-demand-exceeds-total-capacity","scope":"all mandatory visits","evidence":{"claim":True}})
        self.assert_code("UNVERIFIED_PROOF",verify_result,request(),output)

    def test_30_unknown_cannot_have_evaluated_metric(self):
        output=result(); output.update(status="unknown",solution=None,termination="time_limit",constraints=[])
        self.assert_code("EVALUATION_WITHOUT_SOLUTION",verify_result,request(),output)

    def test_31_timeout_unknown_is_preserved(self):
        output=result(); output.update(status="unknown",solution=None,termination="time_limit",metrics=[],constraints=[])
        self.assertIsNone(verify_result(request(),output))

    def test_32_oracle_scope_is_bounded(self):
        self.problem["vehicles"] += [{"id":"v3","capacity":2},{"id":"v4","capacity":2}]
        self.assert_code("ORACLE_SCOPE_EXCEEDED",exhaustive_optimum,self.problem)

    def test_33_empty_unused_route_costs_zero(self):
        self.problem["vehicles"][0]["capacity"]=4
        self.solution["routes"][0]["visits"]=["a","b","c","d"]
        self.solution["routes"][1]["visits"]=[]
        value=evaluate(self.problem,self.solution)
        self.assertTrue(value["feasible"]); self.assertEqual(value["route_costs"]["v2"],0)

    def test_34_capacity_impossible_is_independently_proven(self):
        self.problem["visits"][0]["demand"]=9
        self.assertFalse(exhaustive_optimum(self.problem)["feasible"])
        output=result(); req=request(self.problem)
        output.update(status="infeasible",solution=None,metrics=[],constraints=[],proof={"claim":"infeasible","method":"total-demand-exceeds-total-capacity","scope":"all mandatory visits","evidence":{"total_demand":12,"total_capacity":4}})
        self.assertIsNone(verify_result(req,output))


if __name__ == "__main__":
    result_ = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(RoutingTests))
    passed = result_.wasSuccessful() and result_.testsRun >= 34 and not result_.skipped
    print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result_.testsRun,
                      "failures":len(result_.failures),"errors":len(result_.errors),"skipped":len(result_.skipped),
                      "scope":"routing candidate semantics, independent witness and tiny exhaustive oracle; no API solve"}))
    sys.exit(0 if passed else 1)
