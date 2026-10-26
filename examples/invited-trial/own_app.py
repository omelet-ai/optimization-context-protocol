"""Minimal app: discover, validate, execute, evaluate and independently verify."""
import argparse
import json
from pathlib import Path
from ocp_candidate import Client, OCPError, parse_json
from ocp_runtime.trial_client import InvitationClient, diagnostic
from conformance.coordinates import verify_result as verify_coordinates
from conformance.routing import verify_result as verify_basic


def trace_error(code):
    hints={"TRACE_EXISTS":"Choose a new --trace filename. Existing output was preserved; do not rerun an uncertain job with a new request ID.",
           "TRACE_DIRECTORY_MISSING":"Create the parent directory or choose an existing directory for --trace.",
           "TRACE_WRITE_FAILED":"Check --trace directory permissions. If execution already succeeded, preserve its request ID before retrying."}
    print(json.dumps({"status":"FAIL","code":code,"hint":hints[code]}))
    return 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True)
    parser.add_argument("--request-id",required=True)
    parser.add_argument("--session",help="Use the invited engine; omit for the local reference")
    parser.add_argument("--trace",help="Save request/result to a new file")
    args=parser.parse_args()
    try:problem=parse_json(Path(args.input).read_text())
    except (OSError,UnicodeError,OCPError):
        print(json.dumps({"status":"FAIL","code":"INPUT_INVALID","hint":"Check --input is readable UTF-8 JSON with unique keys and finite numbers."}));return 1
    trace=Path(args.trace) if args.trace else None
    if trace is not None:
        try:
            if trace.exists() or trace.is_symlink():return trace_error("TRACE_EXISTS")
            if not trace.parent.is_dir():return trace_error("TRACE_DIRECTORY_MISSING")
        except OSError:return trace_error("TRACE_WRITE_FAILED")
    try:
        if args.session:adapter=InvitationClient(args.session)
        else:
            from ocp_routing import RoutingAdapter, ORToolsBackend
            adapter=RoutingAdapter(ORToolsBackend())
        client=Client(adapter)
        requirements=client.requirements()
        if requirements["kind"]=="failure":print(json.dumps(requirements));return 1
        request=client.request(problem,request_id=args.request_id)
        validation=adapter.validate(request)
        if validation["kind"]!="validation" or not validation["valid"]:print(json.dumps(validation));return 1
        result=client.execute(problem,request_id=args.request_id)
        if result["kind"]=="failure":print(json.dumps(result));return 1
        checker={"routing.basic":verify_basic,"routing.coordinates":verify_coordinates}[request["domain_profile"]["id"]]
        checked=checker(request,result)
        evaluation=adapter.evaluate(request,result["solution"]) if result["solution"] is not None else None
        if trace is not None:
            try:
                with open(trace,"x") as stream:json.dump({"request":request,"response":result},stream)
            except FileExistsError:return trace_error("TRACE_EXISTS")
            except OSError:return trace_error("TRACE_WRITE_FAILED")
        # evaluated is a status string, never a boolean field; preserve null values.
        metrics=[] if evaluation is None or evaluation["kind"]!="evaluation" else evaluation["metrics"]
        print(json.dumps({"result":result,"evaluation":evaluation,"independent_check":checked,
                          "metrics":[{"id":m["id"],"status":m["status"],"value":m["value"]} for m in metrics]}))
        return 0 if result["solution"] is not None and evaluation is not None and evaluation["kind"]=="evaluation" else 1
    except Exception as error:
        print(json.dumps(diagnostic(error)));return 1


if __name__=="__main__":raise SystemExit(main())
