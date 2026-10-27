"""Rehearse one exact ZIP in a new HOME/venv/npm cache. No model or remote engine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import subprocess
import sys
import zipfile


def check(archive, work, offline_wheelhouse=None, npm_cache=None):
    archive=Path(archive).resolve();work=Path(work).absolute()
    if work.exists() or work.is_symlink():raise ValueError("Use a new work directory")
    work.mkdir(parents=True);kit=work/"kit with spaces";kit.mkdir();home=work/"empty-home";home.mkdir()
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if Path(name).name!=name or name in {".",".."}:raise ValueError("Unexpected kit path")
        zipped.extractall(kit)
    node=shutil.which("node");npm=shutil.which("npm")
    if not node or not npm:raise ValueError("Node 24 and npm required")
    # npm rejects loading one file as both user and global configuration.
    user_config=home/"user.npmrc";global_config=home/"global.npmrc"
    user_config.write_text("");global_config.write_text("")
    env={"HOME":str(home),"PATH":str(Path(node).parent)+os.pathsep+os.defpath,
         "PYTHONDONTWRITEBYTECODE":"1","PIP_CONFIG_FILE":os.devnull,"PIP_DISABLE_PIP_VERSION_CHECK":"1",
         "npm_config_cache":str(npm_cache or work/"new-npm-cache"),"npm_config_userconfig":str(user_config),
         "npm_config_globalconfig":str(global_config)}
    if npm_cache:env["npm_config_offline"]="true"
    if offline_wheelhouse:env.update(PIP_NO_INDEX="1",PIP_FIND_LINKS=str(Path(offline_wheelhouse).resolve()))
    steps=[]
    report={"status":"INCOMPLETE","kit_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
            "source_tree_sha256":json.loads((kit/"source-manifest.json").read_text())["source_tree_sha256"],
            "platform":platform.system(),"machine":platform.machine(),"python":platform.python_version(),
            "model_calls":0,"external_engine_calls":0,"steps":steps,
            "dependency_mode":"reviewed_offline" if offline_wheelhouse and npm_cache else "public_downloads",
            "scope":"Automated local developer rehearsal; not actual human or LLM acceptance"}

    def run(name,argv,expected=0):
        result=subprocess.run([str(x) for x in argv],cwd=kit,env=env,capture_output=True,text=True,timeout=600)
        steps.append({"step":name,"returncode":result.returncode,"expected":expected})
        print(name+": "+("PASS" if result.returncode==expected else "FAIL"),file=sys.stderr,flush=True)
        if result.returncode!=expected:
            # Keep raw diagnostic output local to this explicitly chosen work dir.
            (work/(name+".stdout.log")).write_text(result.stdout)
            (work/(name+".stderr.log")).write_text(result.stderr)
            raise RuntimeError(name)
        return result.stdout

    provider=None
    try:
        report["node"]=run("node-version",[node,"--version"]).strip()
        if not report["node"].startswith("v24."):raise RuntimeError("Node 24 required")
        base=Path(sys._base_executable).resolve();python=work/"agent environment/bin/python"
        start=json.loads(run("first-success",[base,"-B","start.py","--mcp","--venv",python.parent.parent]))
        assert start["status"]=="PASS"
        doctor=json.loads(run("mcp-doctor",[python,"-I","-B","local_agent.py","doctor"]))
        assert doctor["execute_calls"]==0 and doctor["model_calls"]==0
        smoke=json.loads(run("mcp-smoke",[python,"-I","-B","local_agent.py","smoke","--input","basic-input.json","--request-id","fresh-mcp"]))
        assert smoke["execute_calls"]==1 and smoke["independent_check"]["total_cost"]==18
        config=json.loads(run("mcp-config",[python,"-I","-B","local_agent.py","config"]))
        assert config["mcpServers"]["ocp-local"]["command"]==str(python)
        data=json.loads((kit/"basic-input.json").read_text());data["matrix"]["values"]=[[v*2 for v in row] for row in data["matrix"]["values"]]
        (kit/"my-input.json").write_text(json.dumps(data))
        app=json.loads(run("python-own-input",[python,"-B","own_app.py","--input","my-input.json","--request-id","fresh-python"]))
        assert app["independent_check"]["total_cost"]==36
        data["matrix"]["unit"]="kilometer";(kit/"bad-unit.json").write_text(json.dumps(data))
        rejected=json.loads(run("mcp-bad-unit",[python,"-I","-B","local_agent.py","smoke","--input","bad-unit.json","--request-id","fresh-bad-mcp"],1))
        assert rejected["execute_calls"]==0 and rejected["code"]=="INPUT_REJECTED"
        run("npm-install",[npm,"install","--no-save","--package-lock=false","--ignore-scripts","--no-audit","--no-fund","./ocp-candidate-0.1.0.tgz"])
        run("typescript-build",[npm,"run","build"])
        provider=subprocess.Popen([str(python),"-I","-B","-m","ocp_runtime.http_server"],cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        with selectors.DefaultSelector() as selector:
            selector.register(provider.stdout,selectors.EVENT_READ)
            if not selector.select(60):raise RuntimeError("provider-startup-timeout")
        url=json.loads(provider.stdout.readline())["url"]
        ts=json.loads(run("typescript-app",[node,"dist/main.js",url,"basic-input.json","--request-id","fresh-typescript"]))
        assert ts["kind"]=="result" and ts["status"]=="feasible"
        value=run("node-own-input",[node,"own_app.cjs",url,"my-input.json","fresh-node"])
        node_result=json.loads(value);assert node_result["evaluation"]["metrics"][0]["value"]==36
        (kit/"node-result.json").write_text(value)
        run("node-independent-check",[python,"-I","-B","-c","import json;from conformance.routing import verify_result;t=json.load(open('node-result.json'));assert verify_result(t['request'],t['response'])['total_cost']==36"])
        bad=json.loads(run("node-bad-unit",[node,"own_app.cjs",url,"bad-unit.json","fresh-bad-node"],2));assert bad["execute_calls"]==0
        run("byo-install",[base,"-B","install.py","--profile","byo","--venv",work/"byo environment"])
        byopy=work/"byo environment/bin/python"
        run("byo-no-optional-dependencies",[byopy,"-I","-B","-c","import importlib.util;assert importlib.util.find_spec('ortools') is None;assert importlib.util.find_spec('mcp') is None"])
        own=json.loads(run("byo-engine",[byopy,"-B","demo.py","--engine","own"]));assert own["status"]=="PASS"
        report["status"]="PASS"
    except Exception:
        report["status"]="FAIL"
    finally:
        if provider is not None:
            if provider.poll() is None:
                provider.terminate()
                try:provider.wait(timeout=10)
                except subprocess.TimeoutExpired:provider.kill();provider.wait(timeout=5)
            provider.stdout.close()
        (work/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit",required=True);parser.add_argument("--work",required=True)
    parser.add_argument("--offline-wheelhouse");parser.add_argument("--npm-cache")
    args=parser.parse_args();result=check(args.kit,args.work,args.offline_wheelhouse,args.npm_cache)
    print(json.dumps(result));sys.exit(0 if result["status"]=="PASS" else 1)
