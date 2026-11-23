from __future__ import annotations

import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
import shutil
import tempfile
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.specifiers import InvalidSpecifier, SpecifierSet

TEMPLATE_REVISION = "0.1.0-draft.5"
RUNTIME_VERSION = "0.4.0.dev12+publicformat3"
RECORD = ".ocp-generation.json"
DEPENDENCIES = "python-dependencies.json"


class ScaffoldError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree(path, *, installed_template=False):
    """Inventory regular author files; do not copy keys, symlinks or build output."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ScaffoldError("CONTENT_DIRECTORY_REQUIRED")
    result = {}
    for file in sorted(path.rglob("*")):
        rel = file.relative_to(path).as_posix()
        if file.is_symlink():
            raise ScaffoldError("SYMLINK_NOT_ALLOWED: " + rel)
        if installed_template and ("__pycache__" in file.relative_to(path).parts or file.suffix == ".pyc"):
            # pip may byte-compile Python resource files after installation.
            # These are never copied into newly generated author projects.
            continue
        if file.is_dir():
            continue
        if not file.is_file():
            raise ScaffoldError("REGULAR_FILES_REQUIRED: " + rel)
        if any(part in {".git", ".venv", "node_modules", "__pycache__"} or part.startswith(".env") for part in file.relative_to(path).parts):
            raise ScaffoldError("PRIVATE_OR_GENERATED_CONTENT: " + rel)
        if file.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".pyc"}:
            raise ScaffoldError("PRIVATE_OR_GENERATED_CONTENT: " + rel)
        result[rel] = file.read_bytes()
    return result


def template_files(template_directory=None):
    # Installed resource is the default. Source callers must explicitly provide a template.
    root = Path(template_directory) if template_directory else Path(str(files(__package__).joinpath("_template")))
    return tree(root, installed_template=True)


def python_dependencies(content, name):
    """Package declarations are data; never execute a resolver or author code here."""
    if DEPENDENCIES not in content:
        return [], ">=3.12"
    try:
        value = json.loads(content[DEPENDENCIES])
    except (ValueError, UnicodeError) as error:
        raise ScaffoldError("DEPENDENCIES_INVALID_JSON") from error
    if (not isinstance(value, dict) or not {"schema", "requires"} <= set(value)
            or set(value) - {"schema", "requires", "requires-python"}
            or value["schema"] != "ocp-python-dependencies/v1"
            or not isinstance(value["requires"], list) or len(value["requires"]) > 100):
        raise ScaffoldError("DEPENDENCIES_INVALID")
    python = value.get("requires-python", ">=3.12")
    if not isinstance(python, str) or not python or len(python) > 256 or any(ord(c) < 32 for c in python):
        raise ScaffoldError("DEPENDENCIES_PYTHON_INVALID")
    try:
        python = str(SpecifierSet(">=3.12," + python))
    except InvalidSpecifier as error:
        raise ScaffoldError("DEPENDENCIES_PYTHON_INVALID") from error
    result, seen = [], set()
    for item in value["requires"]:
        if not isinstance(item, str) or len(item) > 1024 or any(ord(c) < 32 for c in item):
            raise ScaffoldError("DEPENDENCY_INVALID")
        try:
            requirement = Requirement(item)
        except InvalidRequirement as error:
            raise ScaffoldError("DEPENDENCY_INVALID") from error
        normalized = canonicalize_name(requirement.name)
        if requirement.url:
            raise ScaffoldError("DEPENDENCY_URL_UNSUPPORTED")
        if normalized in {canonicalize_name(name), "ocp-candidate"}:
            raise ScaffoldError("DEPENDENCY_RESERVED")
        key = (normalized, str(requirement.marker))
        if key in seen:
            raise ScaffoldError("DEPENDENCY_DUPLICATE")
        seen.add(key)
        result.append(str(requirement))
    return result, python


def render(name, template_directory=None, *, dependencies=(), requires_python=">=3.12"):
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,62}[a-z0-9]", name):
        raise ScaffoldError("INVALID_PACKAGE_NAME")
    original = template_files(template_directory)
    params = {"package_name": name, "module_name": "ocp_" + name.replace("-", "_"),
              "runtime_version": RUNTIME_VERSION, "template_revision": TEMPLATE_REVISION,
              "python_dependencies": list(dependencies), "requires_python": requires_python}
    rendered = {}
    for path, value in original.items():
        text = value.decode("utf8")
        for key, val in params.items():
            if key == "python_dependencies":
                val = json.dumps(["ocp-candidate[server]==" + RUNTIME_VERSION, *dependencies], ensure_ascii=True)
            text = text.replace("{{" + key + "}}", val)
        if "{{" in text:
            raise ScaffoldError("UNKNOWN_TEMPLATE_VARIABLE")
        rendered[path] = text.encode("utf8")
    return rendered, params, {p: sha(v) for p, v in original.items()}


def create_project(output, name, *, content=None, template_directory=None):
    target = Path(output).absolute()
    if target.exists() or target.is_symlink():
        raise ScaffoldError("OUTPUT_ALREADY_EXISTS")
    authored = tree(content) if content is not None else {}
    dependencies, requires_python = python_dependencies(authored, name)
    base, params, template_hashes = render(name, template_directory, dependencies=dependencies, requires_python=requires_python)
    payload = dict(base)
    if content is not None:
        if "manifest.json" not in authored:
            raise ScaffoldError("CONTENT_MANIFEST_REQUIRED")
        payload = {p: v for p, v in base.items() if not p.startswith("content/")}
        payload.update({"content/" + p: v for p, v in authored.items()})
    record = {"schema": "ocp-generation/v1", "parameters": params,
              "template_hashes": template_hashes,
              "files": {p: {"sha256": sha(v), "role": "content" if p.startswith("content/") else "derived" if p == "pyproject.toml" and (dependencies or requires_python != ">=3.12") else "common"}
                        for p, v in payload.items()}}
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".ocp-scaffold-", dir=target.parent))
    try:
        for relative, value in payload.items():
            p = staging / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(value)
        (staging / RECORD).write_text(json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
        # Claim an absent directory atomically. Do not replace even an empty
        # destination that another process created after our initial check.
        try:
            target.mkdir()
        except FileExistsError as error:
            raise ScaffoldError("OUTPUT_ALREADY_EXISTS") from error
        for staged in sorted(staging.rglob("*")):
            destination = target / staged.relative_to(staging)
            if staged.is_dir():
                destination.mkdir(exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as stream:
                    stream.write(staged.read_bytes())
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return record


def verified_record(project, template_directory=None):
    payload = tree(project)
    if RECORD not in payload:
        raise ScaffoldError("GENERATION_RECORD_REQUIRED")
    record = json.loads(payload.pop(RECORD))
    if record.get("schema") != "ocp-generation/v1":
        raise ScaffoldError("GENERATION_RECORD_UNSUPPORTED")
    name = record["parameters"]["package_name"]
    authored = {p.removeprefix("content/"): v for p, v in payload.items() if p.startswith("content/")}
    dependencies, requires_python = python_dependencies(authored, name)
    rendered, params, hashes = render(name, template_directory, dependencies=dependencies, requires_python=requires_python)
    if params != record["parameters"] or hashes != record["template_hashes"]:
        raise ScaffoldError("TEMPLATE_REVISION_MISMATCH")
    if set(payload) != set(record["files"]):
        raise ScaffoldError("UNRECORDED_PROJECT_FILES")
    for path, value in payload.items():
        if sha(value) != record["files"][path]["sha256"]:
            raise ScaffoldError("PROJECT_EDIT_CONFLICT: " + path)
        if not path.startswith("content/") and rendered.get(path) != value:
            raise ScaffoldError("PROJECT_EDIT_CONFLICT: " + path)
    return record


def strip_content(project, output, *, template_directory=None):
    record = verified_record(project, template_directory)
    return create_project(output, record["parameters"]["package_name"], template_directory=template_directory)


def inject_content(project, content, output, *, template_directory=None):
    record = verified_record(project, template_directory)
    return create_project(output, record["parameters"]["package_name"], content=content, template_directory=template_directory)
