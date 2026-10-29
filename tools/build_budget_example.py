"""Build three local extension wheels; never publish or modify canonical sources."""
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
    output = Path(output_dir).resolve(); output.mkdir(parents=True, exist_ok=True)
    records = {}
    for component in ['profile', 'engine', 'checker']:
        with tempfile.TemporaryDirectory(prefix='ocp-budget-build-') as temp:
            stage = Path(temp)
            source = ROOT / 'authoring/budget_example' / component
            shutil.copyfile(source / 'pyproject.toml', stage / 'pyproject.toml')
            shutil.copytree(source / 'src', stage / 'src', ignore=shutil.ignore_patterns('__pycache__'))
            for name in ['LICENSE', 'NOTICE']: shutil.copyfile(ROOT / name, stage / name)
            result = subprocess.run([sys.executable, '-B', '-m', 'build', '--wheel', '--no-isolation', '--outdir', str(output), str(stage)],
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True, timeout=60)
            if result.returncode: raise RuntimeError(result.stderr)
        wheel = output / ('ocp_budget_' + component + '_example-0.1.0-py3-none-any.whl')
        records[component] = {'wheel': str(wheel), 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}
    return records


if __name__ == '__main__': print(json.dumps(build(ROOT / '.harness/work/dist')))
