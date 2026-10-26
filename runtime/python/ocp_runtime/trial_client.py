"""Installed invitation client: pinned HTTP, doctor and remote MCP stdio bridge."""

import argparse
import errno
import json
import re
import sys

from ocp_candidate.contract import OCPError
from ocp_candidate.http_adapter import HTTPAdapter
from .trial import digest
from .trial_ops import read_private_json, PrivateFileError


def diagnostic(error):
    """Fixed messages only: never reflect session contents, keys or raw exceptions."""
    if isinstance(error,ModuleNotFoundError): code="DEPENDENCY_MISSING"
    elif isinstance(error,FileNotFoundError): code="INVITATION_NOT_FOUND"
    elif isinstance(error,PermissionError): code="INVITATION_UNREADABLE"
    elif isinstance(error,OSError) and error.errno==errno.ELOOP: code="INVITATION_UNSAFE_FILE"
    elif isinstance(error,(OCPError,PrivateFileError)): code=error.code
    else: code="INVITATION_INVALID"
    hints={
        "DEPENDENCY_MISSING":"Install the documented wheel extras in this Python environment (reference for local OR-Tools, mcp for the MCP bridge).",
        "INVITATION_NOT_FOUND":"Check --session points to the session.json supplied by your inviter.",
        "INVITATION_UNREADABLE":"Check file ownership and owner read permission; keep group/world access disabled.",
        "INVITATION_PERMISSIONS":"Run chmod 600 session.json, then retry doctor. Do not share the key.",
        "INVITATION_UNSAFE_FILE":"Use a regular private session.json file, not a symlink or directory.",
        "INVITATION_TOO_LARGE":"Request a new session.json from your inviter; do not paste its contents.",
        "INVITATION_JSON_INVALID":"The session file is invalid JSON. Request a fresh file from your inviter.",
        "INVITATION_INVALID":"Use the original session.json containing endpoint, trial key and catalog pin.",
        "CATALOG_CHANGED":"Stop execution and request a reviewed session from the inviter. Do not change the pin yourself.",
        "UNAUTHORIZED":"The key is unknown, revoked or expired. Contact the inviter; do not send the key.",
        "TRIAL_EXPIRED":"This invitation window has ended. Contact the inviter for a newly approved window.",
        "TRANSPORT_UNCERTAIN":"Check connectivity and invitation hours. If a solve was submitted, keep its request ID; do not create a new one.",
        "QUOTA_EXCEEDED":"The trial limit is reached. Contact the inviter; do not create another identity.",
    }
    return {"status":"FAIL","code":code,"hint":hints.get(code,"Keep the request ID and report the error code to the inviter; never send the key.")}


class InvitationClient(HTTPAdapter):
    def __init__(self,path):
        try: config=read_private_json(path)
        except OCPError as error: raise OCPError("INVITATION_JSON_INVALID") from error
        if set(config)!={"endpoint","token","catalog_sha256"}: raise ValueError("Invalid invitation")
        if not isinstance(config["token"],str) or not re.fullmatch(r"ocp_trial_[A-Za-z0-9_-]{43}",config["token"]): raise ValueError("Trial key required")
        if not isinstance(config["catalog_sha256"],str) or not re.fullmatch(r"[0-9a-f]{64}",config["catalog_sha256"]): raise ValueError("Descriptor pin required")
        super().__init__(config["endpoint"],timeout=15,token=config["token"])
        self.expected=config["catalog_sha256"]

    def describe(self):
        value=super().describe()
        if value["kind"]=="failure": raise OCPError(value["error"]["code"])
        if digest(value)!=self.expected: raise OCPError("CATALOG_CHANGED")
        return value

    def execute(self,request):
        self.describe()  # No spend if the selected environment changed.
        return super().execute(request)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session",required=True)
    parser.add_argument("action",choices=["doctor","mcp"])
    args=parser.parse_args()
    try:
        adapter=InvitationClient(args.session)
        capability=adapter.describe()
        if args.action=="doctor":
            print(json.dumps({"status":"PASS","scope":"authenticated_discovery_only_no_solve",
                "capability":capability["capability"],"catalog_sha256":adapter.expected}))
        else:
            from .mcp_server import create_mcp
            create_mcp(adapter,name="OCP invited trial",instructions=
                "Use synthetic routing inputs only. Describe, request requirements, validate, execute, then evaluate. "
                "An execution spends the invitation quota. Keep the same request_id for the same request; "
                "never automatically retry after uncertainty or create a fresh ID to bypass it. "
                "No async jobs. Never request or display the key. Contact the inviter for recovery.").run(transport="stdio")
    except Exception as error:
        print(json.dumps(diagnostic(error)),file=sys.stderr);return 1
    return 0


if __name__=="__main__": sys.exit(main())
