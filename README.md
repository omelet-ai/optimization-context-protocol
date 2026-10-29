# Optimization Context Protocol (OCP)

**Connect optimization engines to applications and AI agents through an explicit contract.**

OCP describes what an engine supports, what an application requests, what was
actually enforced, and how to check the result. Applications can use their own
engines independently of Omelet, Foundry, Studio, or a particular transport.

**Status: open-source developer preview, licensed under [Apache-2.0](LICENSE).**
Source code is available in this GitHub repository. Visit the
[public documentation site](https://omelet-ai.github.io/optimization-context-protocol/)
and [한국어 소개](https://omelet-ai.github.io/optimization-context-protocol/ko/).
Package-registry releases and open trial enrollment are not available yet.
A passing local check is not engine certification
or evidence of unaided external adoption.

See [project status and verification boundaries](docs/users/PROJECT_STATUS.md)
and the [first immutable preview plan](docs/development/PREVIEW_RELEASE.md).
## Download and run the native preview

Start with the [v0.1.1-preview.1 prerelease](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1). Download
`ocp-native-v0.1.1-preview.1.zip` and `SHA256SUMS`, compare the ZIP's SHA-256,
and extract into a new folder. Python 3.12 on macOS or Linux is required.
Git, Node, a source build, an Omelet key and model calls are unnecessary for
this Python/MCP path. Dependencies are installed from public PyPI.

```sh
shasum -a 256 ocp-native-v0.1.1-preview.1.zip
unzip ocp-native-v0.1.1-preview.1.zip -d ocp-native-preview
cd ocp-native-preview
python3.12 -B install.py
.native/bin/python -I -B demo.py
.native/bin/python -I -B mcp_config.py
```

Compare the first command's output with the native ZIP line in `SHA256SUMS`
before continuing. On Linux, `sha256sum` is also available. Checksums detect
changed bytes; they are not signatures. Read `START_HERE.md` inside the ZIP for
MCP, your own inputs, engine replacement and the blank independent review form.
The demo's checked costs are routing 18, worker 7 and inventory 16; units and
mathematical status are reported separately. See the source-build path below
if you want to develop OCP itself.

## Core 0.1 and native v1

**Core 0.1 and the native v1 candidate are public source developer previews.**
Both are licensed under Apache-2.0. The Core quickstart below retains the existing
synchronous interface; the [native source quickstart](#native-v1-from-public-source)
builds a separate opt-in kit aligned with Foundry Capability Contract v1.
Native implementation, pinned shared contracts and build tools are included here.
This is not a stable v1 or full gateway/ocps1 release. The [native ZIP](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1)
is a prerelease; PyPI/npm packages are not published.

<!-- ocp:core-native-table:start -->
| Boundary | Core 0.1 | Native v1 candidate |
| --- | --- | --- |
| Availability | Public source developer preview; install from GitHub | Public source and native prerelease ZIP; source build also available |
| Execution | Synchronous reference calls | Asynchronous jobs: submit, poll, fetch result, request cancellation |
| Wire format | Core request/result envelopes, version `0.1.0` | Capability Contract v1 outer catalog/job/error; declared Core 0.1 domain payload retained |
| SDK entrypoints | `ocp_candidate` / `ocp-candidate` | Explicit opt-in: `ocp_candidate.native` / `ocp-candidate/native` |
| MCP | Six tools, starting with `ocp_context` | Eight tools, starting with `ocp_native_context` |
| Local setup | No account or key; Python/MCP need no Node | Separate local build; host manages ephemeral credentials; Python/MCP need no Node |
<!-- ocp:core-native-table:end -->

In the native reference, `contractVersion: "1"` identifies the outer contract.
`domainPayloadFormat: "ocp-core-request/0.1.0"` identifies the preserved problem
body, and `JobResult.result` contains the original domain result. Contract,
domain-profile and package versions are separate. This does not make matrix
routing equivalent to coordinate routing, or worker assignment to nurse scheduling.

Native jobs follow submit → poll → fetch result → evaluate. A job marked
`succeeded` means computation completed, not that a solution is optimal.
Inspect the inner result status, termination, proof and null metrics, and use
a separate independent checker. Keep the same idempotency key and input after
an uncertain response. Cancellation is a request; confirm a terminal job state
before saying the computation stopped.

Existing Core 0.1 imports and synchronous semantics remain supported; no removal
date is set. A native integration needs the prerelease ZIP or a locally built native kit and explicit
entrypoints. Do not change wire formats merely by updating a dependency. The
native MCP candidate is a stateless local binding, not the full
`foundry-ocp-standard/v1` gateway/ocps1 state profile. Its localhost-only server,
volatile two-hour records and default 128-job session limit are local reference
policies, not universal OCP requirements. Native sources and the prerelease ZIP are public. PyPI/npm releases and public
self-service trial signup are not open for either path.

See the [protocol comparison](https://omelet-ai.github.io/optimization-context-protocol/reference/index.html#core-native)
and [native MCP overview](https://omelet-ai.github.io/optimization-context-protocol/guides/apps/index.html#native-mcp).

See the [native build and verification guide](docs/development/NATIVE_SOURCE_REVIEW.md)
and [source license and origin](sdk/native-contracts/LICENSE_SCOPE.md). The source
selection and Apache-2.0 notices were approved on 2026-10-28; registry and hosted
trial publication remain separate.

## Native v1 from public source

Use this opt-in path for Capability Contract v1 jobs and the eight native MCP
tools. From a fresh checkout of this repository, use Python 3.12 on macOS or Linux.
The Python/MCP path needs no Node, Foundry checkout, account, API key or model.
Run the full block from the repository root in one terminal. It downloads public
build dependencies and produces a separate local kit:

<!-- ocp:readme-native-build -->
```sh
OCP_NATIVE_WORK="$(mktemp -d)"
python3.12 -m venv "$OCP_NATIVE_WORK/build-env"
"$OCP_NATIVE_WORK/build-env/bin/python" -m pip install -r tools/requirements-dev.lock
"$OCP_NATIVE_WORK/build-env/bin/python" -B tools/build_native_candidate.py --output "$OCP_NATIVE_WORK/kit"
cd "$OCP_NATIVE_WORK/kit"
python3.12 -B install.py
.native/bin/python -I -B demo.py
```

Expect `status: "PASS"`, three actual jobs and independently checked costs:
routing **18 meters**, worker scheduling **7 cost units**, inventory **16 cost units**.
`install.py` and `demo.py` here are generated native-kit files. Keep this terminal
in the kit directory. Reuse `.native/bin/python` to rerun; choose a fresh output
path if rebuilding. No model is called. Native setup without the MCP extra is
also covered by an independent install regression.

Generate MCP configuration and run the real stdio walkthrough:

<!-- ocp:readme-native-mcp -->
```sh
.native/bin/python -I -B mcp_config.py
.native/bin/python -I -B mcp_walkthrough.py --domain worker-scheduling --input worker-input.json
```

The generated configuration selects `ocp_runtime.native_mcp` and its eight tools;
existing `ocp_runtime.mcp_server` remains the separate six-tool Core server.
For optional TypeScript, use Node 24/npm and add `--with-typescript` to the build
command with a new output directory. Native SDK entrypoints remain explicit.
See [installation, input changes and Node usage](docs/users/NATIVE_LOCAL_CANDIDATE.md),
[three-domain examples](docs/users/NATIVE_THREE_DOMAIN_WALKTHROUGH.md), and the
[engine registration template](authoring/native_server_template.py).

For an end-to-end business exercise, follow [fixed-time inspection assignment](docs/users/NATIVE_INSPECTION_ACCEPTANCE.md):
import worker/task/cost CSVs, solve, inspect assignment and workload tables, change
a condition, swap the worker engine, and recheck the result independently.
The kit now includes `project.py`, `inspection.py` and optional BYO/profile example
wheels. See [independent projects](docs/users/NATIVE_PROJECT_WORKFLOW.md) for the
same app across domains. These are local builds from public source, not registry releases.

Validation covers macOS arm64 and Linux amd64 in a network-disabled Python 3.12
container under Docker on an arm64 host. Windows and native Linux arm64 are not
verified. Automated checks do not establish external-human or model-host acceptance.

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
| Try Omelet | **Recommended when invited**; public signup is not open | [Invited trial](docs/users/INVITED_TRIAL.md) |
| Run locally | **Start now** without an invitation, account or key | [Developer quickstart](docs/users/DEVELOPER_QUICKSTART.md) |
| Bring your engine | Implement an existing profile, or define a new problem profile | [Engine authoring](https://omelet-ai.github.io/optimization-context-protocol/start/engine/) |
| Connect your AI agent | Give your host explicit context through the optional MCP binding | [MCP setup](#connect-mcp-without-calling-a-model) |

Omelet trial is the recommended introduction when an invitation is available.
It is optional; Core compliance never requires an Omelet account.

## First success from GitHub

This quickstart installs **Core 0.1**, including the six-tool Core MCP server.

Prerequisites: **Git and Python 3.12 on PATH**, on macOS or Linux.
Check `python3.12 --version` first. **Python and MCP installation need no Node or
npm.** Node 24/npm are needed only for the optional Node/TypeScript kit.
Windows is not supported by this installer. No Omelet account, trial key or
model call is needed.

```sh
git clone https://github.com/omelet-ai/optimization-context-protocol.git
cd optimization-context-protocol
```

From that repository root, run this complete block in one terminal. It downloads
public PyPI dependencies and builds a local kit; it publishes nothing.

<!-- ocp:readme-build -->
```sh
OCP_WORK="$(mktemp -d)"
python3.12 -B tools/quickstart.py --directory "$OCP_WORK"
cd "$OCP_WORK/kit"
```

Keep this terminal in the kit directory for the commands below. `start.py` and
the sample JSON files are **generated kit files**, not files in the repository root.
The temporary directory keeps generated environments out of your checkout. For
a lasting installation, choose a new directory outside the checkout instead of
`mktemp -d`, keep it in place, and regenerate host configuration if you move it.

The setup command installs the engines, independent checker and MCP server, then
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
The `verification` field separates feasibility, cost recomputation, optimality,
infeasibility and unverified execution provenance. Read the
[verification scope guide](docs/users/VERIFICATION_SCOPE.md) before interpreting PASS.
Copy a sample to a new JSON file before editing it, and use a new request ID for
a changed problem. [Three-domain examples](docs/users/MULTI_DOMAIN_QUICKSTART.md)
show changes with known answers and the supported size/constraint limits.

For a complete data → scenario → solve → check → explanation example, follow
the [worker assignment analysis](docs/users/WORKER_ANALYSIS.md). It reads CSVs,
compares changed costs and availability, and writes assignment tables plus exact
OCP transcripts. The sample costs are 12, 14 and unavailable for a proven
infeasible scenario; missing costs are never converted to zero.

## Current profile limits

These are limits of the current **0.1.0 profile contracts**, not universal limits
of OCP Core. A selected engine may advertise a narrower scope.

| Profile | Current contract | Not supported by this profile |
| --- | --- | --- |
| `routing.basic` | 1–64 visits, 1–16 vehicles, one depot, integer meter matrix and kg capacity | Time windows, multiple trips, soft constraints |
| `worker.scheduling` | 1–8 fixed-time tasks, 1–4 workers | Shift generation, breaks, travel, fairness objectives |
| `inventory.replenishment` | 1–4 independent products, 1–6 daily periods, orders ≤5 items per product/period, capacity ≤50 items | Demand forecasting, shortages, shared capacity or budgets |

The routing teaching engine has a narrower limit of 6 visits and 3 vehicles.
Consult [the contracts and compatibility rules](docs/users/COMPATIBILITY.md)
and discover the engine's actual capabilities before building a request.

## Connect MCP without calling a model

This section uses **Core 0.1** tools. Native v1 has a separate eight-tool binding
and is not installed by these commands.

OCP defines optimization request and result semantics. The optional MCP binding
makes that context and those operations available to an AI host; OCP also works
through library and HTTP bindings without MCP.

For a request such as “reduce delivery distance while respecting capacity”, the
recommended agent flow is:

1. Call `ocp_context()`, select an advertised profile, and inspect its schema and request template.
2. Ask for missing capacities or distances instead of inventing them.
3. Validate supported requirements before executing a solve.
4. Evaluate a returned solution, run the independent checker, and explain its actual status and verification scope.

This is recommended behavior, not a recorded model conversation or a guarantee
for every model/host. Provider evaluation and independent checking are separate.

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
| `python3.12` is missing | Install the prerequisite version, or put its executable on PATH. These instructions do not install system runtimes. |
| `start.py` or a sample is missing | Complete the kit build, then `cd "$OCP_WORK/kit"` in the same terminal. Do not run kit commands from the repository root. |
| `ENVIRONMENT_EXISTS` | Reuse `.agent/bin/python` to run examples; choose a new path only for a fresh install. |
| A download/build fails | Preserve the failure output and check public PyPI access. Run the build block again to create a new temporary directory. No automatic retry occurs. |
| MCP config works here but not on another machine | Install the kit on the host machine and generate its configuration there; local paths do not transfer between machines. |

The full local regression environment is Python 3.12 on macOS Apple Silicon.
An earlier complete-kit installation ran on Python 3.12.15 in a Linux x86_64
container under Docker Desktop on that Mac; this is not verification of every
subsequent installer change. Additional Python/MCP/Node checks are recorded for each exact ZIP using the
[evaluation rehearsal](docs/development/NO_KEY_EVALUATION.md). Native Linux machines
and the full Linux trial integration remain separate work; the installer rejects
Windows. Node 24 is also used by the optional Node/TypeScript consumer.

See [first-use instructions](docs/users/INVITED_TRIAL.md) and
[connect your app or engine](docs/users/DEVELOPER_QUICKSTART.md).

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
명시하는 인터페이스입니다. Apache-2.0으로 소스와 설명 사이트가 공개된 개발자 프리뷰이며, trial 운영과 패키지 레지스트리 출시는 별도입니다.
[한국어 시작 안내](docs/users/GETTING_STARTED.md)를 참고하세요.
