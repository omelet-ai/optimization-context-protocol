"""Build a private candidate wheel from explicit sources and canonical schemas."""

import hashlib
import json
import os
import re
import tomllib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def build(output_dir=None, *, version=None):
    output = Path(output_dir or ROOT / ".harness/work/dist").resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocp-wheel-build-") as directory:
        staging = Path(directory) / "candidate"
        source_only = shutil.ignore_patterns('__pycache__', '*.pyc')
        shutil.copytree(ROOT / "sdk/python", staging, ignore=source_only)
        metadata = staging / "pyproject.toml"
        package_version = tomllib.loads(metadata.read_text())["project"]["version"]
        if version is not None:
            if not re.fullmatch(r"[0-9][A-Za-z0-9.+-]*", version):
                raise ValueError("Invalid candidate version")
            metadata.write_text(metadata.read_text().replace('version = "' + package_version + '"', 'version = "' + version + '"', 1))
            package_version = version
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            shutil.copy2(ROOT / name, staging / name)
        shutil.copytree(ROOT / "adapters/python/ocp_routing", staging / "src/ocp_routing", ignore=source_only)
        shutil.copytree(ROOT / "runtime/python/ocp_runtime", staging / "src/ocp_runtime", ignore=source_only)
        # Generated projects must depend on this exact installed runtime artifact.
        scaffold = staging / "src/ocp_runtime/authoring/scaffold.py"
        authoring_source = scaffold.read_text()
        authoring_source, replaced = re.subn(r'^RUNTIME_VERSION = "[^"\n]+"$',
            'RUNTIME_VERSION = "' + package_version + '"', authoring_source, flags=re.MULTILINE)
        if replaced != 1:
            raise ValueError("Exactly one authoring runtime version must be stamped")
        scaffold.write_text(authoring_source)
        shutil.copytree(ROOT / "templates/ocp-server", staging / "src/ocp_runtime/authoring/_template", ignore=source_only)
        shutil.copytree(ROOT / "adapters/python/ocp_planning", staging / "src/ocp_planning", ignore=source_only)
        # Generic proposal excludes private catalog content and connector packages.
        resources = staging / "src/ocp_candidate/schemas"
        resources.mkdir()
        shutil.copy2(ROOT / "spec/profile-registry.json", staging / "src/ocp_candidate/profiles.json")
        source_hashes = {}
        for path in sorted((ROOT / "spec/schemas").glob("*.json")):
            shutil.copy2(path, resources / path.name)
            source_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (staging / "src/ocp_candidate/schema-manifest.json").write_text(json.dumps(source_hashes, sort_keys=True))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run([sys.executable,"-B","-m","build","--wheel","--no-isolation","--outdir",str(output),str(staging)],env=env,capture_output=True,text=True)
        if completed.returncode:
            print(completed.stderr, file=sys.stderr)
            raise RuntimeError("Candidate wheel build failed")
    wheels = sorted(output.glob("ocp_candidate-" + package_version + "-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected one exact candidate wheel")
    return {"wheel":str(wheels[0]),"sha256":hashlib.sha256(wheels[0].read_bytes()).hexdigest(),"schemas":source_hashes}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
