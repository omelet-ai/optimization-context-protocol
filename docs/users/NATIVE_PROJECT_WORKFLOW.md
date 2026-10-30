# Start an independent optimization project

This developer preview turns the native kit into a separate project.
Omelet engineers and external developers use the same installed contracts, SDK,
server and checker. The project does not copy or modify a Foundry checkout.
`project.py` is an example application you may replace, not a new protocol layer.
Its `ocp-project/1` files are application settings, not a universal OCP contract.

The published `v0.1.1-preview.1` native ZIP includes this workflow and optional
example wheels. Extract it, or build public source with
`tools/build_native_candidate.py`. Use the kit containing `project.py` and this
guide; rebuilding source is unnecessary if you already have it. Python 3.12 is required;
Node, Git, a Foundry checkout, accounts and model API keys are not needed at runtime.
The harness tests fresh macOS arm64 and offline Linux amd64 under emulation.
No Windows or native Linux arm64 support is claimed.

## Create and install

From the reviewed kit directory, choose a new sibling folder. The generator
checks the selected files' hashes and refuses to overwrite an existing folder:

<!-- ocp:project-init -->
```sh
python3.12 -I -B project.py init --directory '../my optimization project'
```

The new directory contains its own installer, pinned local wheels, constraints,
application, synthetic inputs, MCP walkthrough and review form. It contains no
Git metadata, source checkout, credentials or previous execution records.
Change into it before executing the following commands:

<!-- ocp:project-install -->
```sh
python3.12 -B install.py
```

Installation normally downloads public dependencies. For a prepared offline
environment, append `--offline-wheelhouse PATH` for each reviewed wheel folder.
Install **before editing the supplied files**: installation verifies the original
manifest. Afterwards, create your own input/config copies for new experiments.
If installation fails, retain the partial environment and retry with a new
`--venv` path. Use that path in place of `.native` in subsequent commands.

## Assign fixed-time tasks, change a condition, compare

The worker example assigns packing, inspection and shipping tasks to eligible
workers. It enforces availability, non-overlap and maximum working minutes.
These are generic tasks with fixed intervals; no nurse-specific rules or shift
generation are implied. Costs are per assignment in `cost_unit`, not hourly rates.

For a six-task inspection business exercise with CSV input, readable assignment
and workload reports, and an owner acceptance checklist, use `INSPECTION_GUIDE.md`
in the generated project (source: `docs/users/NATIVE_INSPECTION_ACCEPTANCE.md`).
It reuses this application and the same worker profile; it adds no new Core contract.

<!-- ocp:project-worker -->
```sh
.native/bin/python -I -B project.py run --project worker-project.json --output runs/baseline
```

Expect `solution_status: optimal`, independently recomputed cost **7**, and
`optimality: PASS` within the small profile's enumeration bounds. Read the full
assignments in `runs/baseline/response.json`. A `succeeded` job is a completed
computation, while `optimal` is a separate mathematical claim.

Suppose Alice can work only 60 minutes instead of 120. Create a scenario without
overwriting the original input:

<!-- ocp:project-change -->
```sh
.native/bin/python -I -B - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('worker-input.json').read_text())
data['workers'][0]['max_minutes'] = 60
with Path('worker-short-input.json').open('x') as f: json.dump(data, f)
config = json.loads(Path('worker-project.json').read_text())
config['input'] = 'worker-short-input.json'
with Path('worker-short-project.json').open('x') as f: json.dump(config, f)
PY
.native/bin/python -I -B project.py run --project worker-short-project.json --output runs/shorter-availability
.native/bin/python -I -B project.py compare runs/baseline runs/shorter-availability
```

Expect cost **9**, `same_problem: false` and `right_minus_left: 2`. This is the cost
of a changed condition in the synthetic example, not evidence that one engine is
better. Compare only compatible profiles and objective definitions/units. A
missing solution has null cost and no numeric difference; null never becomes 0.

## Replace the engine without changing your app

The optional greedy engine is implemented independently of the reference solver:

<!-- ocp:project-byo -->
```sh
.native/bin/python -I -B -m pip install --no-index --no-deps ./ocp_worker_greedy_example-0.1.0-py3-none-any.whl
.native/bin/python -I -B project.py run --project worker-project.json --engine byo --output runs/byo
.native/bin/python -I -B project.py compare runs/baseline runs/byo
```

Both cost **7** in this example, but the greedy result is `feasible` and its
optimality is `NOT_CLAIMED`. Matching results do not imply equal algorithms.
Use `byo_worker_scenarios.py` to create cost-gap, greedy-trap and infeasible cases.
Changing only the worker's engine leaves the native job contract and application
flow unchanged. An independently written engine is not an independently tested
external developer integration.

## Other domains and MCP

<!-- ocp:project-domains -->
```sh
.native/bin/python -I -B project.py run --project routing-project.json --output runs/routing
.native/bin/python -I -B project.py run --project inventory-project.json --output runs/inventory
```

Expect routing `feasible` at **18 meters**, inventory `optimal` at **16 cost units**.
Both use the same `project.py` path, native server and independent verification.
For an installed custom profile, pass explicit trusted `--extension MODULE:FACTORY`
and `--checker-factory MODULE:FACTORY` to `run`; pass the checker explicitly again
to `review`/`compare`. Input/config/record files cannot select executable factories.
The supplied `budget-project.json` needs the three optional budget wheels first.

<!-- ocp:project-mcp -->
```sh
.native/bin/python -I -B mcp_config.py
.native/bin/python -I -B mcp_walkthrough.py --domain worker-scheduling --input worker-input.json
```

This prints MCP host configuration, then runs actual stdio tool calls, one job,
same-key replay and independent checking. It makes **zero LLM calls**. Model-host
acceptance is separate. Keep the environment in place or regenerate configuration.

## Review results and failure handling

<!-- ocp:project-review -->
```sh
.native/bin/python -I -B project.py review runs/baseline
```

This command checks file integrity, record identity and recomputes constraints,
objective and supported proof claims using the independent checker. It does not
trust the stored `check.json` PASS or start an engine. The checks have explicit
scope; record hashes are not signatures, engine execution attestation or human
acceptance. A party replacing a whole internally consistent record is not detected
as a forgery. Keep a trusted copy of the record hash when exchanging evidence.

Each new output directory contains catalog/requirements/validation, the request,
job identity, original result, verification report and package versions. Tokens
and endpoint credentials are not saved. Actual problem and solution data **are**
saved: use synthetic data for evaluation and review any sharing separately.

Invalid inputs return `INPUT_REJECTED` with field issues and zero submit attempts.
An existing output directory is rejected before any job. A failed or uncertain
submission keeps its journal and original idempotency key, with no automatic
retry. This local server is volatile: stopping it loses server-side jobs. The
journal cannot resume a stopped server or prove cancellation. Read the recorded
failure before deliberately starting a new experiment in a new directory.

## Adoption review

`ADOPTION_REVIEW.json` starts with internal acceptance and external independent
developer evaluation both `NOT_RUN`. Automation never changes those fields.
An actual reviewer should independently modify an input, explain the cost change,
swap an engine, inspect MCP calls and reject a corrupted solution. Record first
error, environment, help needed, time to first verified solution and remaining
limitations. A maintainer's automated PASS is not the reviewer's acceptance.

This workflow is ready for local evaluation after its recorded harness gates
pass. The GitHub prerelease provides a public kit; do not include private
project data or completed review records when sharing it. Organization-wide
migration, registry publication, deployment and additional model trials require
their own approved scope.
