"""Install a reviewed local native bundle; no Node, model, or host-config edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import venv


def verify(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('format') != 'ocp-native-review-kit/1' or manifest.get('publication_authorized') is not False:
        raise ValueError('KIT_INVALID')
    for name, digest in manifest['files'].items():
        path = root / name
        if (not re.fullmatch(r'[A-Za-z0-9_.+-]+', name) or path.is_symlink()
                or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError('KIT_CHANGED')
    wheels = manifest['python_wheels']
    if set(wheels) != {'sdk', 'contracts', 'checker'} or any(n not in manifest['files'] or not n.endswith('.whl') for n in wheels.values()):
        raise ValueError('KIT_INVALID')
    return wheels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', default='.native')
    parser.add_argument('--offline-wheelhouse', action='append', default=[])
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12): raise ValueError('PYTHON_3_12_REQUIRED')
    if os.name != 'posix': raise ValueError('PLATFORM_NOT_SUPPORTED')
    root = Path(__file__).resolve().parent
    destination = Path(args.venv).absolute()
    if destination.exists() or destination.is_symlink(): raise ValueError('ENVIRONMENT_EXISTS')
    wheels = verify(root)
    sources = []
    for value in args.offline_wheelhouse:
        path = Path(value).resolve()
        if not path.is_dir(): raise ValueError('OFFLINE_WHEELHOUSE_INVALID')
        sources += ['--find-links', str(path)]
    venv.EnvBuilder(with_pip=True, symlinks=True).create(destination)
    python = destination / 'bin/python'
    command = [str(python), '-B', '-m', 'pip', 'install', '--no-compile', '--disable-pip-version-check', '--no-cache-dir', '-c', str(root / 'constraints.txt')]
    if sources: command += ['--no-index', *sources]
    command += [str(root / wheels['contracts']), str(root / wheels['sdk']) + '[reference,mcp,native]', str(root / wheels['checker'])]
    env = {'PATH': os.defpath, 'HOME': str(Path.home()), 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_CONFIG_FILE': os.devnull}
    env.update({k: os.environ[k] for k in ['PIP_NO_INDEX', 'PIP_FIND_LINKS'] if k in os.environ})
    subprocess.run(command, check=True, stdout=sys.stderr, env=env, timeout=300)
    subprocess.run([str(python), '-B', '-m', 'pip', 'check'], check=True, stdout=sys.stderr, env=env, timeout=30)
    print(json.dumps({'status': 'PASS', 'scope': 'installation only', 'python': str(python), 'model_calls': 0}))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(json.dumps({'status': 'FAIL', 'code': str(error) if isinstance(error, ValueError) else 'INSTALL_FAILED',
                          'hint': 'Keep any partial environment for diagnosis; choose a new --venv path to retry.'}), file=sys.stderr)
        sys.exit(1)
