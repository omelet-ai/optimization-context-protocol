"""H01 independent candidate schema, semantics and compatibility checks."""

from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from conformance.core_contract import ContractError, SCHEMA_PATH, parse_json, validate_message
from jsonschema import Draft202012Validator


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = parse_json(SCHEMA_PATH.read_text())
        cls.examples = {x["message"]["kind"]: x["message"] for x in parse_json(
            (ROOT / "cases/core/messages.json").read_text())["positive"]}

    def example(self, kind="request"):
        return deepcopy(self.examples[kind])

    def reject(self, value, code="SCHEMA_INVALID"):
        with self.assertRaises(ContractError) as caught:
            validate_message(value)
        self.assertEqual(caught.exception.code, code)

    def test_01_schema_is_draft202012(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        Draft202012Validator.check_schema(self.schema)
        self.assertEqual(importlib.metadata.version("jsonschema"), "4.26.0")

    def test_02_all_message_kinds_have_positive_fixture(self):
        self.assertEqual(set(self.examples), {"capability", "request", "requirements", "validation", "result", "failure", "evaluation", "conformance"})
        for message in self.examples.values():
            validate_message(message)

    def test_03_unknown_core_version(self):
        value = self.example(); value["core_version"] = "99.0.0"
        self.reject(value)

    def test_04_unknown_envelope_field(self):
        value = self.example(); value["tenant"] = "not-a-core-field"
        self.reject(value)

    def test_05_unknown_configuration_field(self):
        value = self.example(); value["configuration"]["approximate"] = True
        self.reject(value)

    def test_06_missing_identity(self):
        value = self.example(); del value["capability"]["version"]
        self.reject(value)

    def test_07_bad_profile_version(self):
        value = self.example(); value["domain_profile"]["version"] = "latest"
        self.reject(value)

    def test_08_required_extension_rejected(self):
        value = self.example(); value["extensions"] = [{"id":"unknown","version":"1","required":True,"value":{}}]
        self.reject(value, "UNSUPPORTED_EXTENSION")

    def test_09_optional_extension_is_advisory(self):
        value = self.example(); value["extensions"] = [{"id":"display-hint","version":"1","required":False,"value":{"color":"blue"}}]
        validate_message(value)

    def test_10_duplicate_objective_rejected(self):
        value = self.example(); value["configuration"]["objectives"] *= 2
        self.reject(value, "DUPLICATE_ID")

    def test_11_duplicate_extension_rejected(self):
        value = self.example(); value["extensions"] = [{"id":"hint","version":"1","required":False,"value":{}}] * 2
        self.reject(value, "DUPLICATE_ID")

    def test_12_negative_weight_rejected(self):
        value = self.example(); value["configuration"]["objectives"][0]["weight"] = -1
        self.reject(value)

    def test_13_boolean_budget_rejected(self):
        value = self.example(); value["budget"]["time_limit_ms"] = True
        self.reject(value)

    def test_14_nonfinite_number_rejected(self):
        value = self.example(); value["input"]["costs"] = [[float("nan")]]
        self.reject(value, "NONFINITE_NUMBER")

    def test_15_duplicate_json_key_rejected(self):
        with self.assertRaises(ContractError):
            parse_json('{"id":1,"id":2}')

    def test_16_json_overflow_rejected(self):
        with self.assertRaises(ContractError):
            parse_json('{"cost":1e999}')

    def test_17_feasible_needs_solution(self):
        value = self.example("result"); value["solution"] = None
        self.reject(value)

    def test_18_optimal_needs_proof(self):
        value = self.example("result"); value["status"] = "optimal"
        self.reject(value)

    def test_19_infeasible_needs_proof(self):
        value = self.example("result"); value.update(status="infeasible",solution=None)
        self.reject(value)

    def test_20_timeout_is_not_proof(self):
        value = self.example("result"); value.update(status="infeasible",solution=None,termination="time_limit",proof={"claim":"infeasible","method":"claimed","scope":"all","evidence":{"x":1}})
        self.reject(value)

    def test_21_unknown_after_timeout_has_no_solution_or_proof(self):
        value = self.example("result"); value.update(status="unknown",solution=None,termination="time_limit",metrics=[],constraints=[])
        validate_message(value)

    def test_22_feasible_at_timeout_is_allowed(self):
        value = self.example("result"); value["termination"] = "time_limit"
        validate_message(value)

    def test_23_not_evaluated_is_not_zero(self):
        value = self.example("evaluation"); value["metrics"][0].update(status="not_evaluated",reason="unavailable",value=0)
        self.reject(value)

    def test_24_not_evaluated_requires_reason(self):
        value = self.example("evaluation"); value["metrics"][0].update(status="not_evaluated",value=None)
        self.reject(value)

    def test_25_evaluated_requires_value(self):
        value = self.example("evaluation"); value["metrics"][0]["value"] = None
        self.reject(value)

    def test_26_constraint_violation_consistency(self):
        value = self.example("evaluation"); value["constraints"][0]["violation"] = 1
        self.reject(value)

    def test_27_result_request_link(self):
        value = self.example("result"); value["provenance"]["request_id"] = "other"
        self.reject(value, "REQUEST_MISMATCH")

    def test_28_no_domain_or_omelet_requirements_in_core(self):
        text = json.dumps(self.schema).lower()
        for token in ("routing", "depot", "vehicle", "stop", "ocp_state", "tenant", "appkit", "oip"):
            self.assertNotIn('"' + token + '"', text)
        request = self.example()
        self.assertNotIn("endpoint", request)
        validate_message(request)

    def test_29_validation_false_requires_issue(self):
        value = self.example("validation"); value["valid"] = False
        self.reject(value)

    def test_30_default_configuration_must_match_schema(self):
        value = self.example("capability"); value["configuration_schema"] = False
        self.reject(value, "INVALID_DEFAULT_CONFIGURATION")

    def test_31_conformance_empty_checks_rejected(self):
        value = self.example("conformance"); value["checks"] = []
        self.reject(value)

    def test_32_requirements_traceability(self):
        requirements = json.loads((ROOT / "spec/requirements.json").read_text())["requirements"]
        known = set(unittest.defaultTestLoader.getTestCaseNames(type(self)))
        core = [r for r in requirements if r["gate"] == "H01"]
        self.assertGreaterEqual(len(core), 10)
        self.assertEqual(len({r["id"] for r in core}), len(core))
        for requirement in core:
            self.assertTrue(requirement["tests"])
            self.assertTrue(set(requirement["tests"]) <= known)
            self.assertTrue((ROOT / requirement["normative_source"].split("#")[0]).is_file())

    def test_33_external_schema_reference_is_not_fetched(self):
        value = self.example("capability"); value["configuration_schema"] = {"$ref":"https://example.invalid/schema"}
        self.reject(value, "EXTERNAL_SCHEMA_REFERENCE")

    def test_34_integer_precision_bound(self):
        value = self.example(); value["input"]["huge"] = 10 ** 500
        self.reject(value, "INTEGER_OUT_OF_RANGE")

    def test_35_float_integer_precision_bound(self):
        value = self.example(); value["input"]["huge"] = 1e16
        self.reject(value, "INTEGER_OUT_OF_RANGE")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(CoreTests))
    passed = result.wasSuccessful() and result.testsRun >= 35 and not result.skipped
    print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,
                      "failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
                      "scope":"Core candidate schema and semantics; no engine execution"}))
    sys.exit(0 if passed else 1)
