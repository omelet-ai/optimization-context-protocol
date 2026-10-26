"""One invited run, independently checked. Reuse request-id after uncertainty."""
import argparse
import json
from pathlib import Path
from ocp_candidate import Client, OCPError, parse_json
from ocp_candidate.contract import failure
from ocp_runtime.trial_client import InvitationClient, diagnostic
from conformance.coordinates import verify_result

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--session",required=True)
parser.add_argument("--input",required=True)
parser.add_argument("--request-id",required=True)
args=parser.parse_args()
try:
    # Reject ambiguous/non-finite input before even contacting the provider.
    problem=parse_json(Path(args.input).read_text())
except (OSError, UnicodeError, OCPError) as error:
    code=error.code if isinstance(error,OCPError) else "INPUT_UNREADABLE"
    print(json.dumps(failure(args.request_id,OCPError(code,message="Read a UTF-8 JSON input with unique keys and finite numbers; check --input."))))
    raise SystemExit(1)
try:
    client=Client(InvitationClient(args.session))
except Exception as error:
    print(json.dumps(diagnostic(error)))
    raise SystemExit(1)
request=client.request(problem,request_id=args.request_id,time_limit_ms=1000)
response=client.execute(problem,request_id=args.request_id,time_limit_ms=1000)
if response["kind"]=="failure":
    print(json.dumps(response));raise SystemExit(1)
checked=verify_result(request,response)
evaluation=client.adapter.evaluate(request,response["solution"]) if response["solution"] is not None else None
print(json.dumps({"result":response,"independent_check":checked,"evaluation":evaluation},ensure_ascii=False))
if response["solution"] is None or evaluation is None or evaluation["kind"]!="evaluation":raise SystemExit(1)
