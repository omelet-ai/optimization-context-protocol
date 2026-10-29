# Apply three problems through one native server

This is a local exercise for the native v1 kit built from public source. Start with
its `README.md` installation. The public GitHub Core 0.1 quickstart is a separate
path. These small synthetic problems illustrate interface reuse; they are not
production scheduling, replenishment or fleet products. No model or account is
needed. Python 3.12 on macOS arm64 is the tested environment.

## Prepare your own input files

From the installed bundle directory:

<!-- ocp:journey-inputs -->
```sh
.native/bin/python -I -B scenarios.py --output my-inputs
```

This writes twelve editable JSON files: `base`, `changed`, `infeasible` and
`invalid` for each domain. It refuses to replace an existing directory. They are
inputs only. The app obtains configuration and envelope templates from the
server's catalog. Inspect `input_schema`, `providerLimitations`, objectives and
constraints before using a different problem; adding an unsupported field does
not add a solver feature.

## 1. Routing: deliveries from one warehouse

Three deliveries weigh 2 kg each; one van carries 6 kg. Locations lie along a
synthetic line at 1, 3 and 6 meters from the warehouse. The explicit matrix
contains integer meters with `model: explicit_matrix` and `rounding: none`.
This deliberately tiny distance is an arithmetic example, not a road-network model.

<!-- ocp:journey-routing -->
```sh
.native/bin/python -I -B demo.py --domain routing-basic --input my-inputs/routing-basic-base.json --output routing-result.json
```

Expect `response.status: feasible`, distance **12 meter**, all visits covered and
capacity respected. The checker verifies feasibility and recomputes cost. It
does not promote a feasible solver result to optimal, even when this example's
minimum can be calculated by hand. `summary.optimality` is `NOT_CLAIMED`.

The `changed` file moves the farthest location to 10 meters and updates **every
corresponding matrix entry**. Running the same command with that file and a new
output name gives **20 meter**. Compare metric definition, units, configuration
and input assumptions before interpreting a cost difference.

The `infeasible` file contains a 7 kg visit, exceeding the van's 6 kg capacity.
Its proof is a capacity inequality; cost and solution remain null. The `invalid`
file labels the unchanged numbers `km`; validation rejects it. Convert numbers
to the profile's required unit explicitly instead of merely changing the label.

## 2. Worker assignment: fixed tasks and available people

Four tasks are receive (0–60), pack (60–120), dispatch (120–180), audit (30–90).
Ava, Ben and Cy are available 0–180 minutes with a 180-minute workload limit.
Ava costs 1 per regular task; Ben costs 4; Cy costs 5. Audit costs 2/3/4 respectively.
Costs are per assignment, not hourly wages. Intervals that only touch do not overlap.

<!-- ocp:journey-worker -->
```sh
.native/bin/python -I -B demo.py --domain worker-scheduling --input my-inputs/worker-scheduling-base.json --output worker-result.json
```

Expect **optimal, 6 cost_unit**: Ava handles the three regular tasks and Ben the
audit. The `changed` file lowers Ava's workload limit to 120 minutes; the best
cost becomes **9**, while task coverage and non-overlap still hold. More than
one assignment may attain the same cost; do not compare arrays as if one tie
break were required by the protocol.

The `infeasible` file makes only Ava eligible for every task, including the
overlapping audit. Independent bounded enumeration confirms there is no valid
assignment. `invalid` uses `hour`, which this profile does not accept. Current
limits are 8 fixed tasks and 4 workers; this is not a shift-generation, rest-rule
or fairness optimizer.

## 3. Inventory: orders with one-day lead time

One product has demand `[1,2,1]`, initial inventory 1, no scheduled receipts and
lead time 1. Order capacity is 4, storage capacity 5, purchase cost 2 per item,
fixed cost 3 per positive order and holding cost 1 per item at period end.

<!-- ocp:journey-inventory -->
```sh
.native/bin/python -I -B demo.py --domain inventory-replenishment --input my-inputs/inventory-replenishment-base.json --output inventory-result.json
```

Expect **optimal, 10 cost_unit**: orders `[3,0,0]`, ending inventory `[0,1,0]`.
Cost is 6 purchase + 3 fixed + 1 holding. An order placed at period 0 arrives at
period 1, before that day's demand. The `changed` file raises the last demand to
2: orders `[4,0,0]`, inventory `[0,2,0]`, cost **13**. The `infeasible` file raises
the first day's demand to 2; tomorrow's arrival cannot fix today's stockout.
The `invalid` file uses kg instead of the supported integer item quantity.
Demand is deterministic; products have no shared warehouse/budget constraint.

## Use the result in an application

Every output contains `outcomes[0].request`, `response`, `independent_check` and
`summary`. A PASS says the transcript passed the declared checks. An infeasible
problem can therefore PASS verification without providing an operational plan.

<!-- ocp:journey-read-result -->
```sh
.native/bin/python -I -B -c 'import json; r=json.load(open("worker-result.json"))["outcomes"][0]; print(r["summary"]); print(r["response"]["solution"])'
```

The app integration pattern is in `demo.py`: discover catalog → fill its template
→ validate → submit/wait through `NativeClient` → read domain status → independent
assessment. `LocalAPI` supplies the actual reference engine, ephemeral auth and
process cleanup. An application using a remote approved server instead constructs
`NativeClient(endpoint, token)` in its trusted backend. Keep credentials outside
input and model arguments. Do not place secrets in result JSON or frontend bundles.

For each saved outcome, an independent verification report distinguishes
feasibility, objective recalculation, optimality and infeasibility. Small bounded
enumeration verifies the worker and inventory claims; it is not a scalable proof
certificate for arbitrary engines. An offline transcript never attests which
binary ran. Editing a result invalidates its previous report: assess it again.

## Use the same problems through MCP

`mcp_walkthrough.py` is a real MCP SDK client, not a simulated conversation.
It launches the installed server, discovers the exact domain context, resolves
requirements, validates, submits and polls real jobs, then fetches results.
It repeats the same submit key to verify replay without another solve and calls
provider evaluation separately from the independent checker. No LLM is run.

<!-- ocp:journey-mcp -->
```sh
.native/bin/python -I -B mcp_walkthrough.py --domain worker-scheduling --input my-inputs/worker-scheduling-changed.json
```

Substitute the other domain names and JSON files to follow the same flow.
On invalid input expect `INPUT_REJECTED`, field-level issues and zero submissions.
For an infeasible result the provider returns `NO_SOLUTION` from evaluation;
the independent checker instead examines its infeasibility claim. Neither path
turns a missing solution into a zero-cost solution. Host configuration is generated
by `mcp_config.py` as explained in the bundle README.

These workflows exercise transport and tools, not an LLM's reasoning or a real
external person's unaided experience. The published prerelease ZIP is the
reviewed delivery artifact; a local rebuild has different bytes. Linux amd64
Python/MCP is tested under Docker emulation; native Linux arm64, Windows and
Linux Node remain unverified. Additional model trials require their own scope.

If a job ends as `failed` or `cancelled`, the walkthrough reports `JOB_FAILED`
or `JOB_CANCELLED` with the original job, request and idempotency key. No result,
objective or independent PASS is invented, and no resubmission occurs. A local
worker lease can expire after a host pause; inspect the job's error before
choosing a new run. A failed job is not mathematical infeasibility. Keep the
machine awake during an uninterrupted regression run; tests must still fail if
an expected calculation does not finish.
