"""Build a local BYO example wheel without modifying its source directory."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def build(output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ocp-worker-greedy-build-') as directory:
        stage = Path(directory)
        shutil.copyfile(ROOT / 'authoring/worker_greedy/pyproject.toml', stage / 'pyproject.toml')
        shutil.copytree(ROOT / 'authoring/worker_greedy/src', stage / 'src', ignore=shutil.ignore_patterns('__pycache__'))
        for name in ['LICENSE', 'NOTICE']:
            shutil.copyfile(ROOT / name, stage / name)
        result = subprocess.run([sys.executable, '-B', '-m', 'build', '--wheel', '--no-isolation', '--outdir', str(output), str(stage)],
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr)
    wheel = output / 'ocp_worker_greedy_example-0.1.0-py3-none-any.whl'
    return {'wheel': str(wheel), 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(build(ROOT / '.harness/work/dist')))
