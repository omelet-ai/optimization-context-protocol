"""Prepare an exact OCP request from explicit spherical-distance CSV inputs.

Run with the installed candidate Python. This command validates but never solves.
"""
import argparse
import json
from pathlib import Path
import sys

from ocp_candidate import Client
from ocp_runtime.coordinate_input import coordinates_from_csv
from ocp_runtime.providers import make_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('depot', 'visits', 'vehicles'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--distance-model', required=True, choices=['haversine'])
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    try:
        def read(path):
            with path.open('rb') as source:
                value = source.read(65537)
            if len(value) > 65536:
                raise ValueError('CSV_SIZE_LIMIT')
            return value.decode('utf-8')
        data = coordinates_from_csv(read(args.depot), read(args.visits), read(args.vehicles),
                                    distance_model=args.distance_model)
        client = Client(make_provider('routing.coordinates'))
        request = client.request(data, request_id=args.request_id, time_limit_ms=1000)
        checked = client.adapter.validate(request)
        if not checked['valid']:
            print(json.dumps(checked), file=sys.stderr); return 1
        print(json.dumps(request, indent=2, ensure_ascii=False)); return 0
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'INVALID_INPUT', 'code': getattr(error, 'code', str(error))}), file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
