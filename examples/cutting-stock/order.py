"""Submit a synthetic cutting order or look up a desktop host's job over stdio MCP."""
import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

from mcp import Client, StdioServerParameters


async def call(client, tool, arguments):
    reply = await client.call_tool(tool, arguments)
    if reply.is_error:
        raise ValueError(f"{tool} failed: {reply.structured_content or reply.content}")
    value = reply.structured_content
    if value.get("inline") is not False:
        return value

    reference = value["artifact"]
    data = bytearray()
    while len(data) < reference["size_bytes"]:
        chunk = await client.call_tool("ocp_read_artifact", {"reference": reference, "offset": len(data)})
        if chunk.is_error:
            raise ValueError("Could not read the result artifact")
        part = base64.b64decode(chunk.structured_content["data_base64"], validate=True)
        if not part or len(data) + len(part) > reference["size_bytes"]:
            raise ValueError("Invalid result artifact length")
        data.extend(part)
    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValueError("Result artifact checksum mismatch")
    return json.loads(data)


async def run(config, pieces, job_id):
    params = StdioServerParameters(command=sys.executable, args=[
        "-I", "-B", "-m", "ocp_cutplan.server", "serve", "--config", str(config.resolve())])
    async with Client(params, read_timeout_seconds=30) as client:
        servers = (await call(client, "ocp_context", {}))["servers"]
        if not any(server["id"] == "cutplan" for server in servers):
            raise ValueError("The cutting-stock server is missing from the catalogue")
        ref = {"server_id": "cutplan"}
        if job_id is None:
            data = {"stock_length_cm": 100, "pieces_cm": pieces, "kerf_cm": 0}
            request = {**ref, "input_value": data, "configuration": {}}
            validation = await call(client, "ocp_validate", request)
            if validation["status"] != "valid":
                raise ValueError(f"Invalid cutting order: {validation}")
            submission = await call(client, "ocp_submit", {**request, "idempotency_key": str(uuid4())})
            job_id = submission["job"]["jobId"]
            print(f"Submitted job {job_id}", file=sys.stderr)
        ref["job_id"] = job_id
        async with asyncio.timeout(45):
            while True:
                job = await call(client, "ocp_job", ref)
                if job["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(0.15)
        if job["status"] not in {"succeeded", "infeasible"}:
            raise ValueError(f"Job {job_id} ended with status {job['status']}")
        outcome = (await call(client, "ocp_result", ref))["outcome"]
        evaluation = (await call(client, "ocp_evaluate", ref))["evaluation"]
        return {"job_id": job_id, "solution_status": outcome["solution_status"],
                "result": outcome["result"], "proof": outcome["proof"], "evaluation": evaluation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Same local configuration as the desktop app")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pieces", nargs="+", type=int, metavar="CM", help="Submit a new order for 100 cm bars")
    mode.add_argument("--job-id", help="Read an existing job without submitting another order")
    args = parser.parse_args()
    receipt = asyncio.run(run(args.config, args.pieces, args.job_id))
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    if receipt["solution_status"] == "infeasible":
        return 0
    return 0 if receipt["evaluation"] and receipt["evaluation"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
