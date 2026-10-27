# Three optimization domains, one application flow

Private developer preview. These are small executable reference profiles, not
production scheduling or inventory services. No model, account or hosted engine
is needed. The profiles are worker.scheduling 0.1.0 and inventory.replenishment
0.1.0 alongside routing.basic 0.1.0. assignment.fixture remains a fixture.

From an extracted developer kit, install into a new environment:

```sh
python3.12 start.py --mcp --venv .agent
.agent/bin/python -I -B multi_app.py --profile routing.basic --input basic-input.json --request-id routing-1
.agent/bin/python -I -B multi_app.py --profile worker.scheduling --input worker-input.json --request-id worker-1
.agent/bin/python -I -B multi_app.py --profile inventory.replenishment --input inventory-input.json --request-id inventory-1
```

Expected baseline total costs are 18 meter, 7 cost_unit and 16 cost_unit,
respectively. Costs from different profiles are not comparable. PASS means the
returned transcript passed the independent checker; inspect solution_found and
response.status separately. No-solution or infeasible is not installation failure.
The worker and inventory reference engines use only the base Python dependencies;
`install.py --profile byo --venv .planning` suffices for those two in-process paths.

The common app discovers requirements, validates, solves once, asks the provider
to evaluate, then checks independently. Copy the input JSON and change values to
use your problem. Keep all required fields and units; use a new request ID when
changing the problem. Invalid inputs return execute_calls=0.

## Worker example

Three fixed tasks overlap: pack [0,60), inspect [30,90), ship [90,150).
Alice and Bob are available [0,180), with 120 minutes each. The optimum cost is
7: Alice packs and ships, Bob inspects. End equals the next start is permitted.
Change Alice's pack cost from 2 to 9: the optimal assignment changes and cost is 8.
Remove Bob from all eligible sets, with corresponding cost keys removed: pack
and inspect cannot both be assigned to Alice, and the result is infeasible.

Limits: 8 tasks, 4 workers, integer minute offsets, nonnegative pair costs. Every
task requires exactly one worker. No shift generation, breaks, travel or fairness.
See the [worker contract](../../spec/profiles/WORKER_SCHEDULING_0_1.md).

## Inventory example

Four days have demands [2,1,3,2], initial stock 2, lead time 1, order limit 5,
unit order cost 1, fixed positive-order cost 4 and holding cost 1. One optimum
orders [1,5,0,0] and ends each day with [0,0,2,0]; total cost is 16.
Set holding_cost to 0: a verified optimum costs 14. Set initial_inventory to 0
while keeping lead_time=1 and no scheduled receipts: day 0 cannot be served.

The input is a supplied forecast. Historical sales are not automatically a forecast.
Receipts arrive before demand; capacity applies before demand; holding cost uses
ending inventory. Products are independent, shortages forbidden, terminal stock
explicit, and orders arriving outside the horizon must be zero. Limits: 4 products,
6 days, order quantities <=5 items. See the
[inventory contract](../../spec/profiles/INVENTORY_REPLENISHMENT_0_1.md).

## MCP

The same six tools support every provider. Test one domain without a model:

```sh
.agent/bin/python -I -B local_agent.py smoke --profile worker.scheduling --input worker-input.json --request-id mcp-worker-1
.agent/bin/python -I -B local_agent.py smoke --profile inventory.replenishment --input inventory-input.json --request-id mcp-inventory-1
.agent/bin/python -I -B local_agent.py config --profile inventory.replenishment
```

For all three domains in one MCP server, configure the absolute installed Python
path with arguments `-I -B -m ocp_runtime.mcp_server --profile all`. The process
uses stdio and stdout is reserved for MCP. A host starts the process, discovers
tools, calls ocp_context(), reads available_profiles, then calls
`ocp_context(profile="worker.scheduling")` (or another advertised exact ID).
Use its request_template, input_schema and profile_semantics. Requirements and
describe accept the same optional profile selector. Validate, execute and evaluate
route by the request's exact profile version and capability; no fallback occurs.
The default single-provider invocation remains routing.basic.

An LLM must ask for missing availability, eligibility, costs or lead time; it must
not invent them. A scenario comparison needs separate requests, the changed input,
actual tool results and matching metrics/units. MCP protocol tests are not actual
LLM judgment tests. Additional model runs require separately bounded approval.

## Your Node app

Start a local provider in another terminal; it prints its loopback URL:

```sh
.agent/bin/python -I -B -m ocp_runtime.http_server --profile worker.scheduling
node own_app.cjs http://127.0.0.1:PORT worker-input.json node-worker-1
```

Use `--profile inventory.replenishment` and inventory-input.json for inventory.
The Node source is identical for routing, worker and inventory. Its evaluation
is provider evaluation; the separately installed Python checker can validate the
returned request/response using conformance.runner.CHECKERS.

## Add your own profile

Core and the clients contain no domain calculations. Implement the five Adapter
operations and exact profile semantics. Register explicit local schema objects and
semantic notes with `ocp_candidate.profiles.ProfileRegistry.register(...)`, then
pass the registry to `create_mcp(your_adapter, registry=registry)`. Several adapters
may be passed as a list. A registry entry supplies context, not a solver or an
independent checker. Supply and test your own checker separately. Duplicate
versions, schema-ID drift and external schema references are rejected; no schema
URL is fetched. Profile selection is an explicit deployment choice, not model code execution.
