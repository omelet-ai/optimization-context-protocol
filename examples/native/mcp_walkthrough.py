"""Run a real MCP client workflow without an LLM; the server stays on localhost."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import uuid

from mcp import Client, StdioServerParameters
from conformance.assessment import assess, load_registry
from conformance.core_contract import ContractError
from ocp_candidate.contract import parse_json


async def run(domain, data, *, worker_engine='reference', extension=None, checker_factory=None):
    events = []
    module = 'ocp_worker_greedy' if worker_engine == 'byo' else 'ocp_runtime.native_mcp'
    command_args = ['-I', '-B', '-m', module] if extension is None else ['-I', '-B', '-m', 'ocp_runtime.native_extension', '--extension', extension]
    checker_registry = load_registry(checker_factory)
    parameters = StdioServerParameters(command=sys.executable, args=command_args,
        env={'PATH': os.defpath, 'HOME': os.environ['HOME'], 'PYTHONDONTWRITEBYTECODE': '1'})
    async with Client(parameters, read_timeout_seconds=90) as host:
        async def call(name, arguments, *, expected_error=False):
            answer = await host.call_tool(name, arguments)
            events.append({'tool': name, 'is_error': answer.is_error})
            if answer.is_error != expected_error: raise ValueError('MCP_OPERATION_FAILED: ' + name)
            return answer.structured_content
        catalog = (await call('ocp_native_context', {'domain': domain}))['catalog']
        try:
            checker_registry.resolve(catalog['domainProfile'])
        except ContractError as error:
            return {'status': 'FAIL', 'code': error.code, 'execute_calls': 0, 'model_calls': 0, 'tool_calls': events}
        requirements = await call('ocp_native_requirements', {'domain': domain, 'selection': catalog['selectionTemplate']})
        problem = catalog['requestTemplate']
        problem.update(input=data, request_id=str(uuid.uuid4()))
        validation = await call('ocp_native_validate', {'domain': domain, 'problem': problem})
        if not validation['valid']:
            return {'status': 'FAIL', 'code': 'INPUT_REJECTED', 'issues': validation['issues'],
                    'execute_calls': 0, 'model_calls': 0, 'tool_calls': events}
        submitted = await call('ocp_native_submit', {'domain': domain, 'problem': problem, 'idempotency_key': problem['request_id']})
        job = submitted['job']; deadline = asyncio.get_running_loop().time() + 60
        while job['status'] not in ('succeeded', 'infeasible', 'failed', 'cancelled'):
            if asyncio.get_running_loop().time() >= deadline: raise ValueError('WAIT_TIMEOUT_TERMINATION_UNCONFIRMED')
            await asyncio.sleep(.05)
            job = await call('ocp_native_job', {'domain': domain, 'job_id': job['jobId']})
        result = await call('ocp_native_result', {'domain': domain, 'job_id': job['jobId']})
        response = result['result']
        report = assess(problem, response, registry=checker_registry)
        # A repeated POST with the same payload/key must return the same real job.
        replay = await call('ocp_native_submit', {'domain': domain, 'problem': problem, 'idempotency_key': problem['request_id']})
        if not replay['replayed'] or replay['job']['jobId'] != job['jobId']: raise ValueError('REPLAY_MISMATCH')
        evaluation = await call('ocp_native_evaluate', {'domain': domain, 'job_id': job['jobId']},
                                expected_error=response['solution'] is None)
        if response['solution'] is None and evaluation['code'] != 'NO_SOLUTION': raise ValueError('EXPECTED_NO_SOLUTION')
        return {'status': report['status'], 'execute_calls': 1, 'model_calls': 0,
                'domain': domain, 'requirements': requirements, 'request': problem, 'response': response,
                'job': job, 'independent_check': report, 'provider_evaluation': evaluation,
                'replayed': True, 'tool_calls': events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--extension', help='Trusted installed domain MODULE:FACTORY')
    parser.add_argument('--checker-factory', help='Trusted installed checker MODULE:FACTORY')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--worker-engine', choices=('reference', 'byo'), default='reference')
    args = parser.parse_args()
    if args.worker_engine == 'byo' and args.domain != 'worker-scheduling':
        parser.error('--worker-engine byo needs --domain worker-scheduling')
    if args.extension and args.worker_engine != 'reference': parser.error('Choose --extension or --worker-engine byo')
    if not args.extension and args.domain not in ['routing-basic', 'worker-scheduling', 'inventory-replenishment']: parser.error('Unknown built-in domain; supply --extension')
    result = asyncio.run(run(args.domain, parse_json(args.input.read_text()), worker_engine=args.worker_engine, extension=args.extension, checker_factory=args.checker_factory))
    print(json.dumps(result, allow_nan=False))
    return result['status'] != 'PASS'


if __name__ == '__main__': raise SystemExit(main())
