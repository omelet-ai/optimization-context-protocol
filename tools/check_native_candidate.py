"""Independent installed-artifact preflight; does not advance historical H stages."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def check_notices(kit):
    """Verify actual distributable bytes, metadata and retained registry protection."""
    manifest = json.loads((kit / 'manifest.json').read_text())
    checked = 0
    for kind, name in manifest['python_wheels'].items():
        base = ROOT / 'sdk/native-contracts/python' if kind == 'contracts' else ROOT
        with zipfile.ZipFile(kit / name) as archive:
            for notice in ['LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md']:
                entries = [n for n in archive.namelist() if n.endswith('.dist-info/licenses/' + notice)]
                assert len(entries) == 1 and archive.read(entries[0]) == (base / notice).read_bytes(), (name, notice)
            metadata = archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))).decode()
            assert 'License-Expression: Apache-2.0' in metadata, name
            if kind == 'contracts': assert 'Private :: Do Not Upload' in metadata
        checked += 1
    for name in manifest['node_archives']:
        with tarfile.open(kit / name) as archive:
            metadata = json.load(archive.extractfile('package/package.json'))
            base = ROOT / 'sdk/native-contracts/typescript' if metadata['name'] == '@omelet/ocp-native-contracts' else ROOT
            assert metadata['license'] == 'Apache-2.0', name
            if metadata['name'] == '@omelet/ocp-native-contracts': assert metadata['private'] is True
            for notice in ['LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md']:
                assert archive.extractfile('package/' + notice).read() == (base / notice).read_bytes(), (name, notice)
        checked += 1
    return checked


def check(kit, wheelhouses, output, node=None, npm=None):
    kit = Path(kit).resolve(); output = Path(output).resolve()
    output.mkdir(exist_ok=False)
    bundle = output / 'bundle with spaces'; shutil.copytree(kit, bundle)
    home = output / 'empty-home'; home.mkdir()
    # /usr/bin can contain Node on CI/Linux. An empty executable search path
    # tests independence from Node without depending on the runner image.
    binary = output / 'python-only-bin'; binary.mkdir()
    environment = {'PATH': str(binary), 'HOME': str(home), 'PYTHONDONTWRITEBYTECODE': '1',
                   'PIP_CONFIG_FILE': os.devnull, 'PIP_NO_INDEX': '1'}
    notice_count = check_notices(kit)
    results = ['archive-notices']

    def run(label, argv, *, expected=0, env=None):
        p = subprocess.run(list(map(str, argv)), cwd=bundle, env=env or environment,
                           capture_output=True, text=True, timeout=300)
        (output / (label + '.log')).write_text(p.stdout + '\n' + p.stderr)
        if p.returncode != expected:
            raise AssertionError(label + ': ' + p.stdout[-1000:] + p.stderr[-2500:])
        return p.stdout

    install = [sys.executable, '-B', 'install.py']
    for wheelhouse in wheelhouses:
        install.extend(['--offline-wheelhouse', Path(wheelhouse).resolve()])
    if shutil.which('node', path=environment['PATH']):
        raise AssertionError('Python-only installation check requires PATH without Node')
    value = json.loads(run('install', install)); assert value['status'] == 'PASS'; results.append('install')
    python = bundle / '.native/bin/python'
    for name in ['binding_tests.py', 'server_tests.py', 'mcp_tests.py', 'inputs.json', 'vectors.json', 'contract-cases.json']:
        shutil.copy2(ROOT / 'tools/native_tests' / name, bundle / name)
    tests = 1 + notice_count
    for name in ['binding_tests', 'server_tests', 'mcp_tests']:
        report = json.loads(run(name, [python, '-I', '-B', name + '.py']).strip().splitlines()[-1])
        assert report['tests_run'] > 0 and not any(report[n] for n in ['errors', 'failures', 'skipped']), report
        tests += report['tests_run']; results.append(name)
    demo = json.loads(run('demo', [python, '-I', '-B', 'demo.py']))
    assert demo['status'] == 'PASS' and demo['execute_calls'] == 3 and demo['model_calls'] == 0
    tests += 1; results.append('demo')
    config = json.loads(run('mcp_config', [python, '-I', '-B', 'mcp_config.py']))
    assert config['mcpServers']['ocp-native-local']['command'] == str(python)
    tests += 1; results.append('mcp_config')
    authored = json.loads(run('authoring', [python, '-I', '-B', 'native_server_template.py', 'worker-input.json']))
    assert authored['response']['metrics'][0]['value'] == 7
    tests += 1; results.append('authoring')
    # Native applications must not get their HTTP server dependency through MCP.
    isolated = [sys.executable, '-B', ROOT / 'tools/native_tests/no_mcp_install.py',
                '--kit', kit, '--output', output / 'without-mcp']
    for directory in wheelhouses: isolated.extend(['--wheelhouse', Path(directory).resolve()])
    separate = json.loads(run('native-without-mcp', isolated))
    assert separate['status'] == 'PASS' and separate['mcp_installed'] is False
    tests += separate['tests_run']; results.append('native-without-mcp')
    # Separate installed checker: accepted actual solutions, rejected corrupted costs.
    independent = '''import json
from copy import deepcopy
from pathlib import Path
from conformance.assessment import assess
count=0
for name in ['python-transcripts.json','mcp-transcripts.json']:
 for item in json.loads(Path(name).read_text()).values():
  assert assess(item['request'],item['response'])['status']=='PASS';count+=1
  if item['response']['solution'] is not None:
   corrupted=deepcopy(item['response']);corrupted['metrics'][0]['value']+=1
   assert assess(item['request'],corrupted)['status']=='FAIL';count+=1
print(json.dumps({'checks':count}))
'''
    tests += json.loads(run('independent', [python, '-I', '-B', '-c', independent]))['checks']
    results.append('independent')
    if node:
        environment_node = dict(environment, PATH=str(Path(node).parent) + os.pathsep + os.defpath,
                                npm_config_ignore_scripts='true', npm_config_audit='false', npm_config_fund='false')
        for key in ['OCP_NPM_CACHE', 'OCP_NPM_OFFLINE']:
            if key in os.environ:
                environment_node[{'OCP_NPM_CACHE': 'npm_config_cache', 'OCP_NPM_OFFLINE': 'npm_config_offline'}[key]] = os.environ[key]
        archives = json.loads((bundle / 'manifest.json').read_text())['node_archives']
        assert len(archives) == 2
        run('node-install', [npm, 'install', '--ignore-scripts', '--save-exact', *[bundle / n for n in archives]], env=environment_node)
        for name in ['binding-contract.test.mjs', 'public-live.test.mjs']:
            shutil.copy2(ROOT / 'tools/native_tests' / name, bundle / name)
        upstream = (ROOT / 'tools/native_tests/upstream.test.ts').read_text()
        upstream = upstream.replace('../src/caller-trace.js', '@omelet/ocp-native-contracts').replace('../src/optimization-api/client.js', '@omelet/ocp-native-contracts')
        (bundle / 'upstream.test.mts').write_text(upstream)
        (bundle / 'sdk.test.mjs').write_text((ROOT / 'tools/native_tests/sdk.test.mjs').read_text().replace('@omelet/ocp-server-base', '@omelet/ocp-native-contracts'))
        shutil.copy2(ROOT / 'tools/native_tests/cancellation.test.mjs', bundle / 'cancellation.test.mjs')
        tap = run('node-contracts', [node, '--test', '--test-reporter=tap', 'binding-contract.test.mjs', 'sdk.test.mjs', 'upstream.test.mts', 'cancellation.test.mjs'], env=environment_node)
        counts = dict(re.findall(r'^# (tests|pass|fail|cancelled|skipped) (\d+)\s*$', tap, re.M))
        assert int(counts['tests']) > 0 and all(counts[k] == '0' for k in ['fail', 'cancelled', 'skipped']), counts
        tests += int(counts['tests']); results.append('node-contracts')
        value = json.loads(run('node-demo', [python, '-I', '-B', 'demo.py', '--node'], env=environment_node))
        assert value['status'] == 'PASS' and [v['response']['metrics'][0]['value'] for v in value['outcomes']] == [18, 7, 16]
        tests += 3; results.append('node-demo')
    manifest_sha = hashlib.sha256((kit / 'manifest.json').read_bytes()).hexdigest()
    report = {'status': 'PASS', 'tests_run': tests, 'errors': 0, 'failures': 0, 'skipped': 0,
              'checks': results, 'manifest_sha256': manifest_sha, 'node_checked': bool(node),
              'model_calls': 0, 'human_acceptance': 'NOT_RUN', 'publication_authorized': False,
              'scope': 'Fresh installed candidate on this host; standalone check, no historical gate promotion'}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', required=True); p.add_argument('--output', required=True)
    p.add_argument('--wheelhouse', action='append', required=True)
    p.add_argument('--node'); p.add_argument('--npm')
    args = p.parse_args()
    if bool(args.node) != bool(args.npm): p.error('--node and --npm must be used together')
    print(json.dumps(check(args.kit, args.wheelhouse, args.output, args.node, args.npm)))
