"""Private artifacts only: clean reinstall, BYO, independent checker and source closure."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_review_bundle import build
from build_typescript import command, NODE, NPM
from isolated_candidate import install
from conformance.routing import verify_result
from check_h02 import request, FIXTURE

WORK=tempfile.TemporaryDirectory(prefix="ocp-h11-clean-")
DIRECTORY=Path(WORK.name)
BUNDLE=build(DIRECTORY/"artifacts")
ARTIFACTS=Path(BUNDLE["directory"])
MANIFEST=BUNDLE["manifest"]
PYTHON,ENV=install(DIRECTORY,ARTIFACTS/"ocp_candidate-0.1.0-py3-none-any.whl",extras="")
installed=subprocess.run([str(PYTHON),"-B","-m","pip","install","--no-index","--no-cache-dir","--no-compile",
                          str(ARTIFACTS/"ocp_conformance_candidate-0.1.0-py3-none-any.whl")],cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=30)
if installed.returncode: raise RuntimeError(installed.stderr)
prepared=subprocess.run([str(PYTHON),"-B","-m","pip","install","--no-index","--no-cache-dir","--no-compile",
                         "--find-links",str(ROOT/".harness/work/wheels"),"build==1.4.0","setuptools==80.9.0","wheel==0.46.3"],
                        cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=30)
if prepared.returncode: raise RuntimeError(prepared.stderr)
with tarfile.open(ARTIFACTS/"ocp-source-candidate-0.1.0.tar.gz") as archive:
    archive.extractall(DIRECTORY/"source",filter="data")
SOURCE=DIRECTORY/"source/ocp-candidate"
(DIRECTORY/"input.json").write_text(json.dumps(FIXTURE["input"]))
(DIRECTORY/"offline_run.py").write_text('''import runpy,socket,sys
def denied(*args,**kwargs): raise RuntimeError("No network in BYO execution")
socket.socket=denied; socket.create_connection=denied
sys.argv=[sys.argv[1]]+sys.argv[2:]
runpy.run_path(sys.argv[0],run_name="__main__")
''')


def python(argv,expected=0):
    completed=subprocess.run([str(PYTHON),"-I","-B",*map(str,argv)],cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=30)
    if completed.returncode!=expected: raise AssertionError(completed.stderr+completed.stdout)
    return json.loads(completed.stdout)


class ArtifactTests(unittest.TestCase):
    def test_01_exact_artifact_hashes(self):
        for name,expected in MANIFEST["artifacts"].items():
            self.assertEqual(hashlib.sha256((ARTIFACTS/name).read_bytes()).hexdigest(),expected)

    def test_02_source_allowlist_and_hashes(self):
        actual={str(p.relative_to(SOURCE)) for p in SOURCE.rglob("*") if p.is_file()}
        self.assertEqual(actual,set(MANIFEST["sources"]))
        for name,expected in MANIFEST["sources"].items():
            self.assertEqual(hashlib.sha256((SOURCE/name).read_bytes()).hexdigest(),expected)
            self.assertFalse(name.startswith((".private/","reference/",".git/",".harness/","docs/plans/")))

    def test_03_no_private_runtime_imports_or_paths(self):
        for path in ARTIFACTS.glob("*.whl"):
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    self.assertNotIn(".env",name); self.assertNotIn(".private/",name)
                    if name.endswith(".py"):
                        value=archive.read(name).decode()
                        for forbidden in ("/Users/","imported-foundry",".private/foundry"):
                            self.assertNotIn(forbidden,value)

    def test_04_clean_sdk_and_checker_without_ortools(self):
        result=python(["-c","import importlib.util,json,ocp_candidate,conformance; print(json.dumps({'ortools':importlib.util.find_spec('ortools') is not None,'sdk':ocp_candidate.__file__,'checker':conformance.__file__}))"])
        self.assertFalse(result["ortools"])
        for name in ("sdk","checker"): self.assertTrue(Path(result[name]).is_relative_to(DIRECTORY/"venv"))

    def test_05_actual_byo_engine_without_account_or_network(self):
        result=python(["offline_run.py",SOURCE/"authoring/byo_library.py","input.json"])
        req=request(); req["request_id"]="byo-library"; req["capability"]={"id":"example.own-routing","version":"0.1.0"}
        self.assertEqual(result["provenance"]["engine"]["id"],"example.enumerating-library")
        self.assertEqual(verify_result(req,result)["total_cost"],18)
        bundle={"artifact_sha256":MANIFEST["artifacts"]["ocp_candidate-0.1.0-py3-none-any.whl"],"implementation":result["provenance"]["implementation"],
                "cases":[{"id":"own-library","request":req,"response":result}]}
        (DIRECTORY/"transcript.json").write_text(json.dumps(bundle))
        checked=python(["-m","conformance.runner","--bundle","transcript.json","--artifact",ARTIFACTS/"ocp_candidate-0.1.0-py3-none-any.whl"])
        self.assertEqual(checked["status"],"PASS")
        self.assertEqual(checked["report"]["checks"][-2]["status"],"NOT_TESTED")

    def test_06_byo_rejects_unimplemented_scale(self):
        problem=deepcopy(FIXTURE["input"])
        problem["vehicles"]=[{"id":"v"+str(i),"capacity":4} for i in range(4)]
        (DIRECTORY/"large.json").write_text(json.dumps(problem))
        result=python(["offline_run.py",SOURCE/"authoring/byo_library.py","large.json"],expected=2)
        self.assertEqual(result["kind"],"failure")
        self.assertEqual(result["error"]["code"],"LIMIT_EXCEEDED")

    def test_07_source_only_python_build(self):
        # Builder dependencies are public installed libraries; cwd/source contains only selected files.
        completed=subprocess.run([str(PYTHON),"-B",str(SOURCE/"tools/build_candidate.py")],cwd=SOURCE,env=ENV,capture_output=True,text=True,timeout=60)
        self.assertEqual(completed.returncode,0,completed.stderr)
        built=Path(json.loads(completed.stdout)["wheel"])
        self.assertTrue(built.resolve().is_relative_to(SOURCE.resolve()))
        with zipfile.ZipFile(built) as archive:
            self.assertIn("ocp_candidate/client.py",archive.namelist())

    def test_08_source_only_conformance_build(self):
        completed=subprocess.run([str(PYTHON),"-B",str(SOURCE/"tools/build_conformance.py")],cwd=SOURCE,env=ENV,capture_output=True,text=True,timeout=60)
        self.assertEqual(completed.returncode,0,completed.stderr)

    def test_09_typescript_tarball_fresh_install(self):
        app=DIRECTORY/"node-consumer"; app.mkdir()
        (app/"package.json").write_text('{"name":"private-check","version":"0.0.0","private":true}')
        command([NPM,"install","--offline","--ignore-scripts","--no-audit","--no-fund",ARTIFACTS/"ocp-candidate-0.1.0.tgz"],app)
        shutil.copy2(SOURCE/"cases/core/messages.json",app/"messages.json")
        out=command([NODE,"-e","const {envelope}=require('ocp-candidate');for(const x of require('./messages.json').positive) envelope(x.message); console.log(JSON.stringify({pass:true}));"],app)
        self.assertTrue(json.loads(out)["pass"])

    def test_10_no_publication_approval_implied(self):
        self.assertFalse(MANIFEST["publication_approved"])
        publication=json.loads((ROOT/"provenance/publication.json").read_text())
        self.assertFalse(publication["publication_authorized"]); self.assertEqual(publication["public_allowlist"],[])
        self.assertFalse(json.loads((ROOT/"sdk/typescript/package.json").read_text()).get("publishConfig"))

    def test_11_dependency_locks_and_versions_retained(self):
        self.assertEqual(hashlib.sha256((SOURCE/"tools/requirements-dev.lock").read_bytes()).hexdigest(),MANIFEST["dependencies"]["python_lock_sha256"])
        self.assertEqual(hashlib.sha256((SOURCE/"sdk/typescript/package-lock.json").read_bytes()).hexdigest(),MANIFEST["dependencies"]["npm_lock_sha256"])

    def test_12_three_paths_compatibility_and_support_docs(self):
        start=(SOURCE/"docs/users/GETTING_STARTED.md").read_text()
        for name in ("Try Omelet","Run locally","Bring your engine"): self.assertIn(name,start)
        self.assertIn("미확정",(SOURCE/"docs/users/CONTRIBUTING_SUPPORT.md").read_text())
        self.assertIn("미검증",(SOURCE/"spec/bindings/HTTP_MCP_0_1.md").read_text())
        for name in MANIFEST["sources"]:
            if not name.endswith(".md"): continue
            for link in re.findall(r"\]\(([^)]+)\)",(SOURCE/name).read_text()):
                if "://" in link or link.startswith("#"): continue
                target=posixpath.normpath(posixpath.join(posixpath.dirname(name),link.split("#")[0]))
                self.assertIn(target,MANIFEST["sources"],name+" links outside selected source: "+link)

    def test_13_source_only_typescript_build(self):
        completed=subprocess.run([str(PYTHON),"-B",str(SOURCE/"tools/build_typescript.py")],cwd=SOURCE,
                                 env=dict(ENV,OCP_NODE=str(NODE)),capture_output=True,text=True,timeout=90)
        self.assertEqual(completed.returncode,0,completed.stderr)
        built=Path(json.loads(completed.stdout)["tarball"])
        self.assertTrue(built.resolve().is_relative_to(SOURCE.resolve()))

    def test_14_wheel_code_matches_selected_sources(self):
        roots={"ocp_candidate":"sdk/python/src/ocp_candidate","ocp_routing":"adapters/python/ocp_routing",
               "ocp_runtime":"runtime/python/ocp_runtime","conformance":"conformance"}
        for path in ARTIFACTS.glob("*.whl"):
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if not name.endswith(".py"): continue
                    package,relative=name.split("/",1)
                    source=roots[package]+"/"+relative
                    self.assertIn(source,MANIFEST["sources"])
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),MANIFEST["sources"][source])


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ArtifactTests))
        passed=result.wasSuccessful() and result.testsRun>=14 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
                          "artifact_sha256":hashlib.sha256((ARTIFACTS/"review-manifest.json").read_bytes()).hexdigest(),
                          "versions":{"candidate":"0.1.0","conformance":"0.1.0","source_files":len(MANIFEST["sources"])},
                          "scope":"Private selected-source artifacts, clean Python/TS source builds, no-ORTools BYO and independent conformance; no publication, real Omelet trial or external-user acceptance"}))
        if passed:
            retained=ROOT/".harness/work/review-candidate"; retained.mkdir(parents=True,exist_ok=True)
            for path in ARTIFACTS.iterdir(): shutil.copy2(path,retained/path.name)
    finally: WORK.cleanup()
    sys.exit(0 if passed else 1)
