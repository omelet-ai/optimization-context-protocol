"""App A: a standalone no-key Python consumer; accepts the caller's JSON input."""

import argparse
import json
import os
from pathlib import Path

from ocp_candidate import Client, OCPError, parse_json
from ocp_candidate.contract import failure
from ocp_routing import ORToolsBackend, RoutingAdapter
from ocp_routing.coordinates import CoordinatesAdapter, CoordinateLibraryBackend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="routing.basic input JSON file")
    parser.add_argument("--profile", choices=["basic","coordinates"], default="basic", help="Local engine profile; HTTP endpoint advertises its own profile")
    parser.add_argument("--endpoint", help="Optional HTTP provider; trial key from OCP_TRIAL_TOKEN environment")
    parser.add_argument("--configuration", help="optional explicit configuration JSON file")
    parser.add_argument("--time-limit-ms", type=int, default=1000)
    parser.add_argument("--request-id", default="app-a")
    args = parser.parse_args()
    try:
        problem = parse_json(Path(args.input).read_text())
        config = parse_json(Path(args.configuration).read_text()) if args.configuration else None
        if args.endpoint:
            from ocp_candidate.http_adapter import HTTPAdapter
            adapter = HTTPAdapter(args.endpoint,token=os.environ.get("OCP_TRIAL_TOKEN"))
        elif args.profile=="coordinates":
            adapter = CoordinatesAdapter(CoordinateLibraryBackend(ORToolsBackend()))
        else:
            adapter = RoutingAdapter(ORToolsBackend())
        result = Client(adapter).execute(
            problem, configuration=config, time_limit_ms=args.time_limit_ms, request_id=args.request_id)
    except (OSError, UnicodeError):
        result = failure("app-a", OCPError("INVALID_DATA", message="Cannot read input JSON"))
    except OCPError as error:
        result = failure("app-a", error)
    print(json.dumps(result, allow_nan=False))
    return 2 if result["kind"] == "failure" else 0


if __name__ == "__main__":
    raise SystemExit(main())
