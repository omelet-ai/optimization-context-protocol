"""Verify the received, narrowly scoped Foundry instruction against its local source.

This is a provenance check, not a signature system or a way to grant permission.
The agent must still honor later user instructions and the recorded action scope.
"""
import hashlib
import json
from pathlib import Path
import sys

MESSAGE_SHA256 = "06f4758deca066d5570159b043f0a0b18827d0d7c7e85583a26bf27c252dfdb1"
SCOPE = {"repository": "omelet-ai/oi-foundry", "base": "main", "branch": "feat/ocp-consumer-integration",
         "actions": ["implement-minimal-consumers", "local-verify", "commit", "push", "draft-pr"],
         "excluded": ["merge", "deploy", "public-release", "external-trial-operations", "provider-migration"]}


def verify(receipt):
    if any(receipt.get(k) != v for k, v in SCOPE.items()):
        raise ValueError("Instruction scope differs from the received authorization")
    if receipt.get("message_sha256") != MESSAGE_SHA256 or type(receipt.get("line")) is not int or receipt["line"] < 1:
        raise ValueError("Invalid source reference")
    source = Path(receipt["source_file"])
    if source.is_symlink() or not source.is_file():
        raise ValueError("Original instruction source unavailable")
    entry = None
    with source.open() as stream:
        for n, line in enumerate(stream, 1):
            if n == receipt["line"]:
                entry = json.loads(line)
                break
    if entry != receipt.get("record") or entry.get("timestamp") != receipt.get("timestamp"):
        raise ValueError("Source record differs from preserved receipt")
    payload = entry.get("payload", {})
    if entry.get("type") != "response_item" or payload.get("role") != "user":
        raise ValueError("Only the original user instruction is accepted")
    content = payload.get("content", [])
    if not content or any(c.get("type") != "input_text" or not isinstance(c.get("text"), str) for c in content):
        raise ValueError("Unsupported instruction content")
    message = "\n".join(c["text"] for c in content)
    if hashlib.sha256(message.encode()).hexdigest() != MESSAGE_SHA256:
        raise ValueError("Received user instruction changed")
    return {"status": "PASS", "authorization_source_verified": True, "scope_verified": True,
            "scope": "Received Foundry minimal-consumer branch/commit/push/draft-PR instruction only; no merge, deployment, trial operation or provider migration",
            "versions": {"instruction_sha256": MESSAGE_SHA256, "repository": SCOPE["repository"], "branch": SCOPE["branch"]}}


if __name__ == "__main__":
    try:
        path = Path(__file__).resolve().parents[1] / ".private/authorizations/foundry-consumer.json"
        print(json.dumps(verify(json.loads(path.read_text()))))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}))
        sys.exit(1)
