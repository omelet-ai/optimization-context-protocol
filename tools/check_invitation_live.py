"""Installed operator server + MCP client against the approved loopback Foundry."""

import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_invitation_kit import build
from isolated_candidate import clean_env
from live_foundry import settings
from conformance.coordinates import verify_result

WORK=tempfile.TemporaryDirectory(prefix="ocp-live-invitation-")
DIRECTORY=Path(WORK.name);KIT=build(DIRECTORY/"kit")
ARTIFACT={"wheel":str(DIRECTORY/"kit/ocp_candidate-0.1.0-py3-none-any.whl"),"sha256":KIT["files"]["ocp_candidate-0.1.0-py3-none-any.whl"]}
ENV=clean_env(DIRECTORY)
installed=subprocess.run([sys.executable,"-B",str(DIRECTORY/"kit/install.py"),"--venv",str(DIRECTORY/"venv"),"--offline-wheelhouse",str(ROOT/".harness/work/wheels")],
    cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=90)
if installed.returncode:raise RuntimeError("Invitation installer failed: "+installed.stderr)
PYTHON=DIRECTORY/"venv/bin/python"
sys.path.insert(0,ARTIFACT["wheel"])
from ocp_runtime.trial_ops import write_private_json, read_private_json
from ocp_runtime.trial_client import InvitationClient
from ocp_candidate import Client
from mcp import Client as MCPClient, StdioServerParameters

CONFIG=DIRECTORY/"operator.json";SECRET=DIRECTORY/"service.json";SESSION=DIRECTORY/"session.json";DB=DIRECTORY/"trial.sqlite"
value,secret,_=settings()
write_private_json(SECRET,{"token":secret})
write_private_json(CONFIG,{"database":str(DB),"upstream":value["base_url"],"service_token_file":str(SECRET),
    **{k:value[k] for k in ("catalog_version","catalog_digest","catalog_document_sha256")}})


def operator(*args,success=True):
    result=subprocess.run([str(PYTHON),"-I","-B","-m","ocp_runtime.trial_ops","--config",str(CONFIG),*args],
        cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=15)
    if (result.returncode==0)!=success:raise RuntimeError("Operator CLI returned unexpected status: "+result.stderr)
    if secret in result.stdout+result.stderr:raise RuntimeError("Service credential leaked")
    return json.loads(result.stdout if success else result.stderr)


