"""Build a credential-free invitation kit from the explicit selected-source bundle."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from build_review_bundle import build as build_review, selected_sources

ROOT=Path(__file__).resolve().parents[1]


def source_provenance(hashes):
    """Identify exact selected content; a base commit alone cannot identify edits."""
    revision=None;changed=None
    top=subprocess.run(["git","rev-parse","--show-toplevel"],cwd=ROOT,capture_output=True,text=True) if shutil.which("git") else None
    if top is not None and top.returncode==0 and Path(top.stdout.strip()).resolve()==ROOT:
        head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True)
        status=subprocess.run(["git","status","--porcelain","--untracked-files=all","--",*sorted(hashes)],cwd=ROOT,capture_output=True,text=True)
        if head.returncode==0 and status.returncode==0:
            revision=head.stdout.strip();changed=bool(status.stdout.strip())
    return {"base_commit":revision,"selected_sources_differ_from_base_commit":changed,
            "identity":"Selected content hashes, not base_commit, identify this kit.",
            "source_tree_sha256":hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),"sources":hashes}


def build(output=None):
    target=Path(output or ROOT/".harness/work/invitation-kit").resolve()
    target.mkdir(parents=True,exist_ok=True)
    if list(target.iterdir()):raise ValueError("Invitation kit output must be empty")
    with tempfile.TemporaryDirectory(prefix="ocp-invite-artifacts-") as directory:
        bundle=build_review(directory)
        for name in ("ocp_candidate-0.1.0-py3-none-any.whl","ocp_conformance_candidate-0.1.0-py3-none-any.whl","ocp-candidate-0.1.0.tgz"):
            shutil.copy2(Path(bundle["directory"])/name,target/name)
    for source,dest in [("examples/invited-trial/install.py","install.py"),("examples/invited-trial/main.py","main.py"),
                        ("docs/users/INVITED_TRIAL.md","README.md"),("tools/requirements-dev.lock","constraints.txt"),
                        ("docs/users/DEVELOPER_QUICKSTART.md","DEVELOPER_GUIDE.md"),
                        ("docs/users/LLM_QUICKSTART.md","LLM_QUICKSTART.md"),
                        ("docs/users/EVALUATION_TASKS.md","EVALUATION_TASKS.md"),
                        ("docs/users/FEEDBACK_TEMPLATE.md","FEEDBACK_TEMPLATE.md"),
                        ("examples/invited-trial/own_app.py","own_app.py"),
                        ("examples/invited-trial/start.py","start.py"),("examples/invited-trial/demo.py","demo.py"),
                        ("examples/invited-trial/local_agent.py","local_agent.py"),
                        ("authoring/byo_library.py","byo_library.py"),("authoring/export_transcript.py","export_transcript.py"),
                        ("examples/app-b/main.ts","main.ts"),("examples/app-b/own_app.cjs","own_app.cjs"),("examples/app-b/package.json","package.json"),
                        ("examples/app-b/tsconfig.json","tsconfig.json")]:
        shutil.copy2(ROOT/source,target/dest)
    data=json.loads((ROOT/"cases/routing/coordinates.json").read_text())["input"]
    (target/"input.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    basic=json.loads((ROOT/"cases/routing/basic-matrix.json").read_text())["input"]
    (target/"basic-input.json").write_text(json.dumps(basic,ensure_ascii=False,indent=2)+"\n")
    hashes=bundle["manifest"]["sources"]
    if selected_sources()!=hashes:raise RuntimeError("Source changed during kit build")
    (target/"source-manifest.json").write_text(json.dumps(source_provenance(hashes),indent=2)+"\n")
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.iterdir())}
    manifest={"scope":"private_invitation_candidate","distribution_authorized":False,"public_release":False,
        "secrets_included":False,"platform_verification":"See the separate report for this exact artifact; building is not verification.","files":files}
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return {"directory":str(target),"files":files}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output")
    print(json.dumps(build(parser.parse_args().output)))
