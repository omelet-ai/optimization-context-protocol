# Native v1: local review quickstart

Use this candidate when developing against Foundry Capability Contract v1 jobs.
It is a **public source developer preview** under Apache-2.0. Build the kit
from the repository using the native source quickstart in README.md before
following this installation guide. The Core quickstart remains a separate path.
Neither PyPI nor npm contains these candidate releases. Bundle hashes check
file integrity, not the identity or trustworthiness of their source.

## Install and solve

Use Python 3.12 on macOS or Linux. This installation needs no Node, Foundry
checkout, account, API key or model. The current native bundle has been tested
on macOS arm64 and Linux amd64 (Python 3.12, offline Docker on an arm64 host
using amd64 emulation). Native Linux arm64 is unverified. Windows is not supported
by this installer. Current stage evidence records the exact bundle and image.

Open a terminal **inside the generated native kit directory**, then run:

<!-- ocp:native-install -->
```sh
python3.12 -B install.py
```

This installs the included SDK, original native contract and independent checker
wheels into a new `.native` environment. Public third-party dependencies are
downloaded by pip. For offline installation, supply `--offline-wheelhouse PATH`
for each reviewed dependency folder. An existing environment is never overwritten.
If setup fails, retain its output, fix the cause and use a new `--venv` path.

<!-- ocp:native-demo -->
```sh
.native/bin/python -I -B demo.py
```

This starts one local native server, submits three real jobs, independently
checks their results and stops the server. Expect `status: "PASS"`,
`execute_calls: 3`, `model_calls: 0`; routing is `feasible` with distance 18m,
worker scheduling is `optimal` with cost 7, and inventory is `optimal` with
cost 16. A native job being `succeeded` only means computation finished.
Inspect each `response.status` and `independent_check` for mathematical meaning.

To use your data, copy the relevant input file to a new location and run:

<!-- ocp:native-worker -->
```sh
.native/bin/python -I -B demo.py --domain worker-scheduling --input worker-input.json
```

Available domains are `routing-basic`, `worker-scheduling` and
`inventory-replenishment`. The example generates a new request/idempotency key
for each new experiment. Application retries after uncertainty must keep the
original key and input; never silently resubmit with a new key.

For complete input-change experiments and result interpretation in all three
domains, follow the bundled `WORKED_EXAMPLES.md` (source:
`docs/users/NATIVE_THREE_DOMAIN_WALKTHROUGH.md`). `demo.py --output NEW_FILE.json`
saves the full request, result, independent verification and concise `summary`.
An existing output file is rejected before any solve. Invalid data returns
`INPUT_REJECTED` with `issues[].fieldPath`, code and message. Fix the named field
and rerun; invalid data is different from a valid problem with no feasible solution.

## Connect MCP without running a model

<!-- ocp:native-config -->
```sh
.native/bin/python -I -B mcp_config.py
```

Paste the emitted JSON into your chosen MCP host. The command prints an absolute
Python path and arguments `-I -B -m ocp_runtime.native_mcp`; it does not edit host
settings, start a model, or expose credentials. Keep the installed environment
in place, or regenerate the configuration after moving it.

Start with `ocp_native_context`, choose a domain, and read its exact catalog,
schemas, `selectionTemplate`, `requestTemplate` and limits. Fill input, resolve
requirements, validate, submit, poll, fetch results and evaluate. There are eight
tools, including cancel. Cancellation is a request: confirm terminal state before
saying computation stopped. Provider evaluation and independent checking are
different operations. This is a stateless local MCP binding, not the full OIP
gateway or ocps1 environment profile.

## Optional Node app

Only this section requires Node 22 or 24 and npm. It also requires a bundle built
with `--with-typescript`; the default Python-only build excludes Node archives.
From a bundle containing both `.tgz` files:

<!-- ocp:native-node-install -->
```sh
npm install --ignore-scripts --save-exact ./omelet-ocp-native-contracts-0.0.0-foundry.7547036d1bc9.review.1.tgz ./ocp-candidate-0.1.1-native.7547036d1bc9.review.1.tgz
```

<!-- ocp:native-node-demo -->
```sh
.native/bin/python -I -B demo.py --node
```

`node_app.mjs` imports `createOptimizationApiClient` from `ocp-candidate/native`.
The Python host starts the API and passes the temporary connection to the Node
child over stdin, then independently verifies its results and stops the server.
For your app, configure endpoint, token and tenant in your trusted backend.

## Compatibility and extension

For new native integrations use `ocp_candidate.native` or `ocp-candidate/native`.
Existing Core 0.1 applications keep their imports and synchronous semantics.
Do not change the existing default client merely by updating a dependency.
Native v1 wraps the declared Core 0.1 domain payload in real asynchronous jobs;
it does not automatically convert arbitrary profiles. See the supplied
`COMPATIBILITY.md` for the boundary and migration policy.

A new engine provides a domain adapter and an importable solve function to the
common server. This bundle includes `native_server_template.py` and
`EXTERNAL_EVALUATION.md` with own-app and own-engine tasks. The runnable template
reuses the reference provider; it is not evidence of an independently written engine.
No Foundry source checkout is used at runtime. Python entry scripts that start
solves need an `if __name__ == '__main__':` guard for spawned worker processes;
the supplied examples already include it.

Limits: small reference problems, localhost only, volatile two-hour jobs, default
128 jobs per session, no production identity or persistent store, no automatic
solver retry. These are local product policies, not universal protocol limits.
No external trial entitlement is created. Publishing this bundle, changing
company services or running an LLM requires its own approved scope.