class InstalledLiveInvitation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process=None
        cls.start()
        endpoint=cls.endpoint
        cls.stop()
        operator("issue","--principal","invitation-check","--endpoint",endpoint,"--out",str(SESSION))
        cls.start(port=cls.port)

    @classmethod
    def start(cls,port=0):
        cls.process=subprocess.Popen([str(PYTHON),"-I","-B","-m","ocp_runtime.trial_ops","--config",str(CONFIG),"serve","--port",str(port)],
            cwd=DIRECTORY,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if not select.select([cls.process.stdout],[],[],12)[0]:raise RuntimeError("Operator service readiness timed out")
        line=cls.process.stdout.readline()
        if not line:raise RuntimeError("Operator service did not start")
        cls.endpoint=json.loads(line)["listening"];cls.port=int(cls.endpoint.rsplit(":",1)[1])

    @classmethod
    def stop(cls):
        if cls.process and cls.process.poll() is None:cls.process.terminate()
        if cls.process:
            cls.process.communicate(timeout=12)
            cls.process=None

    @classmethod
    def tearDownClass(cls):cls.stop()

    def test_01_client_install_has_no_ortools_and_doctor_never_solves(self):
        result=subprocess.run([str(PYTHON),"-I","-B","-c","import importlib.util; assert importlib.util.find_spec('ortools') is None"],cwd=DIRECTORY,env=ENV,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0)
        client=InvitationClient(SESSION);self.assertEqual(client.describe()["capability"]["id"],"routing.coordinates.omelet")
        with sqlite3.connect(DB) as db:self.assertEqual(db.execute("SELECT count(*) FROM runs").fetchone()[0],0)

    def test_02_mcp_real_engine_evaluation_and_retry_are_one_submission(self):
        async def scenario():
            client=Client(InvitationClient(SESSION))
            fixture=json.loads((ROOT/"cases/routing/coordinates.json").read_text())
            request=client.request(fixture["input"],request_id="invited-"+uuid.uuid4().hex,time_limit_ms=1000)
            async with MCPClient(StdioServerParameters(command=str(PYTHON),args=["-I","-B","-m","ocp_runtime.trial_client","--session",str(SESSION),"mcp"],env=ENV,cwd=str(DIRECTORY)),read_timeout_seconds=20) as host:
                tools=await host.list_tools();self.assertEqual(len(tools.tools),6)
                checked=await host.call_tool("ocp_validate",{"request":request});self.assertTrue(checked.structured_content["valid"])
                first=await host.call_tool("ocp_execute",{"request":request});result=first.structured_content
                self.assertEqual(verify_result(request,result)["total_cost"],11358)
                self.assertEqual(result["provenance"]["engine"]["id"],"omelet.standard-vrp")
                again=await host.call_tool("ocp_execute",{"request":request});self.assertEqual(again.structured_content,result)
                evaluated=await host.call_tool("ocp_evaluate",{"request":request,"solution":result["solution"]})
                self.assertEqual(evaluated.structured_content["metrics"][0]["value"],11358)
            with sqlite3.connect(DB) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM runs").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT count(*) FROM upstream_jobs").fetchone()[0],1)
        asyncio.run(scenario())

    def test_03_running_server_prevents_operator_mutations(self):
        self.assertEqual(operator("pause",success=False)["code"],"OPERATOR_ACTION_FAILED")

    def test_04_offline_pause_restart_and_backup_preserve_budget(self):
        self.stop();operator("pause");backup=DIRECTORY/"backup.sqlite";operator("backup","--out",str(backup))
        status=operator("status")["summary"]
        self.assertTrue(status["paused"]);self.assertEqual(status["calls"],1)
        self.start(port=self.port)
        client=Client(InvitationClient(SESSION));fixture=json.loads((ROOT/"cases/routing/coordinates.json").read_text())
        result=client.execute(fixture["input"],request_id="paused-request")
        self.assertEqual(result["error"]["code"],"TRIAL_PAUSED")

    def test_05_offline_revoke_blocks_installed_client_after_restart(self):
        self.stop();operator("revoke","--principal","invitation-check");self.start(port=self.port)
        result=subprocess.run([str(PYTHON),"-I","-B","-m","ocp_runtime.trial_client","--session",str(SESSION),"doctor"],cwd=DIRECTORY,env=ENV,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stderr)["code"],"UNAUTHORIZED")

    def test_06_kit_checksum_blocks_tampering_before_install(self):
        manifest=json.loads((DIRECTORY/"kit/manifest.json").read_text())
        self.assertFalse(manifest["distribution_authorized"]);self.assertFalse(manifest["secrets_included"])
        with (DIRECTORY/"kit/input.json").open("a") as stream:stream.write(" ")
        destination=DIRECTORY/"must-not-exist"
        completed=subprocess.run([sys.executable,"-B",str(DIRECTORY/"kit/install.py"),"--venv",str(destination)],cwd=DIRECTORY,env=ENV,capture_output=True,timeout=10)
        self.assertNotEqual(completed.returncode,0);self.assertFalse(destination.exists())


if __name__=="__main__":
    try:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(InstalledLiveInvitation))
        passed=result.wasSuccessful() and result.testsRun>=6 and not result.skipped
        print(json.dumps({"status":"PASS" if passed else "FAIL","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "artifact_sha256":ARTIFACT["sha256"],"scope":"Installed operator CLI/server and MCP-only client to real loopback Foundry, one reserved solve, independent evaluation; no external URL, Claude Code or human acceptance"}))
    finally:
        InstalledLiveInvitation.stop();WORK.cleanup()
    sys.exit(0 if passed else 1)
