"""Coordinates candidate and adversarial upstream mapping; live Foundry is checked by H16."""
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_candidate import build
from conformance import coordinates
from conformance.core_contract import ContractError, validate_message

WORK=tempfile.TemporaryDirectory(prefix="ocp-h15-")
ARTIFACT=build(WORK.name); sys.path.insert(0,ARTIFACT["wheel"])
from ocp_candidate import Client, OCPError
from ocp_routing import ORToolsBackend
from ocp_routing.coordinates import CoordinatesAdapter, CoordinateLibraryBackend, to_matrix, check_input
from ocp_routing.foundry import FoundryBackend, FoundryCoordinatesAdapter, document_hash
from ocp_routing.ortools_backend import Outcome

FIXTURE=json.loads((ROOT/"cases/routing/coordinates.json").read_text())


def reference(): return CoordinatesAdapter(CoordinateLibraryBackend(ORToolsBackend()))


def request(adapter=None, rid="coordinate-test", budget=1000):
    value=(adapter or reference()).describe()
    return {"core_version":"0.1.0","kind":"request","request_id":rid,"capability":value["capability"],
            "domain_profile":value["domain_profile"],"execution_profile":{"id":"execution.sync","version":"0.1.0"},
            "configuration":value["defaults"],"input":deepcopy(FIXTURE["input"]),"budget":{"time_limit_ms":budget}}


CATALOG={"contractVersion":"1","problemType":"standard-routing","apiVersion":"1.0","catalogVersion":"1.4.0",
         "compilerVersion":"1.2.0","solver":"standard-vrp","catalogDigest":"a"*64}


def fake_backend():
    with patch.object(FoundryBackend,"_call",return_value=deepcopy(CATALOG)):
        return FoundryBackend("http://127.0.0.1:9","test-service-secret", "a"*64,document_hash(CATALOG))


