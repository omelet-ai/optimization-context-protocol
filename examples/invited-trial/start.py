"""First success: verify this kit, create a fresh environment, solve and check."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv",default=".ocp",help="NEW environment; existing files are preserved")
    parser.add_argument("--offline-wheelhouse",help="Optional directory of pinned dependency wheels")
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    destination=Path(args.venv).absolute()
    command=[sys.executable,"-B",str(root/"install.py"),"--profile","local","--venv",str(destination)]
    if args.offline_wheelhouse:command += ["--offline-wheelhouse",args.offline_wheelhouse]
    print("[1/2] Verifying the kit and installing local engines. No account or trial key is needed.",file=sys.stderr,flush=True)
    # Stream pip progress to stderr; stdout is one machine-readable demo report.
    installed=subprocess.run(command,stdout=sys.stderr,timeout=600)
    if installed.returncode:return installed.returncode
    print("[2/2] Solving with two engines and checking intentionally damaged results.",file=sys.stderr,flush=True)
    result=subprocess.run([str(destination/"bin/python"),"-B",str(root/"demo.py"),"--diagnostics"],timeout=60)
    if result.returncode==0:
        print("Run again without installing: <environment>/bin/python demo.py --diagnostics",file=sys.stderr)
        print("Environment: "+str(destination),file=sys.stderr)
    return result.returncode


if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,subprocess.TimeoutExpired):
        print(json.dumps({"status":"FAIL","code":"START_INTERRUPTED",
            "hint":"Check the preceding installation output and network access. Preserve any incomplete environment and use a new --venv path. No remote engine was called."}),file=sys.stderr)
        raise SystemExit(1)
