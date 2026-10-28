"""Fresh Linux amd64 Python/MCP installation, with networking disabled throughout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def inside():
    import platform
    kit = Path('/tmp/bundle with spaces'); shutil.copytree('/input', kit)
    home = Path('/tmp/empty-home'); home.mkdir()
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(home), 'PIP_CONFIG_FILE': '/dev/null',
           'PYTHONDONTWRITEBYTECODE': '1', 'PIP_NO_INDEX': '1'}
    assert shutil.which('node', path=env['PATH']) is None
    results = []

    def call(args, label, expected=0):
        p = subprocess.run(list(map(str, args)), cwd=kit, env=env, capture_output=True, text=True, timeout=180)
        Path('/output', label + '.log').write_text(p.stdout + '\n' + p.stderr)
        if p.returncode != expected: raise AssertionError(label + ': ' + p.stdout[-1500:] + p.stderr[-2500:])
        value = json.loads(p.stdout)
        Path('/output', label + '.json').write_text(json.dumps(value, indent=2))
        results.append(label)
        return value

    installed = call([sys.executable, '-B', 'install.py', '--offline-wheelhouse', '/wheels'], 'install')
    assert installed['status'] == 'PASS'
    python = kit / '.native/bin/python'
    call([python, '-B', 'scenarios.py'], 'inputs')
    expected = {'routing-basic': (12, 20, 'feasible'), 'worker-scheduling': (6, 9, 'optimal'),
                'inventory-replenishment': (10, 13, 'optimal')}
    for domain, (base, changed, status) in expected.items():
        for mode in ['app', 'mcp']:
            for variant in ['base', 'changed', 'infeasible', 'invalid']:
                script = 'demo.py' if mode == 'app' else 'mcp_walkthrough.py'
                v = call([python, '-I', '-B', script, '--domain', domain, '--input',
                          f'my-inputs/{domain}-{variant}.json'], domain + '-' + mode + '-' + variant,
                         expected=1 if variant == 'invalid' else 0)
                assert v['model_calls'] == 0
                if variant == 'invalid':
                    assert v['code'] == 'INPUT_REJECTED' and v['execute_calls'] == 0 and v['issues'][0]['fieldPath']
                    continue
                value = v['outcomes'][0] if mode == 'app' else v
                assert value['independent_check']['status'] == 'PASS'
                checks = value['independent_check']['checks']
                if variant == 'infeasible':
                    assert value['response']['status'] == 'infeasible' and value['response']['solution'] is None
                    assert checks['infeasibility']['status'] == 'PASS'
                    assert checks['objective_recomputation']['value'] is None
                else:
                    assert value['response']['status'] == status
                    assert checks['objective_recomputation']['value'] == (base if variant == 'base' else changed)
                    assert checks['feasibility']['status'] == 'PASS'
                if mode == 'mcp': assert v['replayed'] and v['execute_calls'] == 1
    config = call([python, '-B', 'mcp_config.py'], 'config')
    assert config['mcpServers']['ocp-native-local']['command'] == str(python)
    assert not (home / '.codex').exists()
    report = {'status': 'PASS', 'tests_run': len(results), 'errors': 0, 'failures': 0, 'skipped': 0,
              'platform': platform.platform(), 'architecture': platform.machine(), 'python': platform.python_version(),
              'model_calls': 0, 'scope': 'Linux amd64 under Docker emulation; no native arm64/Windows or human claim'}
    Path('/output/result.json').write_text(json.dumps(report, indent=2))



if __name__ == '__main__': inside()
