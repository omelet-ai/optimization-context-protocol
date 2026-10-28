"""Checks a running Optimization API against Capability Contract v1 (the contract suite over HTTP).

    python -m foundry_capability_contract.conformance --url http://127.0.0.1:8495 --base-path /v1 \\
        --token-env MY_API_TOKEN [--fixtures tests/fixtures/contract.json] [--mutating] [--json]

By default it only reads and sends requests the API must refuse (no job is created): health,
readiness, version, authentication, the catalog digest, the tenant and Idempotency-Key rules, the
error envelope, and validate (with fixtures). ``--mutating`` also submits jobs, under tenants made
for the run: the lifecycle, idempotent replay and conflict, tenant isolation, cancellation (with a
``slowProblem`` fixture) and evaluation. The token is read from the variable ``--token-env`` names,
never from the command line. Fixtures: ``{"problem", "otherProblem"?, "slowProblem"?, "evaluation"?}``.
With jsonschema installed, every answer is also checked against the contract's OpenAPI schemas.
Exit 0 when every check passes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

__all__ = ["READ_ONLY_CHECKS", "MUTATING_CHECKS", "main"]

READ_ONLY_CHECKS = (
    "check_ops",
    "check_auth",
    "check_capabilities_digest",
    "check_validate",
    "check_tenant_required",
    "check_idempotency_key_required",
    "check_error_envelope",
)
MUTATING_CHECKS = (
    "check_job_lifecycle",
    "check_idempotent_replay",
    "check_idempotency_conflict",
    "check_tenant_isolation",
    "check_cancel",
    "check_evaluation",
)


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m foundry_capability_contract.conformance", description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", required=True, help="the API's origin, e.g. http://127.0.0.1:8495")
    parser.add_argument("--base-path", required=True, help="the problem type's base path, e.g. /v1")
    parser.add_argument("--token-env", required=True, help="the environment variable that holds a service token")
    parser.add_argument("--fixtures", type=Path, help="JSON with problem, otherProblem, slowProblem, evaluation")
    parser.add_argument("--mutating", action="store_true", help="also submit jobs (under tenants made for this run)")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds a job may take to finish")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser.parse_args(argv)


def _schemas() -> tuple[dict[str, Any] | None, str]:
    try:
        import jsonschema  # noqa: F401

        from .testing.openapi import contract_openapi

        return contract_openapi(), "answers checked against the contract's OpenAPI schemas"
    except (ImportError, FileNotFoundError) as reason:
        return None, f"answers not checked against the OpenAPI schemas ({type(reason).__name__}: {reason})"


def main(argv: list[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        print(f"{args.token_env} holds no token", file=sys.stderr)
        return 2
    fixtures: dict[str, Any] = json.loads(args.fixtures.read_text(encoding="utf-8")) if args.fixtures else {}
    if args.mutating and "problem" not in fixtures:
        print("--mutating needs --fixtures with a problem", file=sys.stderr)
        return 2

    import httpx

    from .testing.suite import ContractSuite

    openapi, schema_note = _schemas()
    run = uuid.uuid4().hex[:8]
    checks = list(READ_ONLY_CHECKS) + (list(MUTATING_CHECKS) if args.mutating else [])
    if "problem" not in fixtures:
        checks.remove("check_validate")
    if args.mutating and "slowProblem" not in fixtures:
        checks.remove("check_cancel")

    results: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=60.0) as client:
        suite = ContractSuite(
            client,
            base_path=args.base_path.rstrip("/"),
            token=token,
            problem=fixtures.get("problem", {}),
            other_problem=fixtures.get("otherProblem"),
            slow_problem=fixtures.get("slowProblem"),
            evaluation=fixtures.get("evaluation"),
            solve_timeout=args.timeout,
            tenant=f"conformance-{run}-a",
            other_tenant=f"conformance-{run}-b",
            openapi=openapi,
        )
        for check in checks:
            try:
                getattr(suite, check)()
                results.append({"check": check, "ok": True})
            except AssertionError as failure:
                results.append({"check": check, "ok": False, "detail": str(failure)[:500]})
            except Exception as error:  # noqa: BLE001 - reported as the check's failure
                results.append({"check": check, "ok": False, "detail": "".join(traceback.format_exception_only(type(error), error)).strip()[:500]})

    passed = sum(result["ok"] for result in results)
    report = {"ok": passed == len(results), "passed": passed, "checks": results, "mutating": args.mutating, "schemas": schema_note}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for result in results:
            print(f"{'PASS' if result['ok'] else 'FAIL'}  {result['check']}{'' if result['ok'] else '  ' + result['detail']}")
        print(f"{passed}/{len(results)} checks passed ({'with' if args.mutating else 'without'} jobs; {schema_note})")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
