"""Build/pack the TypeScript candidate using locked public npm dependencies."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NODE=Path(os.environ.get("OCP_NODE",Path.home()/".local/bin/node"))
NPM=NODE.with_name("npm")


def command(argv, cwd):
    env=dict(os.environ, PATH=str(NODE.parent)+os.pathsep+os.defpath, npm_config_cache="/private/tmp/ocp-npm-cache")
    result=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,capture_output=True,text=True,timeout=90)
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    return result.stdout


def build(output_dir):
    output=Path(output_dir).resolve(); output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocp-ts-build-") as directory:
        stage=Path(directory)/"package"
        shutil.copytree(ROOT/"sdk/typescript",stage)
        command([NPM,"ci","--offline","--ignore-scripts","--no-audit","--no-fund"],stage)
        command([NODE,stage/"node_modules/typescript/bin/tsc"],stage)
        resources=stage/"dist/schemas"; resources.mkdir()
        shutil.copy2(ROOT/"spec/schemas/core-0.1.schema.json",resources/"core-0.1.schema.json")
        packed=json.loads(command([NPM,"pack","--ignore-scripts","--json","--pack-destination",output],stage))
        tarball=output/packed[0]["filename"]
    return {"tarball":str(tarball),"sha256":hashlib.sha256(tarball.read_bytes()).hexdigest()}


if __name__=="__main__": print(json.dumps(build(ROOT/".harness/work/dist")))
