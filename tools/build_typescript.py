"""Build/pack the TypeScript candidate using locked public npm dependencies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NODE=Path(os.environ.get("OCP_NODE") or shutil.which("node") or "node")
NPM=Path(os.environ.get("OCP_NPM") or (str(NODE.with_name("npm")) if NODE.with_name("npm").is_file() else shutil.which("npm") or "npm"))


def command(argv, cwd, *, timeout=90):
    env=dict(os.environ, PATH=str(NODE.parent)+os.pathsep+os.environ.get("PATH",os.defpath))
    if os.environ.get("OCP_NPM_CACHE"): env["npm_config_cache"]=os.environ["OCP_NPM_CACHE"]
    try:
        result=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Build step exceeded its bounded timeout. Check public dependency download access; preserve this failure before retrying in a new build directory.") from None
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    return result.stdout


def build(output_dir, *, offline=None):
    if offline is None: offline=os.environ.get("OCP_NPM_OFFLINE")=="1"
    output=Path(output_dir).resolve(); output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocp-ts-build-") as directory:
        stage=Path(directory)/"package"
        shutil.copytree(ROOT/"sdk/typescript",stage,ignore=shutil.ignore_patterns("node_modules","dist"))
        # A first public native TypeScript download is distinct from compilation.
        command([NPM,"ci",*(["--offline"] if offline else []),"--ignore-scripts","--no-audit","--no-fund"],stage,timeout=90 if offline else 300)
        command([NODE,stage/"node_modules/typescript/bin/tsc"],stage)
        resources=stage/"dist/schemas"; resources.mkdir()
        shutil.copy2(ROOT/"spec/schemas/core-0.1.schema.json",resources/"core-0.1.schema.json")
        packed=json.loads(command([NPM,"pack","--ignore-scripts","--json","--pack-destination",output],stage))
        tarball=output/packed[0]["filename"]
    return {"tarball":str(tarball),"sha256":hashlib.sha256(tarball.read_bytes()).hexdigest()}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline",action="store_true",default=None,help="Use a previously populated npm cache; fail if dependencies are missing")
    parser.add_argument("--output",default=str(ROOT/".harness/work/dist"))
    args=parser.parse_args()
    try: print(json.dumps(build(args.output,offline=args.offline)))
    except (OSError,RuntimeError) as error:
        parser.exit(1,"Build failed. Install Node 24/npm on PATH (or set OCP_NODE/OCP_NPM). Populate OCP_NPM_CACHE online before --offline.\n"+str(error)+"\n")
