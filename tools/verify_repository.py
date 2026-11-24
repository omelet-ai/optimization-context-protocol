"""Check an explicit repository source selection and, optionally, Git's index.

Selected text, reviewed spreadsheet fixtures and pinned site fonts are checked.
This is a bounded pre-push check,
not a complete secret-detection or rights audit.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import sys
from ci_policy import WORKFLOW, validate as validate_ci
from binary_fixture_policy import reviewed_fixture_text

ROOT = Path(__file__).resolve().parents[1]
SELECTION = "provenance/repository-selection.json"
# Unmodified Korean subsets from the Pretendard v1.3.9 release.
SITE_FONTS = {
    "site/assets/Pretendard-Regular.subset.woff2": "01dd73155fdfab7ce9b25224523e85a96927e21aef97f21957d41f1bfa7e3878",
    "site/assets/Pretendard-SemiBold.subset.woff2": "4247dc5e260b92640c2cbd0e75091154647b71e1d5884116655e2903468c54cc",
}
SITE_FONT_LICENSE = "site/assets/Pretendard-LICENSE.txt"
SITE_FONT_LICENSE_SHA256 = "d31ddd9f2bed32fd7e302a205cf2380ba0de6529152d239ef99cfb6f261bfc04"
FORBIDDEN = (
    ".private/", "reference/", ".harness/", ".github/workflows/", "docs/plans/", "docs/reference/",
    "docs/development/EXTERNAL_GATE_REQUEST.md", "docs/development/FOUNDRY_TRIAL_PREFLIGHT.md",
    "spec/bindings/OMELET_MAPPING.md", "provenance/source-manifest.json", "provenance/copy-report.json",
)
PATTERNS = {
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----",
    "github_token": r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    "aws_access_key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "credential_url": r"https?://[^\s/:@]+:[^\s/@]+@",
    "personal_local_path": r"/Users/" + "omeletjk/",
}


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if result.returncode: raise ValueError("Git command failed: " + " ".join(args[:2]))
    return result.stdout


def verify(index=False, selection_path=SELECTION):
    candidate_path = PurePosixPath(selection_path)
    if (candidate_path.is_absolute() or '..' in candidate_path.parts or '\\' in selection_path
            or candidate_path.as_posix() != selection_path):
        raise ValueError("Invalid selection path")
    def read(name):
        if index: return git("show", ":" + name)
        source = ROOT / name
        if any(p.is_symlink() for p in [source, *source.parents] if p != ROOT and p.is_relative_to(ROOT)):
            raise ValueError("Symlink source: " + name)
        return source.read_bytes()

    selection = json.loads(read(selection_path))
    public_source = selection["scope"] == "public_source_repository"
    candidate = selection["scope"] == "public_source_candidate"
    if selection["scope"] not in {"private_repository_only", "public_source_repository", "public_source_candidate"} or selection["repository"] != "omelet-ai/optimization-context-protocol":
        raise ValueError("Unexpected repository scope")
    if selection["publication_approved"] is not public_source: raise ValueError("Repository approval does not match scope")
    if selection.get("visibility") != ("public" if public_source or candidate else "private"):
        raise ValueError("Repository visibility does not match scope")
    files = selection["files"]
    if not files or len(files) != len(set(files)) or selection_path not in files: raise ValueError("Invalid selection")
    if index:
        staged = git("ls-files", "--stage", "-z").decode().split("\0")
        actual = set()
        for entry in filter(None, staged):
            metadata, name = entry.split("\t", 1)
            mode, _, stage = metadata.split()
            if mode not in {"100644", "100755"} or stage != "0": raise ValueError("Unsupported index entry: " + name)
            actual.add(name)
        if actual != set(files): raise ValueError("Index differs from explicit selection")
    hashes = {}
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or path.as_posix() != name:
            raise ValueError("Invalid repository path")
        if (name != WORKFLOW and name.startswith(FORBIDDEN)) or any(part.startswith(".env") or part in {".git", "node_modules", "__pycache__", ".venv"} for part in path.parts):
            raise ValueError("Excluded repository path: " + name)
        if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".pyc", ".sqlite", ".sqlite3", ".db", ".whl", ".tgz", ".zip", ".gz"}:
            raise ValueError("Excluded file type: " + name)
        content = read(name)
        if len(content) > 1024 * 1024: raise ValueError("Unexpected source size: " + name)
        if path.suffix.lower() == ".woff2":
            if hashlib.sha256(content).hexdigest() != SITE_FONTS.get(name):
                raise ValueError("Unexpected site font: " + name)
            if (SITE_FONT_LICENSE not in files
                    or hashlib.sha256(read(SITE_FONT_LICENSE)).hexdigest() != SITE_FONT_LICENSE_SHA256):
                raise ValueError("Missing or changed site font license")
            # The byte-for-byte upstream font is binary and carries no project-authored text.
            text = ""
        else:
            text = reviewed_fixture_text(name, content) if path.suffix.lower() == ".xlsx" else content.decode("utf-8")
        if name == WORKFLOW:
            validate_ci(text)
        for label, pattern in PATTERNS.items():
            if re.search(pattern, text): raise ValueError("Review required: " + name + " (" + label + ")")
        if name.endswith(".md"):
            for link in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
                if re.match(r"[a-z]+://", link) or link.startswith("#"): continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), link.split("#")[0]))
                if target not in files: raise ValueError("Link outside selection: " + name + " -> " + link)
        hashes[name] = hashlib.sha256(content).hexdigest()
    public = json.loads(read("provenance/publication.json"))
    if public_source:
        required = ("rights_approved", "license_approved", "patent_disclosure_approved", "publication_authorized")
        if any(public.get(key) is not True for key in required): raise ValueError("Source publication approval incomplete")
        allowed = public.get("public_allowlist")
        if not isinstance(allowed, list) or len(allowed) != len(set(allowed)) or set(allowed) != set(files):
            raise ValueError("Public allowlist differs from repository selection")
        if public.get("scope") != "github_source_repository_only" or public.get("repository") != selection["repository"]:
            raise ValueError("Publication target or scope mismatch")
        for flag in ("registry_publication_authorized", "site_deployment_authorized", "trial_deployment_authorized"):
            if public.get(flag) is not False: raise ValueError("Source approval cannot authorize deployment or registry publication")
        if public.get("approval_record") != "provenance/PUBLICATION_APPROVAL.md" or public["approval_record"] not in files:
            raise ValueError("Missing scoped approval record")
        if public.get("license") != "Apache-2.0" or hashes.get("LICENSE") != public.get("license_sha256"):
            raise ValueError("Approved license missing or changed")
        if not {"NOTICE", "THIRD_PARTY_NOTICES.md"}.issubset(files): raise ValueError("Missing license notices")
    elif candidate:
        if (selection.get('approval_status') != 'PENDING_EXACT_CANDIDATE_REVIEW'
                or selection.get('license') != 'Apache-2.0'
                or hashes.get('LICENSE') != public.get('license_sha256')
                or not {'NOTICE', 'THIRD_PARTY_NOTICES.md'}.issubset(files)):
            raise ValueError('Candidate license or review state missing')
        if any(name.startswith('tools/foundry_convergence/') for name in files):
            raise ValueError('Unrelated convergence work is outside this candidate')
    elif public["publication_authorized"] or public["public_allowlist"]:
        raise ValueError("Private selection cannot authorize publication")
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"status": "PASS", "scope": "pending_public_source_candidate" if candidate else ("public_source_selection" if public_source else "private_repository_selection"), "source": "git_index" if index else "working_files",
            "files": len(files), "tree_content_sha256": digest, "public_release_authorized": public_source}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", action="store_true")
    parser.add_argument("--selection", default=SELECTION)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.index, args.selection), ensure_ascii=False))
    except (ValueError, KeyError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False))
        sys.exit(1)
