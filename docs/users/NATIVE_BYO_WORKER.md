# Bring a separate worker engine to the same native app

Public source preview, included in the `v0.1.1-preview.1` native ZIP or built
locally with `tools/build_native_candidate.py`.
These commands run after the native kit's `README.md`
installation in a new Python 3.12 environment. No Node, account or model call is
needed. This optional example wheel is bundled in the kit; it is not published to a registry.
Do not use these commands against a shared Foundry checkout.

The reference provider uses bounded branch-and-bound search. The separate
`ocp-worker-greedy-example` package implements time-ordered greedy assignment
without importing the reference adapter, solver or independent checker. It shares
the canonical SDK, `worker.scheduling@0.1.0` schemas and generic native server.
Both accept 1–8 fixed-time tasks and 1–4 workers. This is an interoperability
example, not a production scheduling engine or an independently authored external
integration. The existing `native_server_template.py` intentionally still reuses
the reference provider; it demonstrates registration only.

## Install and change engine

Run inside the kit directory. The first command installs only the included wheel;
the base installation has already installed its SDK dependency. The installer's
manifest check covers this optional wheel too. Keep the kit files unchanged.

<!-- ocp:byo-install -->
```sh
.native/bin/python -m pip install --no-index --no-deps ocp_worker_greedy_example-0.1.0-py3-none-any.whl
.native/bin/python -m pip check
.native/bin/python -I -B byo_worker_scenarios.py
```

Use the same input and app, changing only the engine flag:

<!-- ocp:byo-reference -->
```sh
.native/bin/python -I -B demo.py --domain worker-scheduling --worker-engine reference --input byo-inputs/adjacent.json
```

<!-- ocp:byo-greedy -->
```sh
.native/bin/python -I -B demo.py --domain worker-scheduling --worker-engine byo --input byo-inputs/adjacent.json
```

Both return cost 2. The reference result is `optimal`; the greedy result is
`feasible` with `proof: null`. Inspect `independent_check.checks`: feasibility and
objective recomputation are `PASS`; greedy optimality is `NOT_CLAIMED`.
`PASS` with no solution means the transcript is consistent, not that a schedule
was found. The separate `execution_attestation` field remains `NOT_CHECKED`.

## Change the problem and compare the result

Replace `adjacent.json` with each file below and run both engine commands. The
five constraints stay enabled; neither engine silently relaxes them.

| Input | Reference | BYO greedy | What the app must communicate |
| --- | --- | --- | --- |
| `adjacent.json` | optimal, cost 2 | feasible, cost 2 | Adjacent half-open intervals may share a worker. |
| `changed-budget.json` | optimal, cost 3 | feasible, cost 101 | Worker a may now work only 60 minutes; a greedy early choice can be expensive. |
| `quality-gap.json` | optimal, cost 3 | feasible, cost 101 | Same profile does not promise the same solution quality. |
| `greedy-trap.json` | optimal, cost 3 | unknown, no solution | A greedy miss does not prove infeasibility. |
| `infeasible.json` | infeasible, independently checked | unknown, no solution | The heuristic has no infeasibility proof. |
| `invalid-unit.json` | rejected before execution | rejected before execution | The profile requires minutes, not hours. |

The greedy algorithm sorts tasks by `(start, end, id)`, then picks the cheapest
currently available eligible worker, breaking cost ties by ID. It does not
backtrack. A missed placement produces `unknown/search_exhausted`; a deadline
without a complete assignment produces `unknown/time_limit`. A complete
assignment can only be `feasible`, never `optimal`. No partial assignment is
misrepresented as a valid schedule.

## Connect your own provider

Implement the five Core operations in your own package. Reuse the SDK/schema
validation, but supply your engine and honest result semantics. The BYO example
package is under `authoring/worker_greedy/` in the source candidate. Its
`registration.py` connects `WorkerProvider` to the generic `ReferenceDomain`
wrapper (the name does not require a reference solver) and a module-level solve
function to `Registration`. Keep this function importable by spawned workers.
Register it with `LocalAPI([registration()])`; the app then discovers the
capability, validates, submits, polls and independently checks the result through
the same SDK. The common app's only engine-specific branch selects registration.
The request capability identifies the selected engine; input/profile/configuration
and client operations remain unchanged. Send a fresh idempotency key per changed
request; do not replay a reference capability ID against another provider.

For programmatic MCP use, pass `{'worker-scheduling': local.client('worker-scheduling')}`
to `ocp_runtime.native_mcp.create_native_mcp`. The same eight tools and context
builder expose the BYO capability and limitations. MCP transport testing is local
and does not invoke a language model. The default three-domain MCP launcher keeps
its reference registrations.

H56 checks fresh offline installation, both engines in this app, actual native
jobs, generic MCP calls, randomized bounded inputs, and deliberately corrupted
results. The BYO execution is also run in a subprocess that rejects imports of
reference providers and conformance code; the independent checker runs separately.
These checks do not establish real external adoption or engine certification.


To exercise the actual MCP path without a model:

<!-- ocp:byo-mcp -->
```sh
.native/bin/python -I -B mcp_walkthrough.py --domain worker-scheduling --worker-engine byo --input byo-inputs/adjacent.json
```

A model host can launch the installed Python with `-I -B -m ocp_worker_greedy` to
serve this worker capability through stdio. Configure this only in an approved
host; these local checks do not run or change any model host.


H58 extends this local verification to the optional Node SDK on macOS arm64 and
Python/MCP on Linux amd64 under Docker emulation with networking disabled. All
six inputs above run with both engines. The expected cost/status differences
remain visible across bindings; compatibility does not promise engine quality.
Linux Node, Windows and native Linux arm64 are outside this check. See
[custom profile registration](NATIVE_PROFILE_EXTENSION.md) to add a new problem,
solver and independent checker without adding per-domain branches to the app.
