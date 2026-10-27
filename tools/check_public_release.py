from pathlib import Path, PurePosixPath
import json
import sys
from verify_repository import verify

root = Path(__file__).resolve().parents[1]
policy = json.loads((root / 'provenance/publication.json').read_text())
required = ['rights_approved', 'license_approved', 'patent_disclosure_approved',
            'independent_build_verified', 'publication_authorized']
reasons = [name for name in required if policy.get(name) is not True]
allowlist = policy.get('public_allowlist', [])
if not allowlist:
    reasons.append('public_allowlist_empty')

for relative in allowlist:
    if not isinstance(relative, str) or not relative or '\\' in relative:
        reasons.append('invalid_public_path:' + repr(relative))
        continue
    declared = PurePosixPath(relative)
    if declared.is_absolute() or '..' in declared.parts or declared.as_posix() != relative:
        reasons.append('invalid_public_path:' + relative)
        continue
    unresolved = root.joinpath(*declared.parts)
    if any(parent.is_symlink() for parent in [unresolved, *unresolved.parents] if parent != root):
        reasons.append('symlink_public_path:' + relative)
        continue
    resolved = unresolved.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        reasons.append('invalid_public_path:' + relative)
        continue
    canonical = resolved.relative_to(root).as_posix()
    if any(canonical == prefix.rstrip('/') or canonical.startswith(prefix.rstrip('/') + '/')
           for prefix in policy['never_export_prefixes']):
        reasons.append('forbidden_public_path:' + canonical)

if reasons:
    print('PUBLIC RELEASE BLOCKED: ' + ', '.join(reasons))
    sys.exit(2)
try:
    selection = verify()
    if not selection['public_release_authorized']:
        raise ValueError('Repository source publication is not approved')
except (ValueError, KeyError, OSError, UnicodeError) as exc:
    print('PUBLIC RELEASE BLOCKED: ' + str(exc))
    sys.exit(2)
print(json.dumps({'status': 'PASS', 'scope': 'github_source_repository_only',
                  'files': selection['files'], 'tree_content_sha256': selection['tree_content_sha256'],
                  'publishes_files': False, 'authorizes_deployment_or_registry': False}))
