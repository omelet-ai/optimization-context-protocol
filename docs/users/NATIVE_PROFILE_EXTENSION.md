# Add your own problem without changing the SDK or server

This developer preview adds an opt-in Python registration API, version
`0.1.0`, alongside the unchanged Core 0.1 and native v1 wire contracts. It is not
a new mandatory standard or a change to existing Foundry projects. Example
source is public; its three optional wheels are included in the published
`v0.1.1-preview.1` native ZIP and current source-built native kits. No registry
packages are published. Install the supplied wheels explicitly to enable them.

The example maximizes benefit from a subset of items within a budget. The profile
package owns schemas and meanings; the engine uses dynamic programming; a third
package checks every possible subset independently. Solver and checker do not
import each other. They share only the domain definition package. Limits: 12
items, capacity 0–1000 credit. This is a bounded demonstration, not a production
portfolio or investment recommendation.

## Install and run the same application

Start with the local native kit's README installation. Inside that kit directory:

<!-- ocp:extension-install -->
```sh
.native/bin/python -m pip install --no-index --no-deps ocp_budget_profile_example-0.1.0-py3-none-any.whl ocp_budget_engine_example-0.1.0-py3-none-any.whl ocp_budget_checker_example-0.1.0-py3-none-any.whl
.native/bin/python -m pip check
```

<!-- ocp:extension-app -->
```sh
.native/bin/python -I -B demo.py --domain budget-selection --input budget-input.json --extension ocp_budget_engine.registration:extension --checker-factory ocp_budget_check:registry
```

Expected: `optimal`, total benefit **11 benefit_unit**, selected items a and b,
with capacity 7 credit. The independent assessment must identify
`ocp-budget-checker-example`, report feasibility/objective/optimality PASS, and
leave execution attestation NOT_CHECKED. It must not label benefit as cost.

Set capacity to 4 in a new input: optimal benefit is 7. Set capacity to 0: empty
selection is valid, benefit is **0**, and solution is not null. Use `hour` as the
cost unit: reject before solving. The engine always has a valid empty incumbent;
a time limit can return `feasible` with no optimality claim. It never claims
infeasibility for this optional-subset profile.

After the optional Node installation in README, append `--node` to the same app
command. No Node-specific profile or solver implementation is needed.

<!-- ocp:extension-mcp -->
```sh
.native/bin/python -I -B mcp_walkthrough.py --domain budget-selection --input budget-input.json --extension ocp_budget_engine.registration:extension --checker-factory ocp_budget_check:registry
```

This uses actual stdio MCP and native HTTP jobs, without a language model.
Independent checking runs in the client process, outside the engine server.
For an approved MCP host, launch the installed Python with
`-I -B -m ocp_runtime.native_extension --extension ocp_budget_engine.registration:extension`.
The common eight tools discover the new domain's schemas, units, objectives and
limits. Host configuration chooses code; tool arguments choose data.

## Implement an independent project

Keep your project outside the SDK and Foundry repositories. The three small
projects under `authoring/budget_example/` demonstrate the complete boundaries:

1. Package your input, solution and configuration schemas with a unique profile
   ID/version and explicit semantics. No runtime fetching of schema URLs.
2. Implement the five Core ports in your engine package. Use `ProfileRegistry`
   to register the exact profile and pass it both to `ReferenceDomain` and to
   `run_provider` in the spawned solve function. Export an `Extension` containing
   importable `Registration` functions. Match `EXTENSION_API` exactly.
3. Implement an independent transcript checker and expose a `CheckerRegistry`
   factory. Registration names the exact profile, checker identity, scope,
   objective metric ID and recomputed-value key. No mutation of global CHECKERS.
4. Install the distributions beside the SDK, then use the unchanged common app
   and MCP commands with explicit host factory names. Run normal, changed-input,
   invalid, timeout and result-corruption cases. Preserve SDK files unchanged.

`CheckerRegistry` callbacks receive copies of the transcript and must return
`None` for no solution, or a dictionary containing `feasible: true` and the
registered recomputed-value key. They must validate the entire profile, including
constraints and any proof claim. Shared assessment validates Core structure,
request/result identity and selected metric consistency; it cannot make an
untrustworthy custom checker mathematically correct. Inspect checker code and
record its identity/scope. Duplicate profile/checker keys are rejected; no
silent overwrite or fallback to a different version. A missing checker stops
this verified demo before compute. The protocol itself does not require every
app to use this demonstration checker.

Factories are explicit trusted local Python code. Never accept a factory name
from a user problem, LLM tool argument, remote catalog or schema. Installing a
package does not activate it, and no entry-point scanning or remote loading occurs.
Unsupported factories, profile versions, schemas or checker outputs must fail;
metadata registration alone never establishes engine correctness.

H57 covers isolated installation, same app/MCP, independent imports, maximization,
empty solutions, version/registration rejection and corrupted results. H58 adds
Node/macOS and offline Linux cross-checks. Human adoption and additional model
execution remain separate approvals.


## Compatibility and local build

The extension/checker APIs are additive preview interfaces. Existing default
registrations, six-tool Core MCP and eight-tool native MCP behavior remain in
the regression lane. Core envelopes and native wire v1 are unchanged; no new
field is mandatory. The verification report format remains 0.1.0, with the
actual selected checker's identity and objective semantics. Use the matching
SDK/checker and example wheels from `v0.1.1-preview.1` or one source-built kit;
unrelated older installations do not implicitly gain these APIs. A later release needs an explicit package version
and publication review. Do not replace installed packages silently.

From the source workspace, `tools/build_budget_example.py` builds the three
wheels using the existing development Python environment and cached build tools.
The public-source `tools/build_native_candidate.py` builder includes them as optional files in its checksum
manifest. These commands do not publish anything. H58 compares macOS arm64 Node
with emulated Linux amd64 Python/MCP using the same cases; it does not claim
Windows, Linux Node, native Linux arm64 or third-party author acceptance.