class CoordinateTests(unittest.TestCase):
    def test_24_main_catalog_requires_explicit_selection(self):
        catalog=dict(CATALOG,catalogVersion="1.3.0")
        with patch.object(FoundryBackend,"_call",return_value=catalog):
            with self.assertRaises(OCPError) as error:
                FoundryBackend("http://127.0.0.1:9","test-secret","a"*64,document_hash(catalog))
            self.assertEqual(error.exception.code,"UPSTREAM_VERSION_MISMATCH")
            backend=FoundryBackend("http://127.0.0.1:9","test-secret","a"*64,document_hash(catalog),catalog_version="1.3.0")
        self.assertEqual(backend.scoped("owner","request").catalog_version,"1.3.0")
        self.assertEqual(backend.payload(FIXTURE["input"],1000),fake_backend().payload(FIXTURE["input"],1000))

    def test_25_selected_catalog_never_falls_forward(self):
        with patch.object(FoundryBackend,"_call",return_value=CATALOG):
            with self.assertRaises(OCPError) as error:
                FoundryBackend("http://127.0.0.1:9","test-secret","a"*64,document_hash(CATALOG),catalog_version="1.3.0")
            self.assertEqual(error.exception.code,"UPSTREAM_VERSION_MISMATCH")

    def test_26_unreviewed_version_rejected_without_network(self):
        with patch.object(FoundryBackend,"_call") as call:
            for version in ("1.2.0","1.5.0","latest",None,True):
                with self.assertRaises(ValueError):
                    FoundryBackend("http://127.0.0.1:9","test-secret","a"*64,"b"*64,catalog_version=version)
            call.assert_not_called()

    def test_27_main_catalog_full_pin_is_still_mandatory(self):
        catalog=dict(CATALOG,catalogVersion="1.3.0")
        with patch.object(FoundryBackend,"_call",return_value=catalog):
            backend=FoundryBackend("http://127.0.0.1:9","test-secret","a"*64,document_hash(catalog),catalog_version="1.3.0")
        for change in ({"catalogDigest":"c"*64},{"newSemanticField":True},{"compilerVersion":"1.3.0"}):
            with patch.object(backend,"_call",return_value=dict(catalog,**change)):
                with self.assertRaises(OCPError) as error:backend.check_catalog()
                self.assertEqual(error.exception.code,"CATALOG_CHANGED")

    def test_28_legacy_default_identity_is_unchanged(self):
        legacy=fake_backend()
        with patch.object(FoundryBackend,"_call",return_value=CATALOG):
            explicit=FoundryBackend("http://127.0.0.1:9","test-service-secret","a"*64,document_hash(CATALOG),catalog_version="1.4.0")
        self.assertEqual(FoundryCoordinatesAdapter(legacy).describe(),FoundryCoordinatesAdapter(explicit).describe())

    def test_01_manual_witness_and_exhaustive_oracle(self):
        self.assertEqual(coordinates.evaluate(FIXTURE["input"],FIXTURE["witness"])["total_cost"],11358)
        self.assertEqual(coordinates.exhaustive_optimum(FIXTURE["input"])["optimal_cost"],11358)

    def test_02_actual_reference_and_independent_result(self):
        adapter=reference(); req=request(adapter); result=adapter.execute(req)
        self.assertEqual(coordinates.verify_result(req,result)["total_cost"],11358)

    def test_03_equator_distance_and_zero(self):
        p=deepcopy(FIXTURE["input"])
        p["depot"]["location"]={"latitude":0,"longitude":0}
        p["visits"][0]["location"]={"latitude":0,"longitude":1}
        matrix=to_matrix(p)["matrix"]["values"]
        self.assertEqual(matrix[0][1],111195); self.assertEqual(matrix[0][0],0)

    def test_04_random_and_extreme_distance_implementations(self):
        rng=random.Random(415)
        for _ in range(30):
            p=deepcopy(FIXTURE["input"])
            for point in [p["depot"],*p["visits"]]:
                point["location"]={"latitude":round(rng.uniform(-85,85),6),"longitude":round(rng.uniform(-180,180),6)}
            self.assertEqual(to_matrix(p),coordinates.to_matrix(p))
        p=deepcopy(FIXTURE["input"])
        for point in [p["depot"],*p["visits"]]:point["location"]={"latitude":0,"longitude":0}
        p["visits"][0]["location"]["latitude"]=1e-9
        self.assertEqual(to_matrix(p),coordinates.to_matrix(p))
        self.assertEqual(to_matrix(p)["matrix"]["values"][0][1],1)

    def test_05_coordinate_shape_and_units_rejected(self):
        for mutation in [lambda p:p["distance"].update(rounding="round"),lambda p:p["distance"].update(earth_radius_m=6378137),
                         lambda p:p["depot"]["location"].update(latitude=86),lambda p:p["depot"]["location"].update(longitude=181),
                         lambda p:p["depot"]["location"].update(latitude=True),lambda p:p.update(matrix={}),
                         lambda p:p.update(load_unit="lb"),lambda p:p["visits"][0].update(time_window=[0,1])]:
            p=deepcopy(FIXTURE["input"]); mutation(p)
            with self.assertRaises(OCPError):check_input(p)

    def test_06_duplicate_id_and_single_vehicle(self):
        for duplicate in (True,False):
            p=deepcopy(FIXTURE["input"])
            if duplicate:p["visits"][1]["id"]=p["visits"][0]["id"]
            else:p["vehicles"].pop()
            self.assertEqual(reference().execute(dict(request(),input=p))["kind"],"failure")

    def test_07_old_matrix_profile_not_silently_reinterpreted(self):
        req=request(); req["domain_profile"]={"id":"routing.basic","version":"0.1.0"}
        self.assertEqual(reference().execute(req)["error"]["code"],"VERSION_MISMATCH")

    def test_08_unsupported_weight_and_budget(self):
        for budget in (999,5001):self.assertEqual(reference().execute(request(budget=budget))["kind"],"failure")
        req=request(); req["configuration"]["objectives"][0]["weight"]=2
        self.assertEqual(reference().execute(req)["error"]["code"],"UNSUPPORTED_CONFIGURATION")

    def test_09_requirements_and_validation_never_solve(self):
        a=reference()
        with patch.object(a.backend,"solve",side_effect=AssertionError("must not solve")):
            validate_message(a.describe()); validate_message(a.requirements(a.describe()["defaults"]))
            self.assertTrue(a.validate(request(a))["valid"])

    def test_10_wrong_result_cost_caught_by_independent_checker(self):
        a=reference();req=request(a);res=a.execute(req);res["metrics"][0]["value"]+=1
        with self.assertRaises(ContractError):coordinates.verify_result(req,res)

    def test_11_missing_visit_caught(self):
        with self.assertRaises(OCPError):
            # Runtime checks structure separately; missing visits produce a nonzero violation.
            p=deepcopy(FIXTURE["input"]);p["visits"][0]["id"]="depot";check_input(p)
        sol=deepcopy(FIXTURE["witness"]);sol["routes"][0]["visits"].pop()
        self.assertFalse(coordinates.evaluate(FIXTURE["input"],sol)["feasible"])

    def test_12_analytic_infeasible_is_proven_without_engine(self):
        a=reference();req=request(a)
        req["input"]["visits"][0]["demand"]=100
        with patch.object(a.backend,"solve",side_effect=AssertionError):res=a.execute(req)
        self.assertEqual(res["status"],"infeasible"); coordinates.verify_result(req,res)

    def test_13_no_solution_is_unknown(self):
        a=reference();req=request(a)
        with patch.object(a.backend,"solve",return_value=Outcome(None,"time_limit",None)):res=a.execute(req)
        self.assertEqual(res["status"],"unknown");coordinates.verify_result(req,res)

    def test_14_foundry_whole_second_budget_never_rounds_up(self):
        payload=FoundryBackend.payload(FIXTURE["input"],1999)
        self.assertEqual(payload["solverParameters"]["timeLimitSeconds"],1)
        self.assertEqual(payload["solverParameters"]["distanceMethod"],"euclidean")
        self.assertEqual(payload["problem"]["vehicles"][0]["costs"],{"fixed":0,"unitDistance":1,"unitDuration":0})

    def test_15_foundry_unknown_status_not_infeasible(self):
        out=FoundryBackend.decode(FIXTURE["input"],{"jobId":"job","status":"infeasible"},"job")
        self.assertIsNone(out.solution);self.assertEqual(out.termination,"search_exhausted")

    def test_16_foundry_invalid_score_route_and_identity(self):
        valid={"jobId":"job","status":"feasible","unassignedVisitIds":[],"routes":[],"totalCost":0,
               "objectiveValues":[{"id":"minimize_total_route_cost","value":0}]}
        for change in [{"totalCost":None},{"totalCost":True},{"jobId":"other"},{"status":"error"},
                       {"routes":[None]},{"routes":[{"vehicleId":[],"stopIds":[]}]},
                       {"objectiveValues":[None]},{"routes":[{"vehicleId":"bad","stopIds":[]}]}]:
            with self.assertRaises(OCPError):FoundryBackend.decode(FIXTURE["input"],dict(valid,**change),"job")

    def test_17_full_catalog_payload_pin(self):
        backend=fake_backend()
        for change in [{"catalogDigest":"b"*64},{"extra":"unannounced"},{"compilerVersion":"9.0.0"}]:
            with patch.object(backend,"_call",return_value=dict(CATALOG,**change)):
                with self.assertRaises(OCPError):backend.check_catalog()

    def test_18_trusted_owner_context_and_secret_separation(self):
        a=FoundryCoordinatesAdapter(fake_backend())
        self.assertEqual(a.execute(request(a))["error"]["code"],"TRUSTED_CONTEXT_REQUIRED")
        self.assertNotIn("test-service-secret",json.dumps(a.describe()))
        one=a.backend.scoped("org-a","same");two=a.backend.scoped("org-b","same")
        self.assertNotEqual(one._tenant,two._tenant);self.assertNotEqual(one._idem,two._idem)
        self.assertEqual(one._idem,a.backend.scoped("org-a","same")._idem)

    def test_19_ambiguous_submission_is_never_retried(self):
        b=fake_backend().scoped("org","once");calls=[]
        def call(method,path,*args,**kwargs):
            calls.append((method,path))
            if path=="/capabilities":return CATALOG
            if path=="/validate":return {"valid":True}
            raise OCPError("TRANSPORT_UNCERTAIN")
        with patch.object(b,"_call",side_effect=call):
            with self.assertRaises(OCPError) as error:b.solve(FIXTURE["input"],1000)
        self.assertEqual(error.exception.code,"EXECUTION_UNCERTAIN")
        self.assertEqual(calls.count(("POST","/jobs")),1)

    def test_20_malformed_poll_requires_confirmed_stop(self):
        b=fake_backend().scoped("org","once")
        def call(method,path,*args,**kwargs):
            if path=="/capabilities":return CATALOG
            if path=="/validate":return {"valid":True}
            if path=="/jobs":return {"jobId":"job"}
            raise OCPError("INVALID_UPSTREAM_RESPONSE")
        with patch.object(b,"_call",side_effect=call),patch.object(b,"_stop",return_value=False) as stop:
            with self.assertRaises(OCPError) as error:b.solve(FIXTURE["input"],1000)
        self.assertEqual(error.exception.code,"EXECUTION_UNCERTAIN");stop.assert_called_once_with("job")

    def test_21_unverified_infeasibility_rejected(self):
        a=reference();req=request(a);res=a.execute(req)
        res.update(status="infeasible",solution=None,metrics=[],constraints=[],proof={"claim":"infeasible","method":"native-code","scope":"all visits","evidence":{}})
        with self.assertRaises(ContractError):coordinates.verify_result(req,res)

    def test_22_generic_client_supports_new_profile(self):
        result=Client(reference()).execute(deepcopy(FIXTURE["input"]),request_id="coordinate-test")
        self.assertEqual(coordinates.verify_result(request(),result)["total_cost"],11358)

    def test_23_wrong_job_cannot_confirm_cancellation(self):
        b=fake_backend().scoped("org","once")
        with patch.object(b,"_call",return_value={"jobId":"other","status":"cancelled"}):
            self.assertFalse(b._stop("job"))
        with patch.object(b,"_call",return_value={"jobId":"job","status":"cancelled"}):
            self.assertTrue(b._stop("job"))


if __name__=="__main__":
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(CoordinateTests))
    passed=result.wasSuccessful() and result.testsRun>=28 and not result.skipped
    print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),
                      "errors":len(result.errors),"skipped":len(result.skipped),"artifact_sha256":ARTIFACT["sha256"],
                      "versions":{"profile":"routing.coordinates@0.1.0"},
                      "scope":"Real OR-Tools, independent coordinate oracle and explicitly injected upstream faults; no live Foundry assertion"}))
    WORK.cleanup();sys.exit(0 if passed else 1)
