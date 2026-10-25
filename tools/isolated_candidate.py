"""Reusable private verification environment: hash-checked public wheels, no index/cache."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def clean_env(home):
    return {"PATH": os.defpath, "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_CONFIG_FILE": os.devnull, "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "LC_ALL": "C.UTF-8"}


def install(directory, wheel, extras="reference"):
    directory = Path(directory)
    wheelhouse = ROOT / ".harness/work/wheels"
    manifest = json.loads((ROOT / "tools/dependency-wheels.json").read_text())
    for name, expected in manifest["sha256"].items():
        path = wheelhouse / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Missing or changed public dependency wheel: " + name)
    if {p.name for p in wheelhouse.iterdir()} != set(manifest["sha256"]):
        raise RuntimeError("Unexpected dependency file; refresh reviewed manifest explicitly")
    envdir = directory / "venv"
    venv.EnvBuilder(with_pip=True, symlinks=False).create(envdir)
    python = envdir / "bin/python"
    env = clean_env(directory)
    installed = subprocess.run([str(python), "-B", "-m", "pip", "install", "--no-index", "--no-cache-dir",
                                "--no-compile", "--find-links", str(wheelhouse), str(wheel) + ("[" + extras + "]" if extras else "")],
                               env=env, cwd=directory, capture_output=True, text=True, timeout=90)
    if installed.returncode:
        raise RuntimeError("Offline candidate install failed: " + installed.stderr[-2000:])
    checked = subprocess.run([str(python), "-B", "-m", "pip", "check"], env=env, cwd=directory,
                             capture_output=True, text=True, timeout=20)
    if checked.returncode:
        raise RuntimeError("Installed dependency check failed")
    return python, env
