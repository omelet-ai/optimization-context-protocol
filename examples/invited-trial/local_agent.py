"""No-key MCP setup and real protocol checks. Never contacts a language model."""
import argparse
import asyncio
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

SERVER_ARGS = ["-I", "-B", "-m", "ocp_runtime.mcp_server"]
TOOLS = {"ocp_context", "ocp_describe", "ocp_requirements", "ocp_validate", "ocp_execute", "ocp_evaluate"}
PROFILES = ("routing.basic", "worker.scheduling", "inventory.replenishment")


class SetupError(ValueError):
    def __init__(self, code, hint):
        self.code, self.hint = code, hint


def dependencies():
    if any(importlib.util.find_spec(name) is None for name in ("mcp", "ortools", "conformance")):
        raise SetupError("LOCAL_MCP_DEPENDENCIES_MISSING",
                         "From an intact kit run python3.12 start.py --mcp --venv NEW_PATH, then use that environment's Python.")


def configuration(profile="routing.basic"):
    # Resolving a symlink here would replace the venv Python with base Python.
    return {"command": str(Path(sys.executable).absolute()), "args": SERVER_ARGS.copy() + (["--profile",profile] if profile!="routing.basic" else [])}


async def probe(problem=None, request_id=None, profile="routing.basic"):
    from mcp import Client, StdioServerParameters
    from jsonschema import Draft202012Validator
    from conformance.runner import CHECKERS

    calls = []
    report = {"status": "PASS", "scope": "installed_local_mcp_only_not_model_acceptance",
              "model_calls": 0, "execute_calls": 0, "tool_calls": calls}
    with tempfile.TemporaryDirectory(prefix="ocp-local-mcp-") as directory:
        # A fresh home/cwd and fixed environment avoid dependence on repo files,
        # user Python paths or trial credentials. No port is opened.
        env = {"PATH": os.defpath, "HOME": directory, "PYTHONDONTWRITEBYTECODE": "1"}
        params = StdioServerParameters(**configuration(profile), env=env, cwd=directory)
        async with Client(params, read_timeout_seconds=60) as host:
            async def call(name, arguments):
                calls.append(name)
                value = await host.call_tool(name, arguments)
                if value.is_error or not isinstance(value.structured_content, dict):
                    raise SetupError("MCP_OPERATION_FAILED", "Run doctor again; check the pinned environment. Do not retry an uncertain solve automatically.")
                return value.structured_content

            names = {tool.name for tool in (await host.list_tools()).tools}
            if names != TOOLS:
                raise SetupError("MCP_TOOLSET_MISMATCH", "Use the exact environment from this kit; do not guess missing tools.")
            guide = await call("ocp_context", {})
            def check_guide(value, selected):
                for key in ("request_schema", "input_schema"):
                    Draft202012Validator.check_schema(value[key])
                if value["capability"]["domain_profile"] != {"id": selected, "version": "0.1.0"}:
                    raise SetupError("MCP_PROFILE_MISMATCH", "The provider did not return the explicitly selected profile.")

            report.update(protocol_version=str(host.protocol_version), tools=sorted(names))
            if profile == "all":
                expected = [{"id": item, "version": "0.1.0"} for item in PROFILES]
                available = guide.get("available_profiles")
                if not isinstance(available, list) or len(available) != len(expected) or any(item not in available for item in expected):
                    raise SetupError("MCP_PROFILE_MISMATCH", "Expected context for all three bundled profiles; check the installed environment.")
                check_guide(guide, PROFILES[0])
                for selected in PROFILES[1:]:
                    check_guide(await call("ocp_context", {"profile": selected}), selected)
                report.update(available_profiles=available, checked_profiles=list(PROFILES))
            else:
                check_guide(guide, profile)
                report["domain_profile"] = guide["capability"]["domain_profile"]
            if problem is None:
                return report
            request = deepcopy(guide["request_template"])
            request.update(input=problem, request_id=request_id)
            validation = await call("ocp_validate", {"request": request})
            report["validation"] = validation
            if validation.get("valid") is not True:
                report.update(status="FAIL", code="INPUT_REJECTED",
                              hint="Review validation.issues and the context input schema; nothing was executed.")
                return report
            report["execute_calls"] = 1
            result = await call("ocp_execute", {"request": request})
            checked = CHECKERS[(profile,"0.1.0")](request, result)
            evaluation = None
            if result["solution"] is not None:
                evaluation = await call("ocp_evaluate", {"request": request, "solution": result["solution"]})
                if evaluation.get("kind") != "evaluation":
                    raise SetupError("MCP_EVALUATION_FAILED", "Preserve the request ID and inspect the local environment.")
            report.update(request=request, response=result, independent_check=checked, evaluation=evaluation)
            # PASS means protocol + checker acceptance, not solution existence.
            report["solution_found"] = result["solution"] is not None
            return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    doctor = sub.add_parser("doctor", help="Start MCP, discover tools and read context; no solve")
    config = sub.add_parser("config", help="Print config for review; do not change host configuration")
    config.add_argument("--format", choices=("json", "codex"), default="json")
    smoke = sub.add_parser("smoke", help="Execute one synthetic input through MCP and independently check the result")
    smoke.add_argument("--input", required=True)
    smoke.add_argument("--request-id", required=True)
    for command in (doctor,config,smoke):
        command.add_argument("--profile",choices=PROFILES if command is smoke else (*PROFILES,"all"),default="routing.basic")
    args = parser.parse_args()
    try:
        dependencies()
        if args.operation == "config":
            value = configuration(args.profile)
            if args.format == "json":
                print(json.dumps({"mcpServers": {"ocp-local": value}}, indent=2))
            else:
                print("[mcp_servers.ocp-local]\ncommand = " + json.dumps(value["command"], ensure_ascii=False)
                      + "\nargs = " + json.dumps(value["args"]) + "\nstartup_timeout_sec = 60\ntool_timeout_sec = 60\nrequired = true")
            return 0
        problem = None
        if args.operation == "smoke":
            from ocp_candidate import parse_json
            try:
                with open(args.input, "rb") as stream:
                    raw = stream.read(131073)
                if len(raw) > 131072:
                    raise ValueError("Input exceeds limit")
                problem = parse_json(raw.decode("utf-8"))
                if not isinstance(problem, dict):
                    raise ValueError("Input must be an object")
            except Exception:
                raise SetupError("INPUT_INVALID", "Use a readable UTF-8 JSON object, at most 128 KiB, with unique keys and finite numbers.") from None
        report = asyncio.run(probe(problem, getattr(args, "request_id", None), args.profile))
        print(json.dumps(report, allow_nan=False))
        return 0 if report["status"] == "PASS" else 1
    except Exception as error:
        code, hint = (error.code, error.hint) if isinstance(error, SetupError) else (
            "LOCAL_MCP_CHECK_FAILED", "Check the installed environment with doctor. No automatic retry; preserve the request ID after an uncertain solve.")
        print(json.dumps({"status": "FAIL", "code": code, "hint": hint, "model_calls": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
