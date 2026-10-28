"""Validate the proposed source inventory without granting publication rights."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

from verify_repository import FORBIDDEN, PATTERNS

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'provenance/native-publication.json'


def verify(root=ROOT, require_approval=False):
    root = Path(root).resolve()
    record = json.loads((root / POLICY).read_text())
    if record['repository'] != 'omelet-ai/optimization-context-protocol' or record['scope'] != 'native_github_source':
        raise ValueError('Unexpected publication target')
    files = record['proposed_files']
    if not files or len(files) != len(set(files)) or POLICY not in files:
        raise ValueError('Invalid explicit inventory')
    hashes = {}
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or path.as_posix() != name:
            raise ValueError('Invalid source path')
        if name.startswith(FORBIDDEN) or any(p.startswith('.env') or p in {'.git', 'node_modules', '__pycache__', '.venv'} for p in path.parts):
            raise ValueError('Forbidden source path: ' + name)
        if path.suffix.lower() in {'.whl', '.tgz', '.zip', '.gz', '.pyc', '.key', '.pem', '.db'}:
            raise ValueError('Not reviewable source: ' + name)
        target = root / name
        if any(p.is_symlink() for p in [target, *target.parents] if p != root and p.is_relative_to(root)):
            raise ValueError('Symlink source: ' + name)
        data = target.read_bytes()
        if len(data) > 1024 * 1024:
            raise ValueError('Unexpected source size: ' + name)
        for label, pattern in PATTERNS.items():
            if re.search(pattern, data.decode('utf-8')):
                raise ValueError('Review required: ' + name + ' (' + label + ')')
        hashes[name] = hashlib.sha256(data).hexdigest()
    # New source cannot inherit a prior Core-only license/publication approval.
    approvals = record['approvals']
    needed = ['source_rights', 'license_and_notices', 'patent_disclosure', 'exact_github_publication']
    if set(approvals) != set(needed) or any(type(v) is not bool for v in approvals.values()):
        raise ValueError('Invalid approval fields')
    pending = [name for name in needed if approvals[name] is not True]
    if require_approval and pending:
        raise PermissionError('Native publication is not approved: ' + ', '.join(pending))
    origins = json.loads((root / 'provenance/native-origin-inventory.json').read_text())
    for name, source in origins['files'].items():
        if require_approval and source.get('rights') != 'OWNER_CONFIRMED_APACHE_2_0_2026-10-28':
            raise PermissionError('Selected source rights are not approved: ' + name)
        if name not in hashes or hashes[name] != source['candidate_sha256']:
            raise ValueError('Extracted source or transformation drift: ' + name)
    return {'status': 'PASS', 'scope': 'github_source_inventory_only',
            'files': len(hashes), 'source_digest': hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            'publication_authorized': not pending, 'pending_approvals': pending, 'files_sha256': hashes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT); parser.add_argument('--require-approval', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root, args.require_approval), indent=2))
    except PermissionError as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc)})); sys.exit(2)
    except (ValueError, KeyError, OSError, UnicodeError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)})); sys.exit(1)
