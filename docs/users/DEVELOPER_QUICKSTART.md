# Build your own app and engine

Run these commands from the extracted developer kit, using Python 3.12 and Node 24
for the optional Node examples. No company checkout, Foundry, key or account is
needed for local use. These are locally built developer-preview artifacts, not published registry packages.
README.md lists prerequisites, platform verification scope and offline options.
한국어 시작 안내와 초대 trial 절차는 README.md 아래에 있습니다.

## 1. Install and get a real result

```sh
python3.12 --version
python3.12 start.py --venv .local
.local/bin/python -B demo.py --diagnostics
```

The start command installs into a new environment and runs the same app/input
with OR-Tools and a small enumerating library. Both outputs are independently
checked; the bundled problem has cost 18 meters. Installation preserves existing
environments. Use a new `--venv` path if you need a clean retry. The diagnostic
also demonstrates rejected units, damaged solutions and an actual 1 ms deadline.
A feasible answer is not a proof of optimality. No solution at a deadline is unknown.

For LLM/MCP use `python3.12 start.py --mcp --venv .agent` instead and follow
LLM_QUICKSTART.md. It includes both engine and MCP dependencies. Its doctor and
smoke checks do not call a model or edit host settings.

## 2. Change the input and build a Python app

Copy `basic-input.json` to `my-input.json`. Double each matrix value for a simple
recalculation check (the bundled problem's checked cost becomes 36 meters), then
try your own synthetic demands/capacities. Adding or renaming visits requires
matching `matrix.node_ids` and rows/columns. Units are kg and integer meters; the
matrix model is explicit_matrix and rounding is none. Unsupported choices fail
validation. `input.json` is a separate coordinates profile for the invited trial.

```sh
.local/bin/python -B own_app.py --input my-input.json --request-id my-app-1 --trace my-app-1.json
```

`own_app.py` is a small complete app: discovery → requirements → validation →
execution → provider evaluation → independent checker. Copy it to a new filename
and replace input loading/presentation with your UI, backend or notebook logic.
Keep failure distinct from result; read result.status, termination and solution.
Only evaluate a non-null solution. Preserve unevaluated metric nulls rather than
turning them into zero. Keep the request ID on an uncertain retry of the same
job; use a new ID for a changed input/job. There is no automatic fallback.

Traces/transcripts create new files only. `TRACE_EXISTS` means preserve the old
file and select a new output name. `TRACE_DIRECTORY_MISSING` means create the
parent directory first. Never change the job identity merely to bypass uncertainty.

## 3. Connect a Node/TypeScript application

Install the local Python provider above first. The Node SDK is a separate consumer;
Node does not run OR-Tools. Node 24/TypeScript 7 versions are pinned in package.json.
This section needs the full kit; the README's Python-only kit deliberately excludes
Node files. See the source build guide for the optional full kit before proceeding.

```sh
node --version
npm install --no-save --package-lock=false --ignore-scripts --no-audit --no-fund ./ocp-candidate-0.1.0.tgz
npm run build
```

In terminal A start the loopback-only provider:

```sh
.local/bin/python -I -B -m ocp_runtime.http_server --port 8765
```

In terminal B:

```sh
node dist/main.js http://127.0.0.1:8765 basic-input.json --request-id my-ts-job-1
node own_app.cjs http://127.0.0.1:8765 my-input.json my-node-job-1
```

`main.ts` is the small TypeScript execution example. `own_app.cjs` includes explicit
validation and provider evaluation; copy it and replace file input/presentation
with your own server-side application. Its output includes request and response
for independent checking. Provider evaluation is not independent verification.
Do not put a trial token in browser JavaScript. Stop the local provider with Ctrl-C.

To check the Node app's synthetic output separately:

```sh
node own_app.cjs http://127.0.0.1:8765 my-input.json my-node-job-2 > node-result.json
.local/bin/python -I -B -c "import json; from conformance.routing import verify_result; t=json.load(open('node-result.json')); print(verify_result(t['request'],t['response']))"
```

Choose a new output filename to preserve earlier evidence. If the app fails,
inspect the error before running the checker; do not treat an empty file as a result.
The checker verifies the supplied request/result, not every possible engine behavior.

## 4. Bring your own engine without OR-Tools or MCP

```sh
python3.12 install.py --profile byo --venv .byo
.byo/bin/python -B byo_library.py basic-input.json --trace own-engine-trace.json
.byo/bin/python -B export_transcript.py --trace own-engine-trace.json --artifact byo_library.py --out own-engine-transcript.json
.byo/bin/python -B -m conformance.runner --bundle own-engine-transcript.json --artifact byo_library.py
```

Copy `byo_library.py` to `my_engine.py`. Replace `EnumeratingLibrary.solve(problem,
time_limit_ms)` with your actual algorithm. Keep `name`, `version`, `solve` and the
`Outcome(solution, termination, objective)` return shape. A solution contains
`routes`, each with `vehicle_id` and ordered `visits`. Extend
`OwnLibraryAdapter.validate` to reject any unsupported condition. The teaching
adapter supports at most six visits and three vehicles. A heuristic that finds no
solution must return unknown unless it has an applicable proof of infeasibility.

Run your new file with a new synthetic input and an unsupported case. Export the
new trace with `--artifact my_engine.py` and a new output filename. The checker
binds the transcript to an artifact hash; it does not prove that this code produced
that transcript or certify the whole engine. A copied sample alone is not evidence
of an independent engine integration.

## 5. Optional invited Omelet trial

Follow README.md's invitation instructions and trial doctor first. Use the
separate coordinates input and an explicit session file:

```sh
.venv/bin/python -B own_app.py --session session.json --input input.json --request-id my-trial-job-1 --trace my-trial-trace.json
```

An expired key or changed catalog is a reason to stop and contact the inviter,
not a reason to silently switch engines or override the expected catalog pin.
No trial session is included in the no-key evaluation kit.

## 6. Report what happened

Use EVALUATION_TASKS.md and a new copy of FEEDBACK_TEMPLATE.md. Record exact kit
and source hashes, platform versions, time, help, failures and retries. Share only
reviewed synthetic input/code/results, never credentials, private URLs, customer
data, home paths or model login logs. Nothing is uploaded by these examples.

For executable worker scheduling and inventory replenishment through the same
app/MCP flow, follow the [three-domain quickstart](MULTI_DOMAIN_QUICKSTART.md).
