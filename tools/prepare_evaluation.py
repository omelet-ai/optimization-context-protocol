"""Freeze a local, credential-free evaluation package; never share or publish it."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import zipfile

from build_invitation_kit import build, ROOT


def prepare(output):
    target=Path(output).absolute()
    if target.exists() or target.is_symlink():raise ValueError("Use a new output directory")
    target.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="ocp-evaluation-") as directory:
        kit=Path(directory)/"kit";build(kit)
        source=json.loads((kit/"source-manifest.json").read_text())
        with zipfile.ZipFile(target/"ocp-developer-kit.zip","x",compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(kit.iterdir()):archive.write(path,path.name)
        with tarfile.open(target/"ocp-source-candidate.tar.gz","x:gz") as archive:
            for name,expected in sorted(source["sources"].items()):
                path=ROOT/name
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                    raise ValueError("Source changed after kit build")
                archive.add(path,arcname="ocp-candidate/"+name,recursive=False)
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.iterdir())}
    report={"status":"PREPARED","distribution_authorized":False,"deployment_authorized":False,
            "rights_review":"pending","human_acceptance":"NOT_RUN","model_calls":0,
            "source_tree_sha256":source["source_tree_sha256"],"base_commit":source["base_commit"],
            "selected_sources_differ_from_base_commit":source["selected_sources_differ_from_base_commit"],
            "files":files,"verification":"Separate evidence must identify these exact artifact hashes."}
    (target/"EVALUATION_MANIFEST.json").write_text(json.dumps(report,indent=2)+"\n")
    (target/"SHA256SUMS").write_text("".join(f"{sha}  {name}\n" for name,sha in files.items()))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",required=True)
    print(json.dumps(prepare(parser.parse_args().output)))
