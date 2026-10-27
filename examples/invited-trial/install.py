"""Verify the invitation kit and install into a NEW Python 3.12 POSIX environment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


class InstallError(ValueError):
    def __init__(self,code,hint): self.code,self.hint=code,hint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv")
    parser.add_argument("--check",action="store_true",help="Check interpreter and kit hashes without creating an environment")
    parser.add_argument("--offline-wheelhouse")
    parser.add_argument("--profile",choices=("trial","local","local-mcp","byo"),default="trial",
                        help="local-mcp installs OR-Tools + MCP; trial installs MCP; local installs OR-Tools; byo installs neither")
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,12) or os.name!="posix":
        raise InstallError("PYTHON_VERSION_UNSUPPORTED","Use Python 3.12 on macOS/Linux. Run python3.12 --version or use its absolute path. See README prerequisites; Windows is not supported by this installer.")
    root=Path(__file__).resolve().parent
    manifest=json.loads((root/"manifest.json").read_text())
    expected={"ocp_candidate-0.1.0-py3-none-any.whl","ocp_conformance_candidate-0.1.0-py3-none-any.whl",
              "install.py","main.py","input.json","README.md","constraints.txt","ocp-candidate-0.1.0.tgz",
              "DEVELOPER_GUIDE.md","own_app.py","byo_library.py","export_transcript.py","basic-input.json","main.ts","package.json","tsconfig.json","start.py","demo.py",
              "LLM_QUICKSTART.md","EVALUATION_TASKS.md","FEEDBACK_TEMPLATE.md","source-manifest.json","own_app.cjs","local_agent.py",
              "multi_app.py","MULTI_DOMAIN_QUICKSTART.md","MULTI_DOMAIN_LLM_TASKS.json",
              "WORKER_SCHEDULING_0_1.md","INVENTORY_REPLENISHMENT_0_1.md","worker-input.json","inventory-input.json"}
    if set(manifest["files"])!=expected:raise InstallError("KIT_INVALID","Use an intact new kit from the inviter; do not edit its manifest.")
    for name,sha in manifest["files"].items():
        if (root/name).is_symlink() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise InstallError("KIT_CHECKSUM_MISMATCH","Extract a new copy of the kit. Do not modify sample files until installation succeeds.")
    if args.check:
        print(json.dumps({"status":"PASS","scope":"interpreter_and_kit_only_no_install_no_solve"}));return
    if not args.venv: parser.error("--venv is required unless --check is used")
    destination=Path(args.venv).absolute()
    if destination.exists() or destination.is_symlink():raise InstallError("ENVIRONMENT_EXISTS","Use the existing environment's Python to run demo.py (local) or doctor (trial), or choose a different --venv path. No files were overwritten.")
    wheelhouse=args.offline_wheelhouse
    if os.environ.get("PIP_NO_INDEX", "").lower() in {"1", "true", "yes", "on"}:
        wheelhouse=wheelhouse or os.environ.get("PIP_FIND_LINKS")
        if not wheelhouse:
            raise InstallError("OFFLINE_WHEELHOUSE_REQUIRED","Offline mode requires --offline-wheelhouse or PIP_FIND_LINKS pointing to one local wheel directory.")
    if wheelhouse:
        wheelhouse=Path(wheelhouse).expanduser().resolve()
        if not wheelhouse.is_dir():
            raise InstallError("OFFLINE_WHEELHOUSE_INVALID","Use one existing local wheel directory. Remote URLs are not accepted in offline mode.")
    # Match `python -m venv` on POSIX. Copying a relocatable Python invoked
    # through a PATH symlink can lose its standard-library location.
    venv.EnvBuilder(with_pip=True,symlinks=True).create(destination)
    python=destination/"bin/python"
    env={"PATH":os.defpath,"HOME":str(Path.home()),"PYTHONDONTWRITEBYTECODE":"1","PIP_CONFIG_FILE":os.devnull,
         "PIP_DISABLE_PIP_VERSION_CHECK":"1"}
    command=[str(python),"-B","-m","pip","install","--no-compile","--no-cache-dir","-c",str(root/"constraints.txt")]
    if wheelhouse:command += ["--no-index","--find-links",str(wheelhouse)]
    extra={"trial":"[mcp]","local":"[reference]","local-mcp":"[reference,mcp]","byo":""}[args.profile]
    command += [str(root/"ocp_candidate-0.1.0-py3-none-any.whl")+extra,str(root/"ocp_conformance_candidate-0.1.0-py3-none-any.whl")]
    subprocess.run(command,env=env,check=True,timeout=480)
    subprocess.run([str(python),"-B","-m","pip","check"],env=env,check=True,timeout=30)
    print(json.dumps({"installed_python":str(python),"profile":args.profile,"scope":"private_invitation_candidate_no_key_included"}))


if __name__=="__main__":
    try: main()
    except Exception as error:
        code,hint=(error.code,error.hint) if isinstance(error,InstallError) else ("INSTALL_FAILED","Check permissions and dependency download access. Preserve the failed environment for diagnosis and retry with a new --venv path.")
        print(json.dumps({"status":"FAIL","code":code,"hint":hint}),file=sys.stderr)
        sys.exit(1)
