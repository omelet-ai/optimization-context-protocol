"""Build a local native preview kit from public source using only this source tree.

No Foundry checkout, Git operation, registry upload, credentials or model call.
Python-only is the default; --with-typescript adds the optional Node artifacts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from build_candidate import build as sdk_build
from build_conformance import build as checker_build
from build_worker_greedy import build as worker_build
from build_budget_example import build as budget_build

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'sdk/native-contracts'
PIN = '7547036d1bc9464d6c43a9bdf7cff0a78e8560d7'
SDK_VERSION = '0.1.1.dev1'
TS_VERSION = '0.1.1-native.7547036d1bc9.review.1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def call(argv, cwd, environment):
    p = subprocess.run(list(map(str, argv)), cwd=cwd, env=environment,
                       capture_output=True, text=True, timeout=300)
    if p.returncode:
        raise RuntimeError(Path(str(argv[0])).name + ': ' + p.stdout[-2000:] + p.stderr[-3000:])
    return p.stdout


def verify_origins():
    python = NATIVE / 'python/src/foundry_capability_contract'
    record = json.loads((python / 'ORIGIN.json').read_text())
    if record['commit'] != PIN:
        raise ValueError('Native Python pin changed')
    prefix = 'shared/ocp-contracts/capability-contract/python/src/foundry_capability_contract/'
    for name, digest in record['files'].items():
        relative = name.removeprefix(prefix) if name.startswith(prefix) else 'capability-contract-v1.json'
        if sha(python / relative) != digest:
            raise ValueError('Native Python source changed: ' + name)
    typescript = NATIVE / 'typescript'
    record = json.loads((typescript / 'ORIGIN.json').read_text())
    if record['commit'] != PIN or record['proposal']['upstream_accepted'] is not False:
        raise ValueError('Native TypeScript provenance changed')
    for name, entry in record['files'].items():
        if sha(typescript / name) != entry['packaged_source_sha256']:
            raise ValueError('Native TypeScript source changed: ' + name)


def typescript_build(output, staging, environment):
    node = os.environ.get('OCP_NODE', 'node')
    npm = os.environ.get('OCP_NPM', 'npm')
    if Path(node).is_absolute():
        environment['PATH'] = str(Path(node).parent) + os.pathsep + environment['PATH']
    environment.update(npm_config_ignore_scripts='true', npm_config_audit='false', npm_config_fund='false')
    if 'OCP_NPM_CACHE' in os.environ:
        environment['npm_config_cache'] = os.environ['OCP_NPM_CACHE']
    if os.environ.get('OCP_NPM_OFFLINE') == '1':
        environment['npm_config_offline'] = 'true'
    chain = staging / 'toolchain'; chain.mkdir()
    for source, target in [('build-package.json', 'package.json'), ('build-package-lock.json', 'package-lock.json')]:
        shutil.copy2(NATIVE / 'typescript' / source, chain / target)
    call([npm, 'ci', '--ignore-scripts'], chain, environment)
    native = staging / 'contracts'; shutil.copytree(NATIVE / 'typescript', native)
    deps = native / 'node_modules'; deps.mkdir()
    for name in ['zod', '@types']:
        (deps / name).symlink_to(chain / 'node_modules' / name, target_is_directory=True)
    call([node, chain / 'node_modules/typescript/bin/tsc', '-p', native], native, environment)
    name = json.loads(call([npm, 'pack', '--json', '--ignore-scripts'], native, environment))[0]['filename']
    shutil.copy2(native / name, output / name)
    sdk = staging / 'sdk'; shutil.copytree(ROOT / 'sdk/typescript', sdk)
    # Install the unchanged Core dependency lock before adding the native export.
    call([npm, 'ci', '--ignore-scripts'], sdk, environment)
    namespace = sdk / 'node_modules/@omelet'; namespace.mkdir(exist_ok=True)
    (namespace / 'ocp-native-contracts').symlink_to(native, target_is_directory=True)
    shutil.copy2(sdk / 'native/entry.mts', sdk / 'src/native.mts')
    meta = json.loads((sdk / 'package.json').read_text())
    meta.update(version=TS_VERSION, engines={'node': '^22.0.0 || ^24.0.0'})
    native_meta = json.loads((native / 'package.json').read_text())
    meta['dependencies'][native_meta['name']] = native_meta['version']
    meta['exports'] = {'.': {'types': './dist/client.d.ts', 'default': './dist/client.js'},
                       './native': {'types': './dist/native.d.mts', 'import': './dist/native.mjs'}}
    write(sdk / 'package.json', meta)
    config = json.loads((sdk / 'tsconfig.json').read_text())
    config['include'].append('src/**/*.mts'); write(sdk / 'tsconfig.json', config)
    call([node, sdk / 'node_modules/typescript/bin/tsc'], sdk, environment)
    (sdk / 'dist/schemas').mkdir()
    shutil.copy2(ROOT / 'spec/schemas/core-0.1.schema.json', sdk / 'dist/schemas/core-0.1.schema.json')
    for notice in ['LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(ROOT / notice, sdk / notice)
    packed = json.loads(call([npm, 'pack', '--json', '--ignore-scripts'], sdk, environment))[0]['filename']
    shutil.copy2(sdk / packed, output / packed)
    return [name, packed]


def build(output, with_typescript=False):
    verify_origins()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new output directory; existing artifacts are never overwritten')
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='ocp-native-build-') as temp:
        staging = Path(temp)
        environment = {key: os.environ[key] for key in ['PATH', 'TMPDIR'] if key in os.environ}
        environment.update(HOME=str(staging / 'home'), PYTHONDONTWRITEBYTECODE='1')
        Path(environment['HOME']).mkdir()
        # Build from a disposable copy so setuptools never writes to canonical source.
        contracts = staging / 'python'; shutil.copytree(NATIVE / 'python', contracts)
        call([sys.executable, '-B', '-m', 'build', '--wheel', '--no-isolation', '--outdir', output, contracts], staging, environment)
        sdk = Path(sdk_build(output, version=SDK_VERSION)['wheel'])
        checker = Path(checker_build(output)['wheel'])
        worker = Path(worker_build(output)['wheel'])
        budget = budget_build(output)
        node_files = typescript_build(output, staging, environment) if with_typescript else []
    mappings = {'install.py': 'examples/native/install.py', 'demo.py': 'examples/native/demo.py',
                'project.py': 'examples/native/project.py', 'inspection.py': 'examples/native/inspection.py',
                'PROJECT_GUIDE.md': 'docs/users/NATIVE_PROJECT_WORKFLOW.md',
                'INSPECTION_GUIDE.md': 'docs/users/NATIVE_INSPECTION_ACCEPTANCE.md',
                'inspection-workers.csv': 'examples/native/inspection-workers.csv',
                'inspection-tasks.csv': 'examples/native/inspection-tasks.csv',
                'inspection-costs.csv': 'examples/native/inspection-costs.csv',
                'byo_worker_scenarios.py': 'examples/native/byo_worker_scenarios.py',
                'BYO_WORKER.md': 'docs/users/NATIVE_BYO_WORKER.md',
                'PROFILE_EXTENSION.md': 'docs/users/NATIVE_PROFILE_EXTENSION.md',
                'budget-input.json': 'examples/native/budget-input.json',
                'mcp_config.py': 'examples/native/mcp_config.py', 'node_app.mjs': 'examples/native/node_app.mjs',
                'scenarios.py': 'examples/native/scenarios.py', 'mcp_walkthrough.py': 'examples/native/mcp_walkthrough.py',
                'native_server_template.py': 'authoring/native_server_template.py',
                'README.md': 'docs/users/NATIVE_LOCAL_CANDIDATE.md',
                'WORKED_EXAMPLES.md': 'docs/users/NATIVE_THREE_DOMAIN_WALKTHROUGH.md',
                'EXTERNAL_EVALUATION.md': 'docs/users/NATIVE_EXTERNAL_EVALUATION.md',
                'COMPATIBILITY.md': 'spec/bindings/FOUNDRY_NATIVE_V1_CANDIDATE.md',
                'LICENSE_SCOPE.md': 'sdk/native-contracts/LICENSE_SCOPE.md'}
    for dest, source in mappings.items():
        shutil.copy2(ROOT / source, output / dest)
    for source, target in [('cases/routing/basic-matrix.json', 'routing'), ('cases/worker/small.json', 'worker'),
                           ('cases/inventory/small.json', 'inventory')]:
        write(output / (target + '-input.json'), json.loads((ROOT / source).read_text())['input'])
    (output / 'constraints.txt').write_text((ROOT / 'tools/requirements-dev.lock').read_text() + '\nfastapi==0.135.1\nannotated-doc==0.0.4\n')
    write(output / 'ORIGIN.json', {'foundry_commit': PIN, 'typescript_proposal': 'cancel-uncertainty-1',
          'upstream_accepted': False, 'source': 'sdk/native-contracts in this source tree',
          'publication_authorized': False, 'source_publication_authorized': True})
    contracts_wheel = next(output.glob('ocp_foundry_contracts_candidate-*.whl'))
    write(output / 'manifest.json', {'format': 'ocp-native-review-kit/1', 'publication_authorized': False, 'source_publication_authorized': True,
          'python_wheels': {'sdk': sdk.name, 'contracts': contracts_wheel.name, 'checker': checker.name},
          'example_wheels': {'worker_greedy': worker.name,
                            **{'budget_' + name: Path(value['wheel']).name for name, value in budget.items()}},
          'node_archives': node_files,
          'files': {p.name: sha(p) for p in sorted(output.iterdir())}})
    return {'directory': str(output), 'files': len(list(output.iterdir())), 'manifest_sha256': sha(output / 'manifest.json'),
            'typescript_built': with_typescript, 'foundry_checkout_required': False, 'publication_authorized': False, 'source_publication_authorized': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--with-typescript', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.with_typescript)))
