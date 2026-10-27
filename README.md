# Optimization Context Protocol (OCP)

**Connect optimization engines to applications and AI agents through an explicit contract.**

OCP describes what an engine supports, what an application requests, what was
actually enforced, and how to check the result. Applications can use their own
engines independently of Omelet, Foundry, Studio, or a particular transport.

**Status: developer preview.** This repository is currently private. The code and
packages are evaluation candidates; a public license, registry release and public
trial enrollment are pending. A passing local check is not engine certification
or evidence of unaided external adoption.

## See the benefit in one command

After receiving and unpacking the credential-free developer kit:

```sh
python3.12 start.py --venv .local
```

This verifies the kit, installs pinned dependencies into a new environment, and
runs **the same application and input through two real engines**: OR-Tools and an
independent enumerating teaching library. It checks both outputs, then demonstrates
rejected units, intentionally corrupted results, and a real execution deadline.
No Omelet account or trial key is needed. The command is for the extracted kit;
[source checkout build instructions](docs/development/BUILD_FROM_SOURCE.md) explain
how to produce it. There is no public download or registry install claim yet.

The full local regression environment is Python 3.12 on macOS Apple Silicon.
The first-success command also ran on Python 3.12.15 in a Linux x86_64 container
under Docker Desktop on that Mac. Additional Python/MCP/Node checks are recorded for each exact ZIP using the
[evaluation rehearsal](docs/development/NO_KEY_EVALUATION.md). Native Linux machines
and the full Linux trial integration remain separate work; the installer rejects
Windows. Node 24 is needed only for the optional Node/TypeScript consumer.

See [first-use instructions](docs/users/INVITED_TRIAL.md) and
[connect your app or engine](docs/users/DEVELOPER_QUICKSTART.md).

For a no-key local LLM connection, use `python3.12 start.py --mcp --venv .agent`
from the kit and follow the [MCP quickstart](docs/users/LLM_QUICKSTART.md).
It installs the engine and MCP together. Doctor, smoke and config generation
do not call a language model; model-host usage remains separate.

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
speed or support for every optimization domain. The current runnable examples
focus on routing. `assignment.fixture` checks a second domain's contract; it does
**not** currently provide a second-domain solver.

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

Only the [selected source files](provenance/repository-selection.json) belong in
this private repository. Internal material, credentials, original snapshots and
execution evidence stay outside it. Publication requires a separate approved
file inventory, rights review and exact destination authorization.

한국어: OCP는 앱·AI 에이전트와 최적화 엔진 사이의 지원 기능·요청·결과·검증을
명시하는 인터페이스입니다. 현재는 개발자 프리뷰이며, 공개 출시는 별도 관문입니다.
[한국어 시작 안내](docs/users/GETTING_STARTED.md)를 참고하세요.
