"""Explicitly selected PRIVATE review artifacts. This is not a publication exporter."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def selected_sources():
    selection=json.loads((ROOT/"provenance/candidate-selection.json").read_text())
    if selection["scope"]!="private_technical_review_only": raise ValueError("Wrong selection scope")
    paths=selection["files"]
    if not paths or len(paths)!=len(set(paths)): raise ValueError("Invalid source selection")
    forbidden=(".private/","reference/",".git/",".harness/","docs/plans/")
    hashes={}
    for name in paths:
        relative=Path(name)
        if relative.is_absolute() or ".." in relative.parts or name.startswith(forbidden) or any(part.startswith(".env") for part in relative.parts):
            raise ValueError("Forbidden candidate path")
        source=ROOT/relative
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT): raise ValueError("Invalid source file")
        hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    return hashes


def build(output_dir=None):
    output=Path(output_dir or ROOT/".harness/work/review-candidate").resolve(); output.mkdir(parents=True,exist_ok=True)
    hashes=selected_sources()
    source_archive=output/"ocp-source-candidate-0.1.0.tar.gz"
    artifacts=[]
    # Build only the selected files. New files elsewhere in the workspace cannot
    # silently enter an artifact through a builder's directory traversal.
    with tempfile.TemporaryDirectory(prefix="ocp-selected-source-") as directory:
        stage=Path(directory)
        for name,expected in hashes.items():
            target=stage/name; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
            if hashlib.sha256(target.read_bytes()).hexdigest()!=expected: raise RuntimeError("Source changed during selection")
        with tarfile.open(source_archive,"w:gz") as archive:
            for name in sorted(hashes): archive.add(stage/name,arcname="ocp-candidate/"+name,recursive=False)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
        for builder in ("build_candidate.py","build_conformance.py","build_typescript.py"):
            timeout=540 if builder=="build_typescript.py" and env.get("OCP_NPM_OFFLINE")!="1" else 120
            completed=subprocess.run([sys.executable,"-B",str(stage/"tools"/builder)],cwd=stage,env=env,capture_output=True,text=True,timeout=timeout)
            if completed.returncode: raise RuntimeError("Selected-source build failed: "+builder+"\n"+completed.stderr)
            artifact=json.loads(completed.stdout)
            source=Path(artifact.get("wheel",artifact.get("tarball")))
            shutil.copy2(source,output/source.name)
            artifacts.append(artifact)
    artifact_hashes={Path(a.get("wheel",a.get("tarball"))).name:a["sha256"] for a in artifacts}
    artifact_hashes[source_archive.name]=hashlib.sha256(source_archive.read_bytes()).hexdigest()
    manifest={"scope":"private_technical_review_only","version":"0.1.0-candidate","publication_approved":False,
              "rights_license_patent":"pending","artifacts":artifact_hashes,"sources":hashes,
              "dependencies":{"python_lock_sha256":hashlib.sha256((ROOT/"tools/requirements-dev.lock").read_bytes()).hexdigest(),
                              "npm_lock_sha256":hashlib.sha256((ROOT/"sdk/typescript/package-lock.json").read_bytes()).hexdigest()},
              "limitations":["Not published","No real Omelet trial","No external-user acceptance","Candidate version not frozen"]}
    (output/"review-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return {"directory":str(output),"manifest":manifest}


if __name__=="__main__":
    result=build(); print(json.dumps({"directory":result["directory"],"artifacts":result["manifest"]["artifacts"]}))
