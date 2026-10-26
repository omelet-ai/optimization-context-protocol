"""MCP stdio binding using official SDK; tool completion is a synchronous OCP result."""

import json
from copy import deepcopy
from ocp_candidate import Client
from ocp_candidate.contract import schema
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent
from .service import Service


def create_mcp(adapter, *, name="OCP local reference", instructions=None):
    service = Service(adapter)
    mcp = MCPServer(name, instructions=(instructions or "Describe capabilities, request requirements, validate, then execute. No async jobs or trial service.")+
        " First read ocp://request-guide/0.1.0 for the complete request template and schemas. Replace its input and request_id; validate before execute. Reading it does not solve.")

    @mcp.resource("ocp://request-guide/0.1.0",mime_type="application/json",
                  description="Versioned Core request schema, provider defaults, input schema and a non-executing request template. No key or solve.")
    def request_guide() -> str:
        client=Client(adapter)
        capability=client.describe()
        core=deepcopy(schema("core"))
        request_schema={"$schema":core["$schema"],"$defs":core["$defs"],"$ref":"#/$defs/request"}
        profile=capability["domain_profile"]
        profiles={("routing.basic","0.1.0"):"routing-input",("routing.coordinates","0.1.0"):"routing-coordinates-input",
                  ("assignment.fixture","0.1.0"):"assignment-fixture-input"}
        input_name=profiles.get((profile["id"],profile["version"]))
        return json.dumps({"guide_version":"0.1.0","request_schema":request_schema,
            "input_schema":deepcopy(schema(input_name)) if input_name else None,
            "input_schema_scope":"Packaged profile schema; unsupported profiles require provider documentation",
            "request_template":client.request({},request_id="REPLACE_WITH_YOUR_STABLE_JOB_ID",time_limit_ms=1000),
            "steps":["Replace input with your synthetic input; fill every required input_schema field.",
                     "Choose one explicit request_id per job. Keep it for an identical retry; use a new ID for a different job.",
                     "Review configuration and budget, then ocp_validate(request). Execute only when valid=true.",
                     "ocp_execute(request) spends quota. No automatic retry or engine fallback.",
                     "ocp_evaluate(request, solution) evaluates without solving. Preserve not_evaluated/null."]},allow_nan=False)

    def returned(message):
        return CallToolResult(content=[TextContent(type="text",text=json.dumps(message,allow_nan=False))],
                              structured_content=message,is_error=message["kind"]=="failure")

    @mcp.tool()
    def ocp_describe() -> CallToolResult:
        """Describe the exact supported optimization profile and choices."""
        return returned(service.dispatch("describe",binding="binding.mcp_stdio"))

    @mcp.tool()
    def ocp_requirements(configuration: dict) -> CallToolResult:
        """Return input requirements for the explicit configuration."""
        return returned(service.dispatch("requirements",{"configuration":configuration},"binding.mcp_stdio"))

    @mcp.tool()
    def ocp_validate(request: dict) -> CallToolResult:
        """Validate a complete Core request from ocp://request-guide/0.1.0 without solving. A false validation is not infeasibility."""
        return returned(service.dispatch("validate",request,"binding.mcp_stdio"))

    @mcp.tool()
    def ocp_execute(request: dict) -> CallToolResult:
        """Run a complete Core request from ocp://request-guide/0.1.0 synchronously. Keep request_id on uncertainty; never retry with a new ID automatically."""
        return returned(service.dispatch("execute",request,"binding.mcp_stdio"))

    @mcp.tool()
    def ocp_evaluate(request: dict, solution: dict) -> CallToolResult:
        """Evaluate a supplied solution without running optimization."""
        return returned(service.dispatch("evaluate",{"request":request,"solution":solution},"binding.mcp_stdio"))

    return mcp


if __name__ == "__main__":
    from ocp_routing import RoutingAdapter, ORToolsBackend
    create_mcp(RoutingAdapter(ORToolsBackend())).run(transport="stdio")
