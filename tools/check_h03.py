"""H03 real OR-Tools port, generic client and negative adapter checks."""

from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tools"))
from build_candidate import build
from conformance.core_contract import validate_message
from conformance.routing import verify_result


WORK=tempfile.TemporaryDirectory(prefix="ocp-h03-")
ARTIFACT=build(WORK.name)
sys.path.insert(0,ARTIFACT["wheel"])
from ocp_candidate import Client, OCPError, parse_json
from ocp_routing import RoutingAdapter, ORToolsBackend
from ocp_routing.ortools_backend import Outcome

FIXTURE=json.loads((ROOT/"cases/routing/basic-matrix.json").read_text())


class FakeBackend:
    """Fault injection only; never counted as real engine execution."""
    name="injected-test-backend"
    version="0.1.0"
    def __init__(self, callback):
        self.callback=callback
        self.calls=0
    def solve(self, problem, budget):
        self.calls+=1
        return self.callback(problem,budget)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter=RoutingAdapter(ORToolsBackend())
        self.client=Client(self.adapter)
        self.problem=deepcopy(FIXTURE["input"])

    def test_01_real_library_solve_and_independent_evaluation(self):
        req=self.client.request(self.problem,request_id="real-1")
        output=self.client.execute(self.problem,request_id="real-1")
        self.assertEqual(output["kind"],"result")
        self.assertEqual(output["status"],"feasible")
        self.assertEqual(output["provenance"]["engine"],{"id":"ortools.routing","version":"9.15.6755"})
        self.assertEqual(verify_result(req,output)["total_cost"],18)
        self.assertTrue(all(item["source"] == "engine" for item in output["metrics"] + output["constraints"]))

    def test_02_describe_matches_core(self):
        validate_message(self.adapter.describe())

    def test_03_requirements_preserve_selection(self):
        output=self.client.requirements()
        validate_message(output)
        self.assertEqual(output["effective_configuration"],FIXTURE["configuration"])
        self.assertIn("/visits",[r["path"] for r in output["required_fields"]])

    def test_04_validate_does_not_call_engine(self):
        backend=FakeBackend(lambda p,b: (_ for _ in ()).throw(AssertionError("should not solve")))
        adapter=RoutingAdapter(backend)
        response=adapter.validate(Client(adapter).request(self.problem))
        self.assertTrue(response["valid"]); self.assertEqual(backend.calls,0)

    def test_05_weight_rejected_before_solve(self):
        backend=FakeBackend(lambda p,b: None); client=Client(RoutingAdapter(backend))
        config=deepcopy(FIXTURE["configuration"]); config["objectives"][0]["weight"]=2
        self.assertEqual(client.execute(self.problem,configuration=config)["error"]["code"],"UNSUPPORTED_CONFIGURATION")
        self.assertEqual(backend.calls,0)

    def test_06_missing_data_rejected(self):
        del self.problem["visits"][0]["demand"]
        self.assertEqual(self.client.execute(self.problem)["error"]["code"],"INVALID_DATA")

    def test_07_direct_adapter_checks_version(self):
        req=self.client.request(self.problem); req["capability"]["version"]="0.2.0"
        self.assertEqual(self.adapter.execute(req)["error"]["code"],"VERSION_MISMATCH")

    def test_08_async_is_not_emulated(self):
        req=self.client.request(self.problem); req["execution_profile"]["id"]="execution.async"
        self.assertEqual(self.adapter.execute(req)["error"]["code"],"UNSUPPORTED_EXECUTION")

    def test_09_required_extension_is_rejected(self):
        req=self.client.request(self.problem); req["extensions"]=[{"id":"unknown","version":"1","required":True,"value":{}}]
        self.assertEqual(self.adapter.execute(req)["error"]["code"],"UNSUPPORTED_EXTENSION")

    def test_10_budget_not_silently_clipped(self):
        self.assertEqual(self.client.execute(self.problem,time_limit_ms=5001)["error"]["code"],"LIMIT_EXCEEDED")

    def test_11_input_is_not_mutated(self):
        original=deepcopy(self.problem)
        self.client.execute(self.problem)
        self.assertEqual(self.problem,original)

    def test_12_engine_exception_is_sanitized(self):
        def crash(p,b): raise RuntimeError("synthetic-secret-must-not-escape")
        output=Client(RoutingAdapter(FakeBackend(crash))).execute(self.problem)
        self.assertEqual(output["error"]["code"],"EXECUTION_ERROR")
        self.assertNotIn("synthetic-secret",json.dumps(output))

    def test_13_search_failure_is_unknown(self):
        client=Client(RoutingAdapter(FakeBackend(lambda p,b:Outcome(None,"search_exhausted",None))))
        output=client.execute(self.problem,request_id="unknown")
        self.assertEqual(output["status"],"unknown")
        self.assertIsNone(verify_result(client.request(self.problem,request_id="unknown"),output))

    def test_14_timeout_mapping_is_unknown(self):
        client=Client(RoutingAdapter(FakeBackend(lambda p,b:Outcome(None,"time_limit",None))))
        output=client.execute(self.problem)
        self.assertEqual((output["status"],output["termination"]),("unknown","time_limit"))
        self.assertEqual(output["metrics"],[])

    def test_15_engine_wrong_cost_is_rejected(self):
        client=Client(RoutingAdapter(FakeBackend(lambda p,b:Outcome(deepcopy(FIXTURE["witness"]),"completed",0))))
        self.assertEqual(client.execute(self.problem)["error"]["code"],"INVALID_ENGINE_RESULT")

    def test_16_engine_missing_visit_is_rejected(self):
        solution=deepcopy(FIXTURE["witness"]); solution["routes"][0]["visits"].pop()
        client=Client(RoutingAdapter(FakeBackend(lambda p,b:Outcome(solution,"completed",18))))
        self.assertEqual(client.execute(self.problem)["error"]["code"],"INVALID_ENGINE_RESULT")

    def test_17_analytic_infeasibility_has_verified_proof(self):
        self.problem["visits"][0]["demand"]=9
        req=self.client.request(self.problem,request_id="proof")
        output=self.client.execute(self.problem,request_id="proof")
        self.assertEqual(output["status"],"infeasible")
        self.assertIsNone(verify_result(req,output))

    def test_18_client_rejects_changed_request_identity(self):
        adapter=self.adapter
        execute=adapter.execute
        def changed(req):
            output=execute(req); output["request_id"]="other"
            return output
        adapter.execute=changed
        self.assertEqual(self.client.execute(self.problem)["kind"],"failure")

    def test_19_client_rejects_changed_configuration(self):
        execute=self.adapter.execute
        def changed(req):
            output=execute(req); output["effective_configuration"]["objectives"][0]["weight"]=2
            return output
        self.adapter.execute=changed
        self.assertEqual(self.client.execute(self.problem)["error"]["code"],"INVALID_RESPONSE")

    def test_20_standalone_wheel_has_no_workspace_import(self):
        with zipfile.ZipFile(ARTIFACT["wheel"]) as archive:
            for name in archive.namelist():
                self.assertFalse(name.startswith((".private/","reference/","conformance/")))
                if name.endswith(".py"):
                    source=archive.read(name).decode()
                    for forbidden in ("from conformance", "import conformance", "imported-foundry", "/Users/", "sys.path.insert"):
                        self.assertNotIn(forbidden,source)

    def test_21_bundled_schemas_match_canonical_hashes(self):
        import hashlib
        with zipfile.ZipFile(ARTIFACT["wheel"]) as archive:
            manifest=json.loads(archive.read("ocp_candidate/schema-manifest.json"))
            self.assertEqual(manifest,ARTIFACT["schemas"])
            for name,expected in manifest.items():
                self.assertEqual(hashlib.sha256(archive.read("ocp_candidate/schemas/"+name)).hexdigest(),expected)

    def test_22_duplicate_json_key_rejected(self):
        with self.assertRaises(OCPError): parse_json('{"id":"a","id":"b"}')

    def test_23_nonfinite_input_is_failure(self):
        self.problem["visits"][0]["demand"]=float("nan")
        output=self.client.execute(self.problem)
        self.assertEqual(output["kind"],"failure"); validate_message(output)

    def test_24_empty_request_id_not_silently_replaced(self):
        output=self.client.execute(self.problem,request_id="")
        self.assertEqual(output["kind"],"failure"); validate_message(output)

    def test_25_provider_evaluation_does_not_claim_independent_origin(self):
        response=self.adapter.evaluate(self.client.request(self.problem),FIXTURE["witness"])
        validate_message(response)
        self.assertTrue(all(item["source"] == "engine" for item in response["metrics"] + response["constraints"]))
        self.assertIn("reuses provider logic", response["limitations"][0])
        # A corrupted solution must still be evaluated, without claiming independence.
        broken = deepcopy(FIXTURE["witness"])
        broken["routes"][0]["visits"].pop()
        checked = self.adapter.evaluate(self.client.request(self.problem), broken)
        self.assertTrue(any(not item["satisfied"] for item in checked["constraints"]))

    def test_26_requirements_reject_unsupported_parameters(self):
        config=deepcopy(FIXTURE["configuration"]); config["parameters"]["seed"]=1
        self.assertEqual(self.client.requirements(config)["kind"],"failure")

    def test_27_unsafe_float_integer_rejected(self):
        with self.assertRaises(OCPError): parse_json('{"x":1e16}')

    def test_28_duplicate_metric_response_rejected(self):
        execute=self.adapter.execute
        def duplicated(req):
            output=execute(req); output["metrics"]*=2
            return output
        self.adapter.execute=duplicated
        self.assertEqual(self.client.execute(self.problem)["kind"],"failure")


if __name__ == "__main__":
    try:
        result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdapterTests))
        passed=result.wasSuccessful() and result.testsRun>=26 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),
                          "errors":len(result.errors),"skipped":len(result.skipped),"artifact_sha256":ARTIFACT["sha256"],
                          "versions":{"core":"0.1.0","routing.basic":"0.1.0","sdk":"0.1.0","ortools":importlib.metadata.version("ortools")},
                          "scope":"Real OR-Tools library call and fault-injected client/adapter checks; not external trial"}))
    finally:
        WORK.cleanup()
    sys.exit(0 if passed else 1)
