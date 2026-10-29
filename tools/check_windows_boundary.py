"""Run on Windows: check honest unsupported-platform errors, never claim support."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check():
    if os.name != 'nt' or sys.version_info[:2] != (3, 12):
        raise ValueError('WINDOWS_PYTHON_3_12_RUNNER_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='ocp-windows-boundary-') as folder:
        work = Path(folder)
        existing = work / 'existing'; existing.mkdir()
        sentinel = existing / 'keep.txt'; sentinel.write_text('preserve me', encoding='utf-8')
        for destination in [work / 'new', existing]:
            for script, flag, code in [('examples/native/install.py', '--venv', 'PLATFORM_NOT_SUPPORTED'),
                                       ('tools/quickstart.py', '--directory', 'PLATFORM_NOT_SUPPORTED')]:
                result = subprocess.run([sys.executable, '-B', str(ROOT / script), flag, str(destination)],
                                        cwd=work, capture_output=True, text=True, timeout=30)
                report = json.loads(result.stderr.strip().splitlines()[-1])
                if result.returncode != 1 or report['status'] != 'FAIL' or report['code'] != code:
                    raise AssertionError('PLATFORM_DIAGNOSTIC_MISMATCH')
                if 'Windows' not in report['hint'] or (work / 'new').exists() or sentinel.read_text() != 'preserve me':
                    raise AssertionError('PLATFORM_BOUNDARY_CHANGED_FILES')
        if sorted(p.relative_to(work).as_posix() for p in work.rglob('*')) != ['existing', 'existing/keep.txt']:
            raise AssertionError('UNEXPECTED_OUTPUT')
    return {'status': 'PASS', 'tests_run': 4, 'errors': 0, 'failures': 0, 'skipped': 0,
            'platform': platform.platform(), 'scope': 'unsupported Windows diagnostics and preservation only',
            'windows_install_supported': False, 'model_calls': 0, 'human_acceptance': 'NOT_RUN'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.parse_args()
    print(json.dumps(check()))
