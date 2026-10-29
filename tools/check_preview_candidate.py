"""H63: one exact public-source ZIP candidate, fresh installs and real consumers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from prepare_preview import ROOT, prepare, verify, files, write
from verify_repository import verify as verify_source


def check(output, wheelhouses, linux_wheels, docker, node, npm):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('OUTPUT_EXISTS')
    if not all((docker, node, npm)):
        raise ValueError('DOCKER_NODE_NPM_REQUIRED')
    # Verify macOS dependencies too; installation must not silently use another set.
    expected = json.loads((ROOT / 'tools/dependency-wheels.json').read_text())['sha256']
    expected.update(json.loads((ROOT / 'tools/native-dependencies.json').read_text()))
    actual = {}
    for directory in wheelhouses:
        for path in Path(directory).glob('*.whl'):
            if path.name in actual:
                raise ValueError('DUPLICATE_DEPENDENCY')
            actual[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('MACOS_DEPENDENCY_DRIFT')
    output.mkdir(parents=True)
    candidate = output / 'candidate'
    built = prepare(candidate, with_typescript=True)
    verify(candidate)
    # Execute the bytes someone would actually download, not the build directory.
    extracted = output / 'extracted'; extracted.mkdir()
    with zipfile.ZipFile(candidate / 'assets' / f'ocp-native-{built["release_id"]}.zip') as archive:
        archive.extractall(extracted)
    if files(extracted) != files(candidate / 'kit'):
        raise ValueError('EXTRACTED_ASSET_DRIFT')
    source = candidate / 'source'
    reports = {}
    common = ['--kit', str(extracted)]
    mac = [arg for path in wheelhouses for arg in ('--wheelhouse', str(Path(path).resolve()))]
    linux = ['--wheelhouse', str(Path(linux_wheels).resolve()), '--docker', docker]
    commands = [
        ('mac-native', 'check_native_candidate.py', common + mac + ['--node', node, '--npm', npm]),
        ('mac-inspection', 'check_inspection_candidate.py', common + mac),
        ('linux-native', 'check_native_linux.py', common + linux),
        ('linux-inspection', 'check_inspection_candidate.py', common + linux + ['--linux']),
    ]
    for label, script, args in commands:
        p = subprocess.run([sys.executable, '-B', str(source / 'tools' / script), *args,
                            '--output', str(output / label)], cwd=source,
                           capture_output=True, text=True, timeout=1200)
        (output / (label + '.log')).write_text(p.stdout + '\n' + p.stderr)
        if p.returncode:
            raise RuntimeError(label + ' failed; inspect ' + str(output / (label + '.log')))
        report = json.loads(p.stdout)
        digest = report.get('manifest_sha256', report.get('kit_manifest_sha256'))
        if (report['status'] != 'PASS' or report['tests_run'] <= 0 or
                any(report[k] != 0 for k in ('errors', 'failures', 'skipped')) or
                report['model_calls'] != 0 or digest != built['kit_manifest_sha256']):
            raise ValueError('INVALID_OR_WRONG_ARTIFACT_EVIDENCE: ' + label)
        reports[label] = report
    integrity = verify(candidate)
    if verify_source()['tree_content_sha256'] != built['source_tree_sha256']:
        raise ValueError('SOURCE_CHANGED_DURING_CHECK')
    result = {'status': 'PASS', 'tests_run': sum(r['tests_run'] for r in reports.values()),
              'errors': 0, 'failures': 0, 'skipped': 0, 'model_calls': 0,
              'source_tree_sha256': built['source_tree_sha256'],
              'artifact_sha256': built['kit_manifest_sha256'], 'release_id': built['release_id'],
              'scope': 'Exact extracted preview ZIP; macOS Python/Node, offline Linux amd64 Python/MCP; not human acceptance',
              'external_developer_acceptance': 'NOT_RUN', 'internal_owner_acceptance': 'NOT_RUN',
              'published': False, 'registry_published': False, 'site_deployed': False,
              'lanes': {name: r['tests_run'] for name, r in reports.items()}}
    write(output / 'result.json', result)
    write(output / 'evidence.json', {'reports': reports, 'integrity': integrity})
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output'); p.add_argument('--wheelhouse', action='append')
    p.add_argument('--linux-wheelhouse', default=str(ROOT / '.harness/work/preview-linux-wheels'))
    p.add_argument('--docker', default=shutil.which('docker') or str(Path.home() / '.docker/bin/docker'))
    p.add_argument('--node', default=os.environ.get('OCP_NODE') or shutil.which('node'))
    p.add_argument('--npm', default=os.environ.get('OCP_NPM') or shutil.which('npm'))
    args = p.parse_args()
    # H63 uses a new work directory each time; failed attempts remain available.
    output = Path(args.output) if args.output else Path(tempfile.mkdtemp(prefix='ocp-preview-')).resolve() / 'check'
    report = check(output, args.wheelhouse or [ROOT / '.harness/work/wheels', ROOT / '.harness/work/preview-native-wheels'],
                   args.linux_wheelhouse, args.docker, args.node, args.npm)
    if not args.output:
        write(ROOT / '.harness/work/preview-latest.json', {'directory': str(output), 'report': report})
    print(json.dumps(report))
