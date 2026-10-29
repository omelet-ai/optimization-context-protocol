"""Bounded policy for the one public, read-only CI workflow. No publishing rights."""
import json
import re

WORKFLOW = '.github/workflows/public-ci.yml'
ACTIONS = {
    'actions/checkout': '3d3c42e5aac5ba805825da76410c181273ba90b1',
    'actions/setup-python': '6d4fd22b20465ccc0f7354476588e8df7c9ca0e0',
    'actions/setup-node': '949feb2413d6458794dcd2491c4babbbce0c15c1',
}


def validate(content):
    # JSON is a YAML subset: using it here makes policy parsing unambiguous and
    # keeps verification available with the Python standard library alone.
    data = json.loads(content)
    if set(data) != {'name', 'on', 'permissions', 'concurrency', 'jobs'}:
        raise ValueError('CI_UNEXPECTED_TOP_LEVEL')
    if data['on'] != {'push': {'branches': ['main']}, 'pull_request': {}, 'workflow_dispatch': {}}:
        raise ValueError('CI_EVENTS')
    if data['permissions'] != {'contents': 'read'}:
        raise ValueError('CI_PERMISSIONS')
    if data['concurrency'] != {'group': 'public-ci-${{ github.workflow }}-${{ github.ref }}', 'cancel-in-progress': True}:
        raise ValueError('CI_CONCURRENCY')
    jobs = data['jobs']
    if set(jobs) != {'public-source', 'windows-boundary', 'required'}:
        raise ValueError('CI_JOBS')
    public = jobs['public-source']
    if public.get('strategy') != {'fail-fast': False, 'matrix': {'include': [
            {'os': 'ubuntu-24.04', 'python': '3.12.15'},
            {'os': 'macos-14', 'python': '3.12.10'}]}}:
        raise ValueError('CI_MATRIX')
    if public['runs-on'] != '${{ matrix.os }}' or jobs['windows-boundary']['runs-on'] != 'windows-2022':
        raise ValueError('CI_RUNNER')
    required = jobs['required']
    if (required.get('needs') != ['public-source', 'windows-boundary'] or required.get('if') != '${{ always() }}'
            or required['runs-on'] != 'ubuntu-24.04'):
        raise ValueError('CI_REQUIRED_GATE')
    if required['steps'] != [{'name': 'Require every lane to succeed',
                             'env': {'PUBLIC_RESULT': '${{ needs.public-source.result }}',
                                     'WINDOWS_RESULT': '${{ needs.windows-boundary.result }}'},
                             'run': 'test "$PUBLIC_RESULT" = success && test "$WINDOWS_RESULT" = success',
                             'shell': 'bash'}]:
        raise ValueError('CI_REQUIRED_GATE_COMMAND')
    for job_id, job in jobs.items():
        if set(job) - {'name', 'runs-on', 'timeout-minutes', 'strategy', 'steps', 'needs', 'if'}:
            raise ValueError('CI_JOB_OPTIONS')
        if not 1 <= job['timeout-minutes'] <= 25:
            raise ValueError('CI_TIMEOUT')
        for step in job['steps']:
            if set(step) - {'name', 'uses', 'with', 'run', 'shell', 'env'}:
                raise ValueError('CI_STEP_OPTIONS')
            if 'uses' in step:
                action, sep, pin = step['uses'].partition('@')
                if not sep or ACTIONS.get(action) != pin or not re.fullmatch('[a-f0-9]{40}', pin):
                    raise ValueError('CI_ACTION_PIN')
                if action == 'actions/checkout' and step.get('with') != {'persist-credentials': False}:
                    raise ValueError('CI_CHECKOUT_CREDENTIALS')
                if action == 'actions/setup-python' and step.get('with') != {
                        'python-version': '${{ matrix.python }}' if job_id == 'public-source' else '3.12.10'}:
                    raise ValueError('CI_PYTHON_VERSION')
    text = json.dumps(data)
    if any(word in text for word in ['secrets.', 'pull_request_target', 'self-hosted', 'upload-artifact',
                                     'continue-on-error', 'environment', 'id-token', 'deploy', 'publish']):
        raise ValueError('CI_PRIVILEGED_OPERATION')
    return data
