# Optimization Context Protocol (OCP)

**Connect optimization engines to applications and AI agents through an explicit contract.**

OCP describes what an engine supports, what an application requests, what was
actually enforced, and how to check the result. Applications can use their own
engines independently of Omelet, Foundry, Studio, or a particular transport.

**Status: open-source developer preview, licensed under [Apache-2.0](LICENSE).**
Source code is available in this GitHub repository. Package-registry releases,
a hosted public website and open trial enrollment are not available yet.
A passing local check is not engine certification
or evidence of unaided external adoption.

## First success from GitHub

Prerequisites: **Git, Python 3.12 and Node 24/npm on PATH**, on macOS or Linux.
Check `python3.12 --version`, `node --version` and `npm --version` first.
Node is required to **build this kit from source**, even if you only use its Python
examples. Once built, Python/MCP users do not need Node. Windows is not supported
by this installer. No Omelet account, trial key or model call is needed.

```sh
git clone https://github.com/omelet-ai/optimization-context-protocol.git
cd optimization-context-protocol
```

From that repository root, run this complete block in one terminal. It downloads
public PyPI/npm dependencies and builds a local kit; it publishes nothing.

<!-- ocp:readme-build -->
```sh
OCP_WORK="$(mktemp -d)"
python3.12 -m venv "$OCP_WORK/build"
"$OCP_WORK/build/bin/python" -m pip install --no-compile build==1.4.0 setuptools==80.9.0 wheel==0.46.3
"$OCP_WORK/build/bin/python" -B tools/build_invitation_kit.py --output "$OCP_WORK/kit"
cd "$OCP_WORK/kit"
python3.12 start.py --mcp --venv .agent
```

Keep this terminal in the kit directory for the commands below. `start.py` and
the sample JSON files are **generated kit files**, not files in the repository root.
The temporary directory keeps generated environments out of your checkout. For
a lasting installation, choose a new directory outside the checkout instead of
`mktemp -d`, keep it in place, and regenerate host configuration if you move it.

The final command installs the engines, independent checker and MCP server, then
runs **the same application and input through two real engines**: OR-Tools and an
independent enumerating teaching library. Expect JSON with `status: "PASS"` and
checked baseline costs of **18 meters**. It also demonstrates rejected units,
intentionally corrupted results, and a real execution deadline. Progress is on
stderr; the final result is on stdout. No language model is called.

To rerun, use `.agent/bin/python -B demo.py --diagnostics`; do not install over the
existing `.agent`. For separate wheel builds or offline setup, see the
[source build guide](docs/development/BUILD_FROM_SOURCE.md).

## Run your first three problems

From the **same kit directory**, use the same application with each profile:

<!-- ocp:readme-examples -->
```sh
.agent/bin/python -I -B multi_app.py --profile routing.basic --input basic-input.json --request-id first-routing
.agent/bin/python -I -B multi_app.py --profile worker.scheduling --input worker-input.json --request-id first-worker
.agent/bin/python -I -B multi_app.py --profile inventory.replenishment --input inventory-input.json --request-id first-inventory
```

The independently checked total costs are **18 meter**, **7 cost_unit** and
**16 cost_unit**, respectively. Check `solution_found` and `response.status` too;
PASS describes the transcript check, not a guarantee of a solution or optimality.
Copy a sample to a new JSON file before editing it, and use a new request ID for
a changed problem. [Three-domain examples](docs/users/MULTI_DOMAIN_QUICKSTART.md)
show changes with known answers and the supported size/constraint limits.

## Connect MCP without calling a model

The installation above already includes MCP. From the same kit directory:

<!-- ocp:readme-mcp -->
```sh
.agent/bin/python -I -B local_agent.py doctor --profile all
.agent/bin/python -I -B local_agent.py smoke --input basic-input.json --request-id first-mcp
.agent/bin/python -I -B local_agent.py config --profile all --format json
.agent/bin/python -I -B local_agent.py config --profile all --format codex
```

Doctor discovers six tools and checks context for all three domains with **zero
solve calls**. Smoke performs one real routing solve and an independent check;
expect cost 18. Config prints absolute executable paths for review, without
editing host settings. Use the JSON or Codex TOML form appropriate for your host,
on the machine where that host runs. Then reload its MCP configuration and check
that `ocp-local` exposes the six tools. Host/model usage is separate from these
local checks. The [MCP guide](docs/users/LLM_QUICKSTART.md) covers host setup,
single-domain configuration and troubleshooting.

