"""Offline, provider-neutral request/result transcript verification with explicit scope."""

import argparse
import hashlib
import json
from pathlib import Path

from .core_contract import ContractError, parse_json, validate_message
from . import assignment, routing

SUITE = {"id":"ocp.transcript", "version":"0.1.0"}
CHECKERS = {("routing.basic","0.1.0"):routing.verify_result,
            ("assignment.fixture","0.1.0"):assignment.verify_result}


def verify_bundle(bundle, artifact_bytes):
    if not isinstance(bundle, dict) or set(bundle) != {"artifact_sha256","implementation","cases"}:
        raise ContractError("INVALID_BUNDLE")
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    if bundle["artifact_sha256"] != digest: raise ContractError("ARTIFACT_MISMATCH")
    if not isinstance(bundle["cases"], list) or not bundle["cases"]: raise ContractError("EMPTY_SUITE")
    checks, profiles, names = [], {}, set()
    for case in bundle["cases"]:
        if not isinstance(case, dict) or set(case) != {"id","request","response"} or not isinstance(case["id"],str) or not case["id"] or case["id"] in names:
            raise ContractError("INVALID_CASE")
        names.add(case["id"])
        try:
            request, response = case["request"], case["response"]
            validate_message(request)
            if request["kind"] != "request": raise ContractError("INVALID_RESULT")
            profile = request["domain_profile"]
            key = (profile["id"],profile["version"])
            profiles[key] = profile
            validate_message(response)
            if response["kind"] != "result": raise ContractError("INVALID_RESULT")
            checker = CHECKERS.get(key)
            if checker is None: raise ContractError("UNSUPPORTED_PROFILE")
            if response["provenance"]["implementation"] != bundle["implementation"]:
                raise ContractError("IMPLEMENTATION_MISMATCH")
            checker(request, response)
            checks.append({"id":case["id"],"status":"PASS","reason":"Transcript semantics independently checked; execution not attested"})
        except ContractError as error:
            checks.append({"id":case["id"],"status":"FAIL","reason":error.code})
    checks.extend([{"id":"execution-attestation","status":"NOT_TESTED","reason":"Offline transcript cannot prove this artifact produced the response"},
                   {"id":"other-profiles-bindings-engines","status":"NOT_TESTED","reason":"Only explicitly listed profile transcripts were checked"}])
    if not profiles:
        raise ContractError("NO_VALID_REQUEST_PROFILE")
    report = {"core_version":"0.1.0","kind":"conformance","implementation":bundle["implementation"],
              "artifact":{"sha256":digest},"suite":SUITE,"profiles":list(profiles.values()),"checks":checks}
    validate_message(report)
    return {"status":"FAIL" if any(check["status"]=="FAIL" for check in checks) else "PASS",
            "report":report, "scope":"Offline transcript semantics; not engine execution, blanket certification or publication approval"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()
    try:
        result = verify_bundle(parse_json(Path(args.bundle).read_text()), Path(args.artifact).read_bytes())
    except (ContractError, OSError, UnicodeError) as error:
        result = {"status":"FAIL","reason":error.code if isinstance(error,ContractError) else "INPUT_UNREADABLE"}
    print(json.dumps(result, allow_nan=False))
    return 0 if result["status"]=="PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
