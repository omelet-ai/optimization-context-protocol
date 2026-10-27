# Connect a local LLM host to OCP without an OCP key

This path installs a real local OR-Tools engine and an MCP stdio server. No Omelet
account, trial session, tunnel or hosted OCP service is needed. Your LLM host has
its own account and usage terms: **no OCP key does not mean free model usage**.
The commands below call no model. Use synthetic data only when you later choose
to send tasks and tool responses to a model provider.

## Install and check the connection

For source installation, follow the [README](https://github.com/omelet-ai/optimization-context-protocol#first-success-from-github): Python/MCP setup needs no Node/npm and already installs MCP.
For an extracted developer kit that has not been installed, with Python 3.12 on macOS or Linux:

```sh
python3.12 start.py --mcp --venv .agent
.agent/bin/python -I -B local_agent.py doctor
.agent/bin/python -I -B local_agent.py smoke --input basic-input.json --request-id mcp-first-1
```

Installation downloads pinned public Python dependencies. For offline use add
`--offline-wheelhouse /absolute/path/to/wheels` to `start.py`. That directory must
contain wheels for your OS, CPU and Python version. Use a new environment path;
existing environments and files are preserved. Windows installation is not supported.

`start.py --mcp` checks the kit, installs both extras and the independent checker,
checks MCP without solving, then runs the two-engine demo. `doctor` initializes
the installed stdio server and reads its six tools and context schema; it reports
zero execute calls. `smoke` validates, executes once, evaluates a non-null solution,
and independently checks the result. The bundled input should produce a feasible
solution with checked cost 18 meters. PASS means the observed protocol/result was
checked; inspect `solution_found` and `response.status` before claiming a solution.
An invalid input returns a nonzero exit and zero execute calls. No automatic retry.

## Generate configuration for your host

For all three bundled domains in one server:

```sh
.agent/bin/python -I -B local_agent.py doctor --profile all
.agent/bin/python -I -B local_agent.py config --profile all --format codex
.agent/bin/python -I -B local_agent.py config --profile all --format json
```

Doctor checks routing, worker and inventory context with zero solve calls. For a
single-domain server, replace `all` with `worker.scheduling`,
`inventory.replenishment` or `routing.basic`. Omitting `--profile` keeps the
original routing-only behavior. Smoke needs a specific domain and matching input;
use the examples in the [three-domain guide](MULTI_DOMAIN_QUICKSTART.md).

These print configuration for review; they do not edit account settings or start
a model. The command uses the environment's absolute Python path, including
spaces, and `-I` to isolate imports. Regenerate it after moving the environment.
Install on the machine where the MCP host runs. A remote Codex executor and your
laptop can have different filesystems; a path on one is not a path on the other.

For Codex, merge the printed TOML block into the intended host's MCP configuration
without overwriting existing settings. Restart/reload the host and verify that
`ocp-local` exposes `ocp_context`, `ocp_describe`, `ocp_requirements`, `ocp_validate`,
`ocp_execute` and `ocp_evaluate`. `startup_timeout_sec = 60` accommodates a cold
engine startup; it does not increase the request's solve budget. `required = true`
makes a connection failure visible. Follow the host's tool approval controls.
See the [official Codex MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

The JSON form is a common `mcpServers` stdio configuration. Adapt the wrapper to
your host's documented format. JSON generation and SDK checks do not establish
compatibility with every host. Browser-only hosts that cannot launch local stdio
processes require a different, separately reviewed connection; this kit does not
publish an endpoint.

## Try a model only when you choose to spend its usage

Start with: “Read OCP's context and tell me which input fields and units are
required. Do not execute yet.” Confirm an actual `ocp_context` call, not just a
plausible answer. Then supply the contents of `basic-input.json` and ask it to
validate, solve once and evaluate the returned solution. Inspect the real calls
and arguments. It should ask about missing capacities, reject unsupported units,
and distinguish feasible from optimal, timeout from infeasible, and null from zero.

Provider `ocp_evaluate` is not the independent checker. The local `smoke` command
checks separately using the conformance package. A model must not claim it ran
that checker unless its actual tool trace shows an independent check.

## Recover without guessing

| Symptom | Action |
| --- | --- |
| `LOCAL_MCP_DEPENDENCIES_MISSING` | Use the `.agent` Python, or install a new environment with `start.py --mcp`. A plain local install omits MCP; a trial install omits OR-Tools. |
| `INPUT_INVALID` | Use readable UTF-8 JSON, unique keys, finite numbers and at most 128 KiB. |
| `INPUT_REJECTED` | Read `validation.issues`; correct your new input file, keeping profile units explicit. Nothing executed. |
| `LOCAL_MCP_CHECK_FAILED` | Run doctor with the same installed Python. Check startup limits and host permissions. Preserve the request ID after an uncertain solve. |
| Host has no OCP tools | Check the executable on the host machine, regenerate config, restart the host, and inspect its MCP status before running a model task. |

Only share error codes and synthetic results after review. Host configs contain
local filesystem paths; do not include them or account credentials in feedback.

한국어: `start.py --mcp`로 로컬 엔진·MCP를 함께 설치합니다. `doctor`는 계산 없이 연결을,
`smoke`는 실제 계산과 독립 검산을 확인합니다. 두 명령은 LLM을 호출하지 않습니다.
실제 모델 사용량과 외부 자료 전송은 별도이며 설치 경로는 모델 호스트가 실행되는 기기 기준입니다.

For executable worker scheduling and inventory replenishment through the same
app/MCP flow, follow the [three-domain quickstart](MULTI_DOMAIN_QUICKSTART.md).
