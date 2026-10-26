"""Build a checker bundle from a real saved request/response and an exact artifact."""
import argparse
import hashlib
import json
from pathlib import Path
from conformance.core_contract import parse_json, validate_message


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace",required=True)
    parser.add_argument("--artifact",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    try:
        trace=parse_json(Path(args.trace).read_text())
        if set(trace)!={"request","response"}:raise ValueError("Invalid trace")
        for value in trace.values():validate_message(value)
        if trace["request"]["kind"]!="request" or trace["response"]["kind"]!="result":raise ValueError("Result trace required")
        bundle={"artifact_sha256":hashlib.sha256(Path(args.artifact).read_bytes()).hexdigest(),
                "implementation":trace["response"]["provenance"]["implementation"],
                "cases":[{"id":"own-engine-run",**trace}]}
        with open(args.out,"x") as stream:json.dump(bundle,stream,indent=2)
        print(json.dumps({"status":"WRITTEN","scope":"Run conformance.runner next; execution is not attested by a transcript."}))
        return 0
    except Exception:
        print(json.dumps({"status":"FAIL","code":"TRANSCRIPT_INPUT_INVALID","hint":"Use an actual request/result trace and exact artifact; choose a new --out path."}))
        return 1


if __name__=="__main__":raise SystemExit(main())
