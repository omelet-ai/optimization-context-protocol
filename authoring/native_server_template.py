"""Local reference of the BYO registration points; replace provider explicitly.

This example reuses worker scheduling only to make the template executable.
It does not claim to be a second independent scheduling engine.
"""
from ocp_runtime.native_domain import ReferenceDomain, run_provider
from ocp_runtime.native_server import LocalAPI, Registration
from ocp_planning import worker_adapter


def solve(problem):
    # Module-level function: spawned worker imports this without running main.
    return run_provider(worker_adapter(), problem)


def main(problem):
    domain = ReferenceDomain(worker_adapter(), problem_type='my-worker-engine')
    with LocalAPI([Registration(domain, solve)]) as local:
        api = local.client(domain.problem_type)
        request = api.capabilities()['requestTemplate']
        request.update(input=problem, request_id='byo-example')
        return request, api.solve(request, tenant='my-app', idempotency_key='byo-example')['result']['result']


if __name__ == '__main__':
    import json, sys
    request, response = main(json.load(open(sys.argv[1])))
    print(json.dumps({'request': request, 'response': response}))
