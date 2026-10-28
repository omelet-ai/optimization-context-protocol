"""Fresh native app installation must not depend on the optional MCP extra."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv


def check(kit, output, wheelhouses):
    output = Path(output).resolve(); output.mkdir(exist_ok=False)
    kit = Path(kit).resolve(); manifest = json.loads((kit / 'manifest.json').read_text())
    environment = {'PATH': os.defpath, 'HOME': str(output), 'PYTHONDONTWRITEBYTECODE': '1',
                   'PIP_CONFIG_FILE': os.devnull, 'PIP_NO_INDEX': '1'}
    venv.EnvBuilder(with_pip=True, symlinks=False).create(output / 'venv')
    python = output / 'venv/bin/python'
    argv = [python, '-B', '-m', 'pip', 'install', '--no-index', '--no-cache-dir', '--no-compile',
            '-c', kit / 'constraints.txt']
    for directory in wheelhouses: argv += ['--find-links', Path(directory).resolve()]
    argv += [kit / manifest['python_wheels']['contracts'],
             str(kit / manifest['python_wheels']['sdk']) + '[native,reference]',
             kit / manifest['python_wheels']['checker']]
    p = subprocess.run(list(map(str, argv)), env=environment, capture_output=True, text=True, timeout=120)
    (output / 'install.log').write_text(p.stdout + p.stderr)
    if p.returncode: raise RuntimeError('Native-only install failed: ' + p.stderr[-2000:])
    subprocess.run([python, '-I', '-B', '-c', 'import importlib.util; assert importlib.util.find_spec("mcp") is None'],
                   env=environment, check=True)
    for name in ['demo.py', 'node_app.mjs', 'routing-input.json', 'worker-input.json', 'inventory-input.json']:
        shutil.copy2(kit / name, output / name)
    p = subprocess.run([python, '-I', '-B', output / 'demo.py'], cwd=output, env=environment,
                       capture_output=True, text=True, timeout=120)
    (output / 'demo.log').write_text(p.stdout + p.stderr)
    if p.returncode: raise RuntimeError('Native-only app failed: ' + p.stderr[-2000:])
    result = json.loads(p.stdout)
    assert result['status'] == 'PASS' and result['execute_calls'] == 3
    report = {'status': 'PASS', 'tests_run': 3, 'mcp_installed': False, 'model_calls': 0}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', required=True); p.add_argument('--output', required=True)
    p.add_argument('--wheelhouse', action='append', required=True); a = p.parse_args()
    print(json.dumps(check(a.kit, a.output, a.wheelhouse)))
