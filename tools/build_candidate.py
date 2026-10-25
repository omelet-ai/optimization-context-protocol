"""Build a private candidate wheel from explicit sources and canonical schemas."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def build(output_dir=None):
    output = Path(output_dir or ROOT / ".harness/work/dist").resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocp-wheel-build-") as directory:
        staging = Path(directory) / "candidate"
        shutil.copytree(ROOT / "sdk/python", staging)
        shutil.copytree(ROOT / "adapters/python/ocp_routing", staging / "src/ocp_routing")
        shutil.copytree(ROOT / "runtime/python/ocp_runtime", staging / "src/ocp_runtime")
        resources = staging / "src/ocp_candidate/schemas"
        resources.mkdir()
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
    wheels = sorted(output.glob("ocp_candidate-0.1.0-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected one exact candidate wheel")
    return {"wheel":str(wheels[0]),"sha256":hashlib.sha256(wheels[0].read_bytes()).hexdigest(),"schemas":source_hashes}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
