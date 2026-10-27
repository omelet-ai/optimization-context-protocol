"""Execute the README journey from selected source, with fresh installed consumers.

Offline regression uses reviewed dependency caches. Anonymous GitHub/online
downloads are a separate rehearsal, never inferred from this check.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

from build_typescript import NODE, NPM
from isolated_candidate import clean_env

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from safe_test_result import DiagnosticResult
PROFILES = {"routing.basic": ("basic-input.json", 18),
            "worker.scheduling": ("worker-input.json", 7),
            "inventory.replenishment": ("inventory-input.json", 16)}


def block(text, marker):
    found = re.findall(r"<!-- ocp:" + re.escape(marker) + r" -->\s*```sh\n(.*?)\n```", text, re.S)
    if len(found) != 1:
        raise ValueError("Expected one executable documentation block: " + marker)
    return found[0]


class ReadmeJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ocp-readme-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name).resolve()
        cls.source = cls.work / "checkout with spaces"
        files = json.loads((ROOT / "provenance/repository-selection.json").read_text())["files"]
        for name in files:
            target = cls.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        cls.home = cls.work / "empty-home"
        cls.home.mkdir()
        bindir = cls.work / "bin"
        bindir.mkdir()
        (bindir / "python3.12").symlink_to(sys._base_executable)
        (bindir / "node").symlink_to(NODE.resolve())
        (bindir / "npm").symlink_to(NPM.resolve())
        scratch = cls.work / "scratch"
        scratch.mkdir()
        cls.env = clean_env(cls.home)
        cls.env.update(PATH=str(bindir) + os.pathsep + os.defpath,
                       TMPDIR=str(scratch), PIP_NO_INDEX="1",
                       PIP_FIND_LINKS=str(ROOT / ".harness/work/wheels"),
                       OCP_NPM_OFFLINE="1", npm_config_offline="true",
                       npm_config_cache=os.environ["OCP_NPM_CACHE"],
                       NPM_CONFIG_USERCONFIG=str(cls.home / "empty-npmrc"))
        reviewed = json.loads((ROOT / "tools/dependency-wheels.json").read_text())["sha256"]
        for name, digest in reviewed.items():
            if hashlib.sha256((ROOT / ".harness/work/wheels" / name).read_bytes()).hexdigest() != digest:
                raise ValueError("Changed dependency wheel: " + name)
        cls.readme = (cls.source / "README.md").read_text()
        result = cls.run_ok(["/bin/sh", "-eu", "-c", block(cls.readme, "readme-build") + "\npwd\n"], cls.source)
        lines = result.stdout.splitlines()
        reports = []
        for match in re.finditer(r"(?m)^\{", result.stdout):
            value, _ = json.JSONDecoder().raw_decode(result.stdout[match.start():])
            if value.get("status"):
                reports.append(value)
        if len(reports) != 1:
            raise ValueError("Expected one final demo result from README build")
        cls.first = reports[0]
        cls.kit = Path(lines[-1]).resolve()
        # mktemp chooses the execution host's temporary root; do not assume
        # that a shell subprocess preserves the caller's TMPDIR override.
        if cls.kit.name != "kit" or not (cls.kit.parent / "build/pyvenv.cfg").is_file():
            raise ValueError("README did not return its newly built kit directory")
        cls.addClassCleanup(shutil.rmtree, cls.kit.parent)
        cls.python = cls.kit / ".agent/bin/python"

    @classmethod
    def run_ok(cls, args, cwd=None, expected=0):
        result = subprocess.run([str(x) for x in args], cwd=cwd or cls.kit,
                                env=cls.env, capture_output=True, text=True, timeout=300)
        if result.returncode != expected:
            raise AssertionError(result.stdout[-2000:] + result.stderr[-3000:])
        return result

    def test_01_exact_readme_build_install(self):
        self.assertEqual(self.first["status"], "PASS")
        self.assertTrue((self.kit / "local_agent.py").is_file())
        self.assertFalse((self.source / "start.py").exists())
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse((self.source / ".private").exists())
        self.assertFalse((self.source / "reference").exists())

    def test_02_exact_readme_three_examples(self):
        lines = block(self.readme, "readme-examples").splitlines()
        self.assertEqual(len(lines), 3)
        for command, (profile, (_, cost)) in zip(lines, PROFILES.items()):
            report = json.loads(self.run_ok(["/bin/sh", "-eu", "-c", command]).stdout)
            self.assertEqual(report["request"]["domain_profile"]["id"], profile)
            self.assertTrue(report["solution_found"])
            self.assertEqual(report["execute_calls"], 1)
            self.assertEqual(report["independent_check"]["total_cost"], cost)

    def configs(self):
        values = []
        for command in block(self.readme, "readme-mcp").splitlines():
            values.append(self.run_ok(["/bin/sh", "-eu", "-c", command]).stdout)
        return values

    def test_03_readme_mcp_doctor_smoke_and_config(self):
        doctor, smoke, raw_json, raw_toml = self.configs()
        doctor, smoke = json.loads(doctor), json.loads(smoke)
        self.assertEqual(doctor["execute_calls"], 0)
        self.assertEqual(doctor["model_calls"], 0)
        self.assertEqual(doctor["checked_profiles"], list(PROFILES))
        self.assertEqual(doctor["tool_calls"], ["ocp_context"] * 3)
        self.assertEqual(len(doctor["tools"]), 6)
        self.assertEqual(smoke["independent_check"]["total_cost"], 18)
        self.assertEqual(smoke["execute_calls"], 1)
        self.assertEqual(smoke["model_calls"], 0)
        config = json.loads(raw_json)["mcpServers"]["ocp-local"]
        toml = tomllib.loads(raw_toml)["mcp_servers"]["ocp-local"]
        self.assertEqual(config["command"], str(self.python))
        for key, value in config.items():
            self.assertEqual(toml[key], value)
        self.assertEqual(config["args"][-2:], ["--profile", "all"])
        self.assertFalse((self.home / ".codex").exists())

    def test_04_generated_config_actual_multi_profile_session(self):
        config = self.run_ok([self.python, "-I", "-B", "local_agent.py", "config", "--profile", "all"]).stdout
        path = self.work / "mcp-config.json"
        path.write_text(config)
        # Launch exactly the generated configuration. One real SDK connection
        # discovers, validates, solves and checks all domains; no model involved.
        code = '''import asyncio,json,os,sys
from mcp import Client,StdioServerParameters
from conformance.runner import CHECKERS
config=json.load(open(sys.argv[1]))['mcpServers']['ocp-local']
async def main():
 async with Client(StdioServerParameters(**config,env={'PATH':os.defpath,'HOME':sys.argv[2]},cwd=sys.argv[2]),read_timeout_seconds=60) as host:
  assert len((await host.list_tools()).tools)==6
  for profile,name,cost in [('routing.basic','basic-input.json',18),('worker.scheduling','worker-input.json',7),('inventory.replenishment','inventory-input.json',16)]:
   g=(await host.call_tool('ocp_context',{'profile':profile})).structured_content
   r=g['request_template'];r.update(input=json.load(open(name)),request_id='generated-'+profile)
   d=await host.call_tool('ocp_describe',{'profile':profile});assert not d.is_error
   q=await host.call_tool('ocp_requirements',{'profile':profile,'configuration':r['configuration']});assert not q.is_error
   v=await host.call_tool('ocp_validate',{'request':r});assert v.structured_content['valid']
   o=await host.call_tool('ocp_execute',{'request':r});assert not o.is_error
   assert CHECKERS[(profile,'0.1.0')](r,o.structured_content)['total_cost']==cost
   e=await host.call_tool('ocp_evaluate',{'request':r,'solution':o.structured_content['solution']});assert not e.is_error
  bad=await host.call_tool('ocp_context',{'profile':'unknown.profile'});assert bad.is_error
 print(json.dumps({'profiles_checked':3,'execute_calls':3,'model_calls':0}))
asyncio.run(main())
'''
        result = json.loads(self.run_ok([self.python, "-I", "-B", "-c", code, path, self.home]).stdout)
        self.assertEqual(result, {"profiles_checked": 3, "execute_calls": 3, "model_calls": 0})

    def test_05_invalid_inputs_never_execute(self):
        for profile, (name, _) in PROFILES.items():
            problem = json.loads((self.kit / name).read_text())
            if profile == "routing.basic":
                problem["matrix"]["unit"] = "kilometer"
            elif profile == "worker.scheduling":
                del problem["workers"][0]["availability"]
            else:
                del problem["products"][0]["lead_time"]
            path = self.work / "invalid.json"
            path.write_text(json.dumps(problem))
            result = self.run_ok([self.python, "-I", "-B", "local_agent.py", "smoke", "--profile", profile,
                                  "--input", path, "--request-id", "invalid-" + profile], expected=1)
            report = json.loads(result.stdout)
            self.assertEqual(report["code"], "INPUT_REJECTED")
            self.assertEqual(report["execute_calls"], 0)
            self.assertNotIn("ocp_execute", report["tool_calls"])

    def test_06_documented_node_install_and_application(self):
        guide = (self.source / "docs/users/MULTI_DOMAIN_QUICKSTART.md").read_text()
        self.run_ok(["/bin/sh", "-eu", "-c", block(guide, "node-install")])
        child = subprocess.Popen([str(self.python), "-I", "-B", "-m", "ocp_runtime.http_server", "--profile", "worker.scheduling"],
                                 cwd=self.home, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(60), "Provider startup timed out")
            url = json.loads(child.stdout.readline())["url"]
            result = json.loads(self.run_ok([NODE, "own_app.cjs", url, "worker-input.json", "readme-node"]).stdout)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["evaluation"]["metrics"][0]["value"], 7)
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=5)
            child.stdout.close()

    def test_07_reinstall_preserves_environment_and_single_profile_still_works(self):
        result = self.run_ok(["python3.12", "start.py", "--mcp", "--venv", ".agent"], expected=1)
        self.assertIn("ENVIRONMENT_EXISTS", result.stderr)
        doctor = json.loads(self.run_ok([self.python, "-I", "-B", "local_agent.py", "doctor"]).stdout)
        self.assertEqual(doctor["domain_profile"]["id"], "routing.basic")
        self.assertEqual(doctor["execute_calls"], 0)


if __name__ == "__main__":
    result = unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReadmeJourney))
    passed = result.wasSuccessful() and result.testsRun >= 7 and not result.skipped
    print(json.dumps({"status": "PASS" if passed else "FAIL", "tests_run": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
                      "failure_diagnostics": result.diagnostics, "model_calls": 0,
                      "scope": "Exact README commands from selected source; fresh offline Python/Node/MCP; not an online GitHub or human acceptance test"}))
    sys.exit(0 if passed else 1)
