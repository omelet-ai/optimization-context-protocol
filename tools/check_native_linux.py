"""Check an exact kit in the pinned offline Linux image; no project checkout mounts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(kit, wheels, output, docker):
    kit, wheels, output = (Path(p).resolve() for p in (kit, wheels, output))
    dependencies = json.loads((ROOT / 'tools/linux-dependencies.json').read_text())
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels.glob('*.whl')}
    if hashes != dependencies['files']:
        raise ValueError('Linux dependency wheelhouse differs from the reviewed hashes')
    output.mkdir(exist_ok=False)
    argv = [docker, 'run', '--rm', '--pull=never', '--platform=linux/amd64', '--network=none',
            '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=256',
            '--memory=2g', '--cpus=2', '--user', f'{os.getuid()}:{os.getgid()}',
            '--tmpfs', '/tmp:rw,exec,size=1g,mode=1777', '-v', f'{kit}:/input:ro',
            '-v', f'{wheels}:/wheels:ro', '-v', f'{output}:/output:rw',
            '-v', f'{ROOT / "tools/native_tests/linux_install.py"}:/check.py:ro',
            dependencies['image'], 'python', '-B', '/check.py']
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1000)
    (output / 'container.log').write_text(p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError('Linux check failed; see ' + str(output / 'container.log'))
    report = json.loads((output / 'result.json').read_text())
    report.update(image=dependencies['image'], network='none',
                  manifest_sha256=hashlib.sha256((kit / 'manifest.json').read_bytes()).hexdigest())
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['kit', 'wheelhouse', 'output']: p.add_argument('--' + name, required=True)
    p.add_argument('--docker', default='docker'); args = p.parse_args()
    print(json.dumps(run(args.kit, args.wheelhouse, args.output, args.docker)))
