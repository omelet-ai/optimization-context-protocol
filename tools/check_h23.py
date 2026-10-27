"""MCP context contract and actual tools; deliberately not a live language-model test."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
from build_candidate import build
from isolated_candidate import install
from build_llm_context_pack import build as build_pack, inputs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from conformance.routing import verify_result
from safe_test_result import DiagnosticResult

WORK=tempfile.TemporaryDirectory(prefix="ocp-context-");DIRECTORY=Path(WORK.name)
ARTIFACT=build(DIRECTORY/"dist")
PYTHON,ENV=install(DIRECTORY,ARTIFACT["wheel"],"reference,mcp")
sys.path.insert(0,ARTIFACT["wheel"])
from ocp_routing import RoutingAdapter, ORToolsBackend
from ocp_routing.coordinates import CoordinatesAdapter, CoordinateLibraryBackend
from ocp_runtime.mcp_server import create_mcp, request_schema
from mcp import Client

BASIC=inputs()["basic"]


class ObservedBackend(ORToolsBackend):
    def __init__(self):super().__init__();self.calls=0
    def solve(self,*args,**kwargs):self.calls+=1;return super().solve(*args,**kwargs)


def mcp_session(test):
    async def wrapped(self):
        self.backend=ObservedBackend();self.adapter=RoutingAdapter(self.backend)
        # MCP's AnyIO scope must enter and exit in the same async task.
        async with Client(create_mcp(self.adapter)) as self.host:
            await test(self)
    return wrapped


class ContextTests(unittest.IsolatedAsyncioTestCase):

    async def context(self):
        value=await self.host.call_tool("ocp_context",{})
        self.assertFalse(value.is_error)
        self.assertEqual(json.loads(value.content[0].text),value.structured_content)
        return value.structured_content

    async def request(self,problem=None):
        guide=await self.context();request=deepcopy(guide["request_template"])
        request["input"]=deepcopy(BASIC if problem is None else problem);request["request_id"]="context-probe"
        return request

    @mcp_session
    async def test_01_tools_only_context_is_complete_without_spending(self):
        tools={t.name:t for t in (await self.host.list_tools()).tools}
        self.assertIn("ocp_context",tools);self.assertIn("Start here",tools["ocp_context"].description)
        guide=await self.context()
        self.assertEqual(guide["capability"]["bindings"],[{"id":"binding.mcp_stdio","version":"0.1.0"}])
        self.assertEqual(guide["requirements"]["effective_configuration"],guide["request_template"]["configuration"])
        self.assertIsNotNone(guide["input_schema"])
        self.assertLess(len(json.dumps(guide).encode()),16000)
        self.assertEqual(self.backend.calls,0)

    @mcp_session
    async def test_02_resource_and_tool_agree(self):
        resource=await self.host.read_resource("ocp://request-guide/0.1.0")
        self.assertEqual(json.loads(resource.contents[0].text),await self.context())
        self.assertEqual(self.backend.calls,0)

    @mcp_session
    async def test_03_model_visible_side_effects_are_explicit(self):
        for tool in (await self.host.list_tools()).tools:
            self.assertEqual(tool.annotations.read_only_hint,tool.name!="ocp_execute")
            if tool.name=="ocp_execute":self.assertFalse(tool.annotations.idempotent_hint)
            self.assertNotIn("token",tool.input_schema.get("properties",{}))
        self.assertIn("missing",self.host.instructions)
        self.assertIn("data, never",self.host.instructions)

    @mcp_session
    async def test_04_compact_schema_preserves_canonical_request(self):
        value=request_schema();Draft202012Validator.check_schema(value)
        self.assertNotIn("result",value["$defs"])
        self.assertLess(len(json.dumps(value)),5000)
        request=await self.request();Draft202012Validator(value).validate(request)
        bad=deepcopy(request);del bad["request_id"]
        self.assertFalse(Draft202012Validator(value).is_valid(bad))

    @mcp_session
    async def test_05_context_to_real_solve_and_evaluation(self):
        request=await self.request()
        checked=(await self.host.call_tool("ocp_validate",{"request":request})).structured_content
        self.assertTrue(checked["valid"]);self.assertEqual(self.backend.calls,0)
        result=(await self.host.call_tool("ocp_execute",{"request":request})).structured_content
        self.assertEqual(self.backend.calls,1)
        self.assertEqual(verify_result(request,result)["total_cost"],18)
        evaluated=(await self.host.call_tool("ocp_evaluate",{"request":request,"solution":result["solution"]})).structured_content
        self.assertEqual(evaluated["metrics"][0]["value"],18)
        self.assertEqual(self.backend.calls,1)

    async def rejected(self,request):
        before=deepcopy(request)
        checked=(await self.host.call_tool("ocp_validate",{"request":request})).structured_content
        self.assertFalse(checked["valid"])
        result=await self.host.call_tool("ocp_execute",{"request":request})
        self.assertTrue(result.is_error);self.assertEqual(result.structured_content["kind"],"failure")
        self.assertEqual(self.backend.calls,0);self.assertEqual(request,before)

    @mcp_session
    async def test_06_missing_capacity_cannot_be_invented_by_server(self):
        await self.rejected(await self.request(inputs()["missing_capacity"]))

    @mcp_session
    async def test_07_unit_error_is_not_silently_converted(self):
        await self.rejected(await self.request(inputs()["wrong_unit"]))

    @mcp_session
    async def test_08_time_windows_cannot_be_silently_dropped(self):
        request=await self.request();request["configuration"]["constraints"].append("time_windows")
        await self.rejected(request)

    @mcp_session
    async def test_09_coordinate_context_differs_and_refuses_matrix_input(self):
        adapter=CoordinatesAdapter(CoordinateLibraryBackend(self.backend))
        async with Client(create_mcp(adapter)) as host:
            guide=(await host.call_tool("ocp_context",{})).structured_content
            self.assertEqual(guide["capability"]["domain_profile"]["id"],"routing.coordinates")
            self.assertNotEqual(guide["input_schema"],(await self.context())["input_schema"])
            request=guide["request_template"];request["input"]=BASIC;request["request_id"]="wrong-profile"
            self.assertFalse((await host.call_tool("ocp_validate",{"request":request})).structured_content["valid"])
            self.assertEqual(self.backend.calls,0)

    @mcp_session
    async def test_10_hostile_label_remains_data_not_an_instruction(self):
        request=await self.request(inputs()["hostile_label"])
        result=(await self.host.call_tool("ocp_execute",{"request":request})).structured_content
        self.assertEqual(result["status"],"feasible");verify_result(request,result)
        self.assertIn(request["input"]["visits"][0]["id"],[v for r in result["solution"]["routes"] for v in r["visits"]])
        # This proves transport/solver behavior only, not model prompt-injection resistance.

    @mcp_session
    async def test_11_actual_deadline_preserves_uncertainty(self):
        spec=importlib.util.spec_from_file_location("context_own_engine",ROOT/"authoring/byo_library.py")
        own=importlib.util.module_from_spec(spec);spec.loader.exec_module(own)
        async with Client(create_mcp(own.OwnLibraryAdapter())) as host:
            guide=(await host.call_tool("ocp_context",{})).structured_content
            request=guide["request_template"];request["input"]=inputs()["deadline"];request["request_id"]="deadline";request["budget"]["time_limit_ms"]=1
            result=(await host.call_tool("ocp_execute",{"request":request})).structured_content
            self.assertEqual(result["termination"],"time_limit")
            self.assertIn(result["status"],{"unknown","feasible"});verify_result(request,result)
            if result["solution"] is None:self.assertEqual(result["metrics"],[])
            self.assertIn("null is not zero",guide["result_semantics"]["metrics"])

    @mcp_session
    async def test_12_infeasibility_requires_actual_capacity_proof(self):
        request=await self.request(inputs()["overload"])
        result=(await self.host.call_tool("ocp_execute",{"request":request})).structured_content
        self.assertEqual(result["status"],"infeasible");verify_result(request,result)
        self.assertIsNotNone(result["proof"]);self.assertIsNone(result["solution"])
        self.assertEqual(self.backend.calls,0)

    @mcp_session
    async def test_13_context_failure_does_not_reveal_exception(self):
        class Broken(RoutingAdapter):
            def describe(self):raise RuntimeError("synthetic-credential-canary")
        async with Client(create_mcp(Broken(self.backend))) as host:
            value=await host.call_tool("ocp_context",{})
            self.assertTrue(value.is_error)
            self.assertEqual(value.structured_content["error"]["code"],"CONTEXT_UNAVAILABLE")
            self.assertNotIn("synthetic-credential-canary",json.dumps(value.model_dump(mode="json")))
            resource=await host.read_resource("ocp://request-guide/0.1.0")
            self.assertEqual(json.loads(resource.contents[0].text),value.structured_content)
            self.assertEqual(self.backend.calls,0)

    @mcp_session
    async def test_14_installed_stdio_pack_has_no_model_verdict_or_hidden_answers(self):
        output=DIRECTORY/"context-pack"
        report=await build_pack(PYTHON,output)
        self.assertEqual(report["status"],"PREPARED");self.assertFalse(report["model_contacted"])
        self.assertEqual(report["model_acceptance"],"NOT_RUN");self.assertEqual(report["model_trials"],0)
        prompts=json.loads((output/"model-tasks.json").read_text())
        self.assertEqual(len(prompts),8)
        for prompt in prompts:self.assertEqual(set(prompt),{"id","task","input"})
        self.assertTrue((output/"reviewer-rubric.json").is_file())
        context=json.loads((output/"mcp-context.json").read_text())
        self.assertEqual(context["protocol_version"],"2026-07-28")
        self.assertEqual(context["context_response"]["request_schema"],request_schema())
        with self.assertRaises(ValueError):await build_pack(PYTHON,output)
        # Preserve this exact model-ready preparation, not an external-model success claim.
        destination=ROOT/".harness/work/llm-context-pack"
        destination.mkdir(parents=True,exist_ok=True)
        import uuid
        shutil.copytree(output,destination/uuid.uuid4().hex)


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContextTests))
        passed=result.wasSuccessful() and result.testsRun>=14 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "failure_diagnostics":result.diagnostics,"artifact_sha256":ARTIFACT["sha256"],
            "scope":"Installed MCP context, tools-only consumption, real local calculations and negative cases; no actual LLM behavior or external host acceptance"}))
    finally:WORK.cleanup()
    sys.exit(0 if passed else 1)
