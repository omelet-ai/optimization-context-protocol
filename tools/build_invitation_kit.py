"""Build a credential-free invitation kit from the explicit selected-source bundle."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from build_review_bundle import build as build_review

ROOT=Path(__file__).resolve().parents[1]


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
                        ("examples/invited-trial/own_app.py","own_app.py"),
                        ("authoring/byo_library.py","byo_library.py"),("authoring/export_transcript.py","export_transcript.py"),
                        ("examples/app-b/main.ts","main.ts"),("examples/app-b/package.json","package.json"),
                        ("examples/app-b/tsconfig.json","tsconfig.json")]:
        shutil.copy2(ROOT/source,target/dest)
    data=json.loads((ROOT/"cases/routing/coordinates.json").read_text())["input"]
    (target/"input.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    basic=json.loads((ROOT/"cases/routing/basic-matrix.json").read_text())["input"]
    (target/"basic-input.json").write_text(json.dumps(basic,ensure_ascii=False,indent=2)+"\n")
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.iterdir())}
    manifest={"scope":"private_invitation_candidate","distribution_authorized":False,"public_release":False,
        "secrets_included":False,"verified_platform":"CPython 3.12 macOS arm64","files":files}
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return {"directory":str(target),"files":files}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output")
    print(json.dumps(build(parser.parse_args().output)))
