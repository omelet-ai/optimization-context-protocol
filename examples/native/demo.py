"""Use installed native SDK/server and independent checker from a review bundle."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

from conformance.assessment import assess
from ocp_candidate.contract import parse_json
from ocp_candidate.native import NativeError
from ocp_runtime.native_server import LocalAPI

DOMAINS = {'routing-basic': 'routing-input.json', 'worker-scheduling': 'worker-input.json',
           'inventory-replenishment': 'inventory-input.json'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=DOMAINS)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--node', action='store_true', help='Use the optional installed TypeScript SDK from Node')
    parser.add_argument('--output', type=Path, help='Save the full result and independent report to a new JSON file')
    args = parser.parse_args()
    if args.input and not args.domain: parser.error('--input needs --domain')
    root = Path(__file__).resolve().parent
    if args.output and args.output.exists():
        print(json.dumps({'status': 'FAIL', 'code': 'OUTPUT_EXISTS', 'execute_calls': 0, 'model_calls': 0})); return 1
    inputs = {}
    for domain in ([args.domain] if args.domain else DOMAINS):
        try:
            inputs[domain] = parse_json((args.input or root / DOMAINS[domain]).read_text())
        except (ValueError, OSError, UnicodeError):
            print(json.dumps({'status': 'FAIL', 'code': 'INPUT_FILE_INVALID', 'domain': domain,
                'message': 'Provide a readable UTF-8 JSON input object; duplicate keys and non-finite numbers are rejected.',
                'execute_calls': 0, 'model_calls': 0})); return 1
    prepared = {}
    # Prepare and validate every selected input before spending any solver work.
    with LocalAPI() as local:
        for domain, data in inputs.items():
            api = local.client(domain)
            catalog = api.capabilities()
            request = catalog['requestTemplate']
            request.update(input=data, request_id=str(uuid.uuid4()))
            validation = api.validate(request)
            if not validation['valid']:
                print(json.dumps({'status': 'FAIL', 'code': 'INPUT_REJECTED', 'domain': domain,
                    'issues': validation['issues'], 'execute_calls': 0, 'model_calls': 0}));return 1
            prepared[domain] = request
        outcomes = []
        for domain, request in prepared.items():
            if args.node:
                # Ephemeral credentials only cross a local child stdin, never a command argument or a saved file.
                p = subprocess.run(['node', str(root / 'node_app.mjs')], cwd=root, input=json.dumps({
                    'baseUrl': local.client(domain).base, 'token': local.token, 'problem': request}),
                    capture_output=True, text=True, timeout=90)
                if p.returncode: raise ValueError('NODE_EXECUTION_FAILED')
                solved = json.loads(p.stdout)
            else:
                solved = local.client(domain).solve(request, tenant='local-engineer', idempotency_key=request['request_id'])
            response = solved['result']['result']
            check = assess(request, response)
            if check['status'] != 'PASS': raise ValueError('INDEPENDENT_CHECK_FAILED')
            metric = check['checks']['objective_recomputation']
            outcomes.append({'domain': domain, 'request': request, 'response': response, 'independent_check': check,
                'summary': {'job_status': solved['job']['status'], 'solution_status': response['status'],
                    'objective_value': metric['value'], 'objective_unit': metric.get('unit'),
                    'optimality': check['checks']['optimality']['status'],
                    'infeasibility': check['checks']['infeasibility']['status']}})
    result = {'status': 'PASS', 'execute_calls': len(outcomes), 'model_calls': 0, 'outcomes': outcomes}
    if args.output:
        with args.output.open('x') as stream: stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except NativeError as error:
        print(json.dumps({'status': 'FAIL', 'code': error.code,
            'message': 'The job may still exist after a transport error or wait timeout; do not resubmit blindly.'}), file=sys.stderr);sys.exit(1)
    except Exception:
        print(json.dumps({'status': 'FAIL', 'code': 'DEMO_FAILED'}), file=sys.stderr);sys.exit(1)
