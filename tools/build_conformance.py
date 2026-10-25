"""Build the independent conformance wheel with its own canonical schemas."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def build(output_dir):
    output=Path(output_dir).resolve(); output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocp-conformance-build-") as directory:
        stage=Path(directory)
        package=stage/"src/conformance"; package.mkdir(parents=True)
        for path in (ROOT/"conformance").glob("*.py"): shutil.copy2(path,package/path.name)
        shutil.copytree(ROOT/"spec/schemas",package/"schemas")
        (stage/"pyproject.toml").write_text('''[build-system]
requires=["setuptools==80.9.0","wheel==0.46.3"]
build-backend="setuptools.build_meta"
[project]
name="ocp-conformance-candidate"
version="0.1.0"
requires-python=">=3.12"
dependencies=["jsonschema==4.26.0"]
[tool.setuptools.packages.find]
where=["src"]
[tool.setuptools.package-data]
conformance=["schemas/*.json"]
''')
        process=subprocess.run([sys.executable,"-B","-m","build","--wheel","--no-isolation","--outdir",str(output),str(stage)],
                               capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1"),timeout=60)
        if process.returncode: raise RuntimeError(process.stderr)
    wheel=output/"ocp_conformance_candidate-0.1.0-py3-none-any.whl"
    return {"wheel":str(wheel),"sha256":hashlib.sha256(wheel.read_bytes()).hexdigest()}


if __name__=="__main__": print(json.dumps(build(ROOT/".harness/work/dist")))
