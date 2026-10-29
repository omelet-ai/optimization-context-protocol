"""Public-source checks, separate from private migration and human acceptance.

Run with Python 3.12. Online mode downloads pinned public wheels; --wheelhouse
uses only the given local dependencies. Never reads an original Foundry tree.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from ci_policy import WORKFLOW, validate
from verify_repository import verify

ROOT = Path(__file__).resolve().parents[1]
UNIT_CHECKS = ['tools/tests/test_harness.py', 'tools/tests/test_repository_selection.py',
               'tools/tests/test_public_ci.py', 'tools/tests/test_preview.py',
               'tools/check_h01.py', 'tools/check_h02.py', 'tools/check_h03.py',
               'tools/check_h05.py', 'tools/check_h26.py', 'tools/check_h27.py', 'tools/check_h28.py']


def passed(report, minimum=1):
    if (report.get('status') != 'PASS' or type(report.get('tests_run')) is not int
            or report['tests_run'] < minimum
            or any(report.get(k) != 0 for k in ('errors', 'failures', 'skipped'))):
        raise ValueError('INCOMPLETE_OR_FAILED_CHECK')
    return report


def require_success(label, result):
    """Keep failures diagnosable on ephemeral runners without artifact uploads."""
    if result.returncode:
        # Children receive only the explicit clean environment above. Outputs
        # come from public-source synthetic checks; no service secrets are sent.
        print(result.stdout[-4000:] + result.stderr[-4000:], file=sys.stderr)
        raise RuntimeError(label + ' failed; inspect the diagnostic output or local log')


def check(output, wheelhouses=(), with_typescript=False):
    if sys.version_info[:2] != (3, 12) or os.name != 'posix':
        raise ValueError('PYTHON_3_12_POSIX_REQUIRED')
    selection = verify()
    validate((ROOT / WORKFLOW).read_text())
    work = Path(output).resolve()
    if work == ROOT or work.is_relative_to(ROOT):
        raise ValueError('OUTPUT_MUST_BE_OUTSIDE_SOURCE')
    work.mkdir(parents=True, exist_ok=False)
    source = work / 'public source'; source.mkdir()
    for name in json.loads((ROOT / 'provenance/repository-selection.json').read_text())['files']:
        target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    home = work / 'empty-home'; home.mkdir()
    scratch = work / 'tmp'; scratch.mkdir()
    env = {'PATH': os.environ.get('PATH', os.defpath), 'HOME': str(home), 'TMPDIR': str(scratch),
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'GIT_OPTIONAL_LOCKS': '0',
           'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
           'npm_config_ignore_scripts': 'true', 'npm_config_audit': 'false', 'npm_config_fund': 'false',
           'OCP_NPM_CACHE': os.environ.get('OCP_NPM_CACHE', str(work / 'npm-cache'))}
    if os.environ.get('OCP_NPM_OFFLINE') == '1': env['OCP_NPM_OFFLINE'] = '1'
    reports = {}
    def run(label, argv, timeout=600, report=False):
        print('[public-ci] ' + label, file=sys.stderr, flush=True)
        result = subprocess.run(list(map(str, argv)), cwd=source, env=env, capture_output=True,
                                text=True, timeout=timeout)
        (work / (label + '.log')).write_text(result.stdout + '\n' + result.stderr)
        require_success(label, result)
        if report:
            reports[label] = passed(json.loads(result.stdout.strip().splitlines()[-1]))
        return result.stdout
    wheels = work / 'wheels'; wheels.mkdir()
    if wheelhouses:
        for directory in wheelhouses:
            for path in Path(directory).resolve().glob('*.whl'):
                target = wheels / path.name
                if target.exists() and target.read_bytes() != path.read_bytes():
                    raise ValueError('CONFLICTING_DEPENDENCY_WHEELS')
                shutil.copyfile(path, target)
    else:
        run('download', [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--no-cache-dir',
                         '--index-url', 'https://pypi.org/simple', '--dest', wheels,
                         '-r', 'tools/requirements-dev.lock', 'fastapi==0.135.1', 'annotated-doc==0.0.4'])
    dependency_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels.glob('*.whl')}
    if not dependency_hashes: raise ValueError('EMPTY_WHEELHOUSE')
    # Test and build from a new environment, not the maintainer's interpreter packages.
    run('venv', [sys.executable, '-m', 'venv', work / 'build-env'])
    python = work / 'build-env/bin/python'
    env.update(PIP_NO_INDEX='1', PIP_FIND_LINKS=wheels.as_uri())
    run('dependencies', [python, '-m', 'pip', 'install', '--no-index', '--no-compile', '--no-cache-dir',
                         '--find-links', wheels, '-r', 'tools/requirements-dev.lock',
                         'fastapi==0.135.1', 'annotated-doc==0.0.4'])
    for name in UNIT_CHECKS:
        run(Path(name).stem, [python, '-B', name], report=True)
    build = [python, '-B', 'tools/build_native_candidate.py', '--output', work / 'kit']
    if with_typescript: build.append('--with-typescript')
    run('build-native', build)
    argv = [python, '-B', 'tools/check_native_candidate.py', '--kit', work / 'kit',
            '--wheelhouse', wheels, '--output', work / 'native']
    if with_typescript:
        node, npm = (shutil.which(n) for n in ('node', 'npm'))
        if not node or not npm: raise ValueError('NODE_NPM_REQUIRED_FOR_OPTIONAL_LANE')
        argv += ['--node', node, '--npm', npm]
    run('installed-native', argv, timeout=900, report=True)
    run('inspection', [python, '-B', 'tools/check_inspection_candidate.py', '--kit', work / 'kit',
                       '--wheelhouse', wheels, '--output', work / 'inspection'], timeout=900, report=True)
    report = {'status': 'PASS', 'tests_run': sum(r['tests_run'] for r in reports.values()),
              'errors': 0, 'failures': 0, 'skipped': 0, 'platform': platform.platform(),
              'machine': platform.machine(), 'python': platform.python_version(),
              'node_checked': with_typescript, 'model_calls': 0, 'human_acceptance': 'NOT_RUN',
              'scope': 'Public source and installed synthetic consumers; no historical gate promotion',
              'source_tree_sha256': selection['tree_content_sha256'], 'dependency_wheels': dependency_hashes,
              'kit_manifest_sha256': hashlib.sha256((work / 'kit/manifest.json').read_bytes()).hexdigest(),
              'checks': {k: v['tests_run'] for k, v in reports.items()}}
    (work / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output'); parser.add_argument('--wheelhouse', action='append', default=[])
    parser.add_argument('--with-typescript', action='store_true'); args = parser.parse_args()
    output = args.output or str(Path(tempfile.mkdtemp(prefix='ocp-public-ci-')) / 'run')
    try:
        print(json.dumps(check(output, args.wheelhouse, args.with_typescript)))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'FAIL', 'code': type(error).__name__, 'reason': str(error)}))
        raise SystemExit(1)