| If you get stuck | Recovery |
| --- | --- |
| `python3.12`, `node` or `npm` is missing | Install the prerequisite version, or put its executable on PATH. These instructions do not install system runtimes. |
| `start.py` or a sample is missing | Complete the kit build, then `cd "$OCP_WORK/kit"` in the same terminal. Do not run kit commands from the repository root. |
| `ENVIRONMENT_EXISTS` | Reuse `.agent/bin/python` to run examples; choose a new path only for a fresh install. |
| A download/build fails | Preserve the failure output and check public PyPI/npm access. Run the build block again to create a new temporary directory. No automatic retry occurs. |
| MCP config works here but not on another machine | Install the kit on the host machine and generate its configuration there; local paths do not transfer between machines. |

The full local regression environment is Python 3.12 on macOS Apple Silicon.
The first-success command also ran on Python 3.12.15 in a Linux x86_64 container
under Docker Desktop on that Mac. Additional Python/MCP/Node checks are recorded for each exact ZIP using the
[evaluation rehearsal](docs/development/NO_KEY_EVALUATION.md). Native Linux machines
and the full Linux trial integration remain separate work; the installer rejects
Windows. Node 24 is also used by the optional Node/TypeScript consumer.

See [first-use instructions](docs/users/INVITED_TRIAL.md) and
[connect your app or engine](docs/users/DEVELOPER_QUICKSTART.md).

## Why add OCP to a solver?

Calling OR-Tools directly is appropriate for one application using its solver API.
OCP is useful when another app, agent or engine needs the same boundary:

| Application need | OCP contract |
| --- | --- |
| Discover supported behavior before building a request | Capabilities, configuration and input requirements |
| Swap a compatible engine without rewriting the application flow | A shared profile and client/adapter interface |
| Avoid silently dropped constraints or changed units | Explicit validation and unsupported-feature errors |
| Explain the outcome accurately | `feasible`, `optimal`, `infeasible`, `unknown`, termination and metric status |
| Detect a bad engine response | A separately packaged checker recomputes declared constraints and cost |

Engine substitution applies only to the intersection of supported profiles,
units, costs and constraints. It does not guarantee identical routes, quality,
speed or support for every optimization domain. Runnable reference profiles cover routing, fixed-time worker scheduling and
deterministic inventory replenishment. Use the [three-domain quickstart](docs/users/MULTI_DOMAIN_QUICKSTART.md)
for the same app and MCP flow across all three. The new profiles deliberately
bound model size so optimality/infeasibility can be checked independently.
`assignment.fixture` remains a separate schema/witness fixture with no solver.

## Choose a starting path

| Path | Use it when | Instructions |
| --- | --- | --- |
| Try Omelet | You have an invitation to a limited real engine trial | [Invited trial](docs/users/INVITED_TRIAL.md) |
| Run locally | You want a first success with no key | [Developer quickstart](docs/users/DEVELOPER_QUICKSTART.md) |
| Bring your engine | You want to connect your own library or service | [Engine authoring](authoring/README.md) |

Omelet trial is the recommended introduction when an invitation is available.
It is optional; Core compliance never requires an Omelet account.

## Scope and contributing

- [Contract and compatibility](docs/users/COMPATIBILITY.md): Core, domain and execution profiles, bindings and environment policy remain separate.
- [Contribution guide](CONTRIBUTING.md), [security reporting](SECURITY.md), and [support scope](docs/users/CONTRIBUTING_SUPPORT.md).
- [Website source](site/README.md): English overview, Korean introduction, examples and three starting paths. Browser examples show build-time calculations, not live engine calls.
- [Development harness](harness/README.md), [task ledger](TASKS.md), and [fresh checkout checks](docs/development/LOCAL_RUNTIME.md).
- [GitHub launch preparation](docs/development/GITHUB_LAUNCH.md) and [publication checklist](PUBLIC_RELEASE_CHECKLIST.md).

The [approved source inventory](provenance/publication.json) defines this
repository's published scope. See [NOTICE](NOTICE) and
[third-party notices](THIRD_PARTY_NOTICES.md). Internal material, credentials,
original snapshots and execution evidence stay outside it. Hosted services,
registry packages and release assets require separate scoped authorization.

한국어: OCP는 앱·AI 에이전트와 최적화 엔진 사이의 지원 기능·요청·결과·검증을
명시하는 인터페이스입니다. Apache-2.0으로 공개된 개발자 프리뷰이며, 사이트·trial 배포와 패키지 레지스트리 출시는 별도입니다.
[한국어 시작 안내](docs/users/GETTING_STARTED.md)를 참고하세요.
