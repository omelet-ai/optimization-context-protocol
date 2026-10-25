"""MCP stdio binding using official SDK; tool completion is a synchronous OCP result."""

import json
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent
from .service import Service


def create_mcp(adapter):
    service = Service(adapter)
    mcp = MCPServer("OCP local reference", instructions="Describe capabilities, request requirements, validate, then execute. No async jobs or trial service.")

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
        """Validate without solving. A false validation is not infeasibility."""
        return returned(service.dispatch("validate",request,"binding.mcp_stdio"))

    @mcp.tool()
    def ocp_execute(request: dict) -> CallToolResult:
        """Run the real local engine synchronously; inspect Core kind/status and errors."""
        return returned(service.dispatch("execute",request,"binding.mcp_stdio"))

    @mcp.tool()
    def ocp_evaluate(request: dict, solution: dict) -> CallToolResult:
        """Evaluate a supplied solution without running optimization."""
        return returned(service.dispatch("evaluate",{"request":request,"solution":solution},"binding.mcp_stdio"))

    return mcp


if __name__ == "__main__":
    from ocp_routing import RoutingAdapter, ORToolsBackend
    create_mcp(RoutingAdapter(ORToolsBackend())).run(transport="stdio")
