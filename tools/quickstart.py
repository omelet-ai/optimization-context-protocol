"""One-command Python/MCP source installation. Standard library only; no Node.

Creates separate build and installed environments under a NEW/empty directory.
Existing files, failed environments and host MCP configuration are preserved.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


class SetupError(ValueError):
    def __init__(self, code, hint):
        self.code, self.hint = code, hint


def setup(destination, wheelhouse=None):
    if sys.version_info[:2] != (3, 12):
        raise SetupError('PYTHON_VERSION_UNSUPPORTED', 'Use Python 3.12 on macOS/Linux; Windows is not supported.')
    if os.name != 'posix':
        raise SetupError('PLATFORM_NOT_SUPPORTED', 'Use macOS/Linux with Python 3.12; Windows is not supported.')
    target = Path(destination).expanduser().absolute()
    aliases = {Path('/var'): Path('/private/var'), Path('/tmp'): Path('/private/tmp')}
    for path in (target, *target.parents):
        if path.is_symlink() and (path == target or aliases.get(path) != path.resolve()):
            raise SetupError('OUTPUT_SYMLINK', 'Choose a new direct directory; existing symlink destinations are not supported.')
    target = target.resolve()
    if target == ROOT or target.is_relative_to(ROOT):
        raise SetupError('OUTPUT_IN_SOURCE', 'Choose a directory outside the source checkout.')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise SetupError('ENVIRONMENT_EXISTS', 'Use the existing kit/.agent/bin/python, or choose a new empty directory. Nothing was overwritten.')
    if wheelhouse is None and os.environ.get('PIP_NO_INDEX', '').lower() in ('1', 'true', 'yes', 'on'):
        wheelhouse = os.environ.get('PIP_FIND_LINKS')
        if not wheelhouse:
            raise SetupError('OFFLINE_WHEELHOUSE_REQUIRED', 'Provide --offline-wheelhouse with build and runtime dependencies.')
    if wheelhouse:
        wheelhouse = Path(wheelhouse).expanduser().resolve()
        if not wheelhouse.is_dir():
            raise SetupError('OFFLINE_WHEELHOUSE_INVALID', 'Use one local wheel directory, never a URL.')
    target.mkdir(parents=True, exist_ok=True)
    build_env = target / 'build'
    print('[setup] Creating a Python build environment; Node/npm are not needed.', file=sys.stderr, flush=True)
    venv.EnvBuilder(with_pip=True, symlinks=True).create(build_env)
    python = build_env / 'bin/python'
    env = {'PATH': os.defpath, 'HOME': str(Path.home()), 'PYTHONDONTWRITEBYTECODE': '1',
           'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
    if wheelhouse:
        env.update(PIP_NO_INDEX='1', PIP_FIND_LINKS=str(wheelhouse))
    command = [str(python), '-B', '-m', 'pip', 'install', '--no-compile', '--no-cache-dir',
               'build==1.4.0', 'setuptools==80.9.0', 'wheel==0.46.3']
    subprocess.run(command, env=env, check=True, stdout=sys.stderr, timeout=480)
    print('[setup] Building the Python/MCP kit from selected source.', file=sys.stderr, flush=True)
    subprocess.run([str(python), '-B', str(ROOT / 'tools/build_invitation_kit.py'),
                    '--target', 'python', '--output', str(target / 'kit')],
                   cwd=ROOT, env=env, check=True, stdout=sys.stderr, timeout=240)
    command = [str(python), '-B', str(target / 'kit/start.py'), '--mcp', '--venv', str(target / 'kit/.agent')]
    if wheelhouse:
        command += ['--offline-wheelhouse', str(wheelhouse)]
    # start.py owns the final machine-readable real solve/check result on stdout.
    subprocess.run(command, cwd=target / 'kit', env=env, check=True, timeout=720)
    print('Ready. Work from: ' + str(target / 'kit'), file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, help='New or empty directory outside the checkout')
    parser.add_argument('--offline-wheelhouse', help='Pinned build and runtime wheels for your Python/OS/CPU')
    args = parser.parse_args()
    try:
        setup(args.directory, args.offline_wheelhouse)
        return 0
    except (SetupError, OSError, subprocess.SubprocessError) as error:
        code, hint = (error.code, error.hint) if isinstance(error, SetupError) else (
            'SETUP_FAILED', 'Inspect preceding progress. Preserve the incomplete directory and retry explicitly with a new destination; no automatic retry occurred.')
        print(json.dumps({'status': 'FAIL', 'code': code, 'hint': hint}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
