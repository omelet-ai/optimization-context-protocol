"""Check an explicit repository source selection and, optionally, Git's index.

Only selected UTF-8 source is read. This is a bounded pre-push check,
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

ROOT = Path(__file__).resolve().parents[1]
SELECTION = "provenance/repository-selection.json"
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


def verify(index=False):
    def read(name):
        if index: return git("show", ":" + name)
        source = ROOT / name
        if any(p.is_symlink() for p in [source, *source.parents] if p != ROOT and p.is_relative_to(ROOT)):
            raise ValueError("Symlink source: " + name)
        return source.read_bytes()

    selection = json.loads(read(SELECTION))
    public_source = selection["scope"] == "public_source_repository"
    if selection["scope"] not in {"private_repository_only", "public_source_repository"} or selection["repository"] != "omelet-ai/optimization-context-protocol":
        raise ValueError("Unexpected repository scope")
    if selection["publication_approved"] is not public_source: raise ValueError("Repository approval does not match scope")
    if selection.get("visibility") != ("public" if public_source else "private"):
        raise ValueError("Repository visibility does not match scope")
    files = selection["files"]
    if not files or len(files) != len(set(files)) or SELECTION not in files: raise ValueError("Invalid selection")
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
        if name.startswith(FORBIDDEN) or any(part.startswith(".env") or part in {".git", "node_modules", "__pycache__", ".venv"} for part in path.parts):
            raise ValueError("Excluded repository path: " + name)
        if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".pyc", ".sqlite", ".sqlite3", ".db", ".whl", ".tgz", ".zip", ".gz"}:
            raise ValueError("Excluded file type: " + name)
        content = read(name)
        if len(content) > 1024 * 1024: raise ValueError("Unexpected source size: " + name)
        text = content.decode("utf-8")
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
    elif public["publication_authorized"] or public["public_allowlist"]:
        raise ValueError("Private selection cannot authorize publication")
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"status": "PASS", "scope": "public_source_selection" if public_source else "private_repository_selection", "source": "git_index" if index else "working_files",
            "files": len(files), "tree_content_sha256": digest, "public_release_authorized": public_source}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.index), ensure_ascii=False))
    except (ValueError, KeyError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False))
        sys.exit(1)
