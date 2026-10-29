"""Prepare immutable local preview assets. Never tags, uploads or records acceptance."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile

from verify_repository import verify as verify_source

ROOT = Path(__file__).resolve().parents[1]
PLAN = 'docs/development/preview-release.json'
FORM = 'docs/users/PREVIEW_REVIEW_FORM.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def read_plan(root=ROOT):
    plan = json.loads((root / PLAN).read_text())
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+-preview\.[0-9]+', plan['release_id']):
        raise ValueError('INVALID_PREVIEW_VERSION')
    if plan['target_repository'] != 'omelet-ai/optimization-context-protocol':
        raise ValueError('WRONG_REPOSITORY')
    if any(plan[k] is not False for k in ('publication_authorized', 'registry_publication_authorized')):
        raise ValueError('PREPARATION_CANNOT_AUTHORIZE_PUBLICATION')
    if plan['maturity'] != 'developer-preview':
        raise ValueError('NOT_A_STABLE_RELEASE')
    return plan


def blank_form(value):
    if value['external_developer_acceptance'] != 'NOT_RUN' or value['internal_owner_acceptance'] != 'NOT_RUN':
        raise ValueError('HUMAN_ACCEPTANCE_MUST_REMAIN_PENDING')
    if value['participant_alias'] is not None or value['maintainer_review'] is not None or value['findings']:
        raise ValueError('NOT_A_BLANK_REVIEW_FORM')
    if value['candidate_sha256'] is not None or any(v is not None for v in value['environment'].values()):
        raise ValueError('NOT_A_BLANK_REVIEW_FORM')
    if [t['id'] for t in value['tasks']] != ['install', 'own-application', 'own-engine', 'mcp-sdk', 'inspection-owner-review']:
        raise ValueError('MISSING_ACCEPTANCE_TASK')
    if any(t['status'] != 'NOT_STARTED' or t['evidence'] or t['help_needed'] is not None or t['minutes'] is not None
           for t in value['tasks']):
        raise ValueError('TASK_ACCEPTANCE_MUST_REMAIN_PENDING')


def files(directory):
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('SYMLINK_IN_ASSET')
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = sha(path)
    return result


def archive(directory, destination):
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for name in files(directory):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            output.writestr(info, (directory / name).read_bytes())


def archive_inventory(path):
    result = {}
    with zipfile.ZipFile(path) as archive_file:
        for entry in archive_file.infolist():
            name = entry.filename
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or p.as_posix() != name or name in result:
                raise ValueError('UNSAFE_ARCHIVE_PATH')
            if not stat.S_ISREG(entry.external_attr >> 16):
                raise ValueError('NON_REGULAR_ARCHIVE_ENTRY')
            result[name] = hashlib.sha256(archive_file.read(entry)).hexdigest()
    return result


def verify(directory):
    """Integrity check only; checksums do not authenticate the publisher."""
    directory = Path(directory)
    plan = read_plan(directory / 'source')
    metadata = json.loads((directory / 'assets/preview.json').read_text())
    if metadata['plan'] != plan or metadata['status'] != 'PREPARED_NOT_PUBLISHED':
        raise ValueError('PREVIEW_PLAN_DRIFT')
    kit = directory / 'kit'
    manifest = json.loads((kit / 'manifest.json').read_text())
    actual = files(kit)
    if actual.pop('manifest.json') != metadata['kit_manifest_sha256'] or actual != manifest['files']:
        raise ValueError('KIT_INVENTORY_DRIFT')
    blank_form(json.loads((kit / 'REVIEW_FORM.json').read_text()))
    source = files(directory / 'source')
    if source != metadata['source_files'] or hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest() != metadata['source_tree_sha256']:
        raise ValueError('SOURCE_INVENTORY_DRIFT')
    selected = json.loads((directory / 'source/provenance/repository-selection.json').read_text())['files']
    if set(source) != set(selected):
        raise ValueError('SOURCE_NOT_EXPLICITLY_SELECTED')
    check_versions(kit, plan)
    for kind, folder in [('source', 'source'), ('native', 'kit')]:
        name = f'ocp-{kind}-{plan["release_id"]}.zip'
        path = directory / 'assets' / name
        if sha(path) != metadata['archives'][name] or archive_inventory(path) != files(directory / folder):
            raise ValueError('ARCHIVE_INVENTORY_DRIFT')
    sums = ''.join(f'{digest}  {name}\n' for name, digest in sorted(metadata['archives'].items()))
    if (directory / 'assets/SHA256SUMS').read_text() != sums:
        raise ValueError('CHECKSUM_LIST_DRIFT')
    if {p.name for p in (directory / 'assets').iterdir()} != set(metadata['archives']) | {'preview.json', 'SHA256SUMS'}:
        raise ValueError('UNLISTED_RELEASE_ASSET')
    return {'status': 'PASS', 'scope': 'archive integrity only; not installation, signature or human acceptance',
            'release_id': plan['release_id'], 'kit_manifest_sha256': metadata['kit_manifest_sha256'],
            'source_tree_sha256': metadata['source_tree_sha256'], 'publication_authorized': False}


def check_versions(kit, plan):
    manifest = json.loads((kit / 'manifest.json').read_text())
    for kind, key in [('sdk', 'python_sdk'), ('contracts', 'native_contracts_python')]:
        with zipfile.ZipFile(kit / manifest['python_wheels'][kind]) as archive_file:
            metadata = archive_file.read(next(n for n in archive_file.namelist() if n.endswith('.dist-info/METADATA'))).decode()
            if re.search(r'^Version: (.+)$', metadata, re.M).group(1) != plan[key]:
                raise ValueError('PACKAGE_VERSION_DRIFT')
    versions = {'ocp-candidate': plan['typescript_sdk'], '@omelet/ocp-native-contracts': plan['native_contracts_typescript']}
    for name in manifest['node_archives']:
        with tarfile.open(kit / name) as archive_file:
            meta = json.load(archive_file.extractfile('package/package.json'))
            if meta['version'] != versions[meta['name']]:
                raise ValueError('PACKAGE_VERSION_DRIFT')
    origin = json.loads((kit / 'ORIGIN.json').read_text())
    if origin['foundry_commit'] != plan['foundry_contract_pin']:
        raise ValueError('CONTRACT_PIN_DRIFT')


def prepare(output, with_typescript=False):
    plan = read_plan()
    blank_form(json.loads((ROOT / FORM).read_text()))
    selection = verify_source()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'; source.mkdir()
    for name in json.loads((ROOT / 'provenance/repository-selection.json').read_text())['files']:
        dest = source / name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    kit = output / 'kit'
    command = [sys.executable, '-B', str(source / 'tools/build_native_candidate.py'), '--output', str(kit)]
    if with_typescript:
        command.append('--with-typescript')
    result = subprocess.run(command, cwd=source, capture_output=True, text=True, timeout=600)
    (output / 'build.log').write_text(result.stdout + '\n' + result.stderr)
    if result.returncode:
        raise RuntimeError('BUILD_FAILED; inspect local build.log')
    manifest = json.loads((kit / 'manifest.json').read_text())
    # These are blank instructions/forms, never completed execution evidence.
    shutil.copyfile(ROOT / FORM, kit / 'REVIEW_FORM.json')
    shutil.copyfile(ROOT / 'docs/users/PREVIEW_START.md', kit / 'START_HERE.md')
    manifest['files'].update({n: sha(kit / n) for n in ('REVIEW_FORM.json', 'START_HERE.md')})
    write(kit / 'manifest.json', manifest)
    assets = output / 'assets'; assets.mkdir()
    archives = {}
    for kind, folder in [('source', source), ('native', kit)]:
        name = f'ocp-{kind}-{plan["release_id"]}.zip'
        archive(folder, assets / name); archives[name] = sha(assets / name)
    write(assets / 'preview.json', {'status': 'PREPARED_NOT_PUBLISHED', 'plan': plan,
          'source_tree_sha256': selection['tree_content_sha256'], 'source_files': files(source),
          'kit_manifest_sha256': sha(kit / 'manifest.json'), 'archives': archives})
    (assets / 'SHA256SUMS').write_text(''.join(f'{h}  {n}\n' for n, h in sorted(archives.items())))
    verify(output)
    return {'status': 'PREPARED_NOT_PUBLISHED', 'directory': str(output), 'release_id': plan['release_id'],
            'source_tree_sha256': selection['tree_content_sha256'], 'kit_manifest_sha256': sha(kit / 'manifest.json'),
            'publication_authorized': False, 'model_calls': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['build', 'verify']); p.add_argument('--directory', required=True)
    p.add_argument('--with-typescript', action='store_true'); args = p.parse_args()
    print(json.dumps(prepare(args.directory, args.with_typescript) if args.action == 'build' else verify(args.directory)))
