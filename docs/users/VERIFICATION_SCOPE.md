# Read a verification result without overstating it

An OCP result is an engine's response. `ocp_evaluate` uses that provider's
evaluation logic. The separately packaged checker recomputes profile semantics.
None of these alone certifies an engine, a deployed service or external adoption.

The common Python app, local MCP smoke command and worker analysis include a
`verification` report alongside the existing `independent_check` measurement.
Read each dimension, not just the outer PASS:

| Check | Meaning | What it does not establish |
| --- | --- | --- |
| structure_and_semantics | Envelope, identity, configuration and supported solution/evaluation semantics | A proof claim, which has its own row |
| feasibility | Supplied assignment/routes/inventory plan satisfies the named profile checks | Optimality or support for undeclared constraints |
| objective_recomputation | Independent cost equals the declared metric, definition and unit | Real-world data accuracy |
| optimality | Applicable independent oracle rederives the claimed optimum | Optimality of other inputs or an arbitrary proof certificate |
| infeasibility | Applicable independent oracle/inequality proves the claimed absence of a solution | Timeout or heuristic failure as evidence of impossibility |
| execution_attestation | Always NOT_CHECKED by this offline checker | Which artifact actually produced the response |

No solution means feasibility/cost are NOT_APPLICABLE and cost remains null.
Unknown remains unknown. A feasible result leaves optimality NOT_CLAIMED.
The scope report's PASS means all applicable requested transcript checks passed;
it does not mean a solution exists or that every dimension was exercised.

## Check an app transcript independently

From the installed kit, save a new transcript and inspect its dimensions:

```sh
.agent/bin/python -I -B multi_app.py --profile worker.scheduling --input worker-input.json --request-id checked-worker > worker-result.json
.agent/bin/python -I -B -m conformance.assessment --transcript worker-result.json
```

The checker ignores existing report fields and uses only `request` and `response`.
Python callers can use `from conformance.assessment import assess`, then
`assess(request, response)`. It needs no provider, solver, network or model.
The report includes profile/version, checker/version and SHA-256 of each input's
sorted-key compact UTF-8 JSON representation. These hashes identify checked data;
they are not signatures or execution attestations. Pin the checker wheel hash too.

## Separate solution checks from proof checks

| Profile | Feasibility and objective scope | Proof scope |
| --- | --- | --- |
| routing.basic / routing.coordinates | Up to 64 visits and 16 vehicles within each schema; coverage, capacity and cost (coordinates also independently converted) | Optimality enumeration up to 7 visits/3 vehicles. Infeasibility uses supported capacity inequalities or that bounded enumeration |
| worker.scheduling | Up to 8 fixed-time tasks/4 workers; coverage, eligibility, availability, overlap, workload and cost | Independent assignment enumeration within the profile |
| inventory.replenishment | Up to 4 products/6 periods within bounded stock/order quantities; inventory balance, service/storage/order constraints and cost | Independent order-vector enumeration within the profile |
| assignment.fixture | Supplied feasible witness and assigned cost | No proof checker or solver |

`mode='full'` is the default. An optimality claim beyond a proof oracle's range
returns INCOMPLETE with that dimension UNSUPPORTED, even if feasibility and cost
pass. Invalid proof/solution/metric data return FAIL. The existing strict
`CHECKERS` and `conformance.runner` interfaces continue to reject out-of-scope or
invalid proof claims; this report does not weaken them.

`assess(request, response, mode='solution')` deliberately avoids the proof oracle.
For an optimal/infeasible response it returns PARTIAL, with the proof dimension
NOT_CHECKED. It validates the original envelope, then checks a private projection
without the claim. It never mutates the original response, changes its hash, or
turns PARTIAL into a verified optimum. Use this mode for a larger supplied route
when only feasibility and cost verification are needed.

The CLI accepts `--mode solution`. Exit codes are 0 for PASS, 1 for FAIL/input
errors, and 2 for PARTIAL/INCOMPLETE. Its transcript input is limited to 1 MiB.
A malformed original proof envelope is rejected even in solution-only mode.

MCP context provides interpretation guidance, not verification results. A model
must not claim an independent check merely because it called `ocp_context` or
`ocp_evaluate`. Run the separate checker (or local smoke host) and name its
dimensions and limits when presenting conclusions.

## Compatibility

`ocp.verification-scope` report version 0.1.0 is an additive application/checker
report, not a Core result or conformance envelope. Core/profile versions, the six
MCP tools, old measurement dictionaries and strict checker behavior are unchanged.
The MCP guide retains version 0.1.0 and adds optional `verification_guidance`.
Older clients can ignore these new report/guide fields. Consumers of the new
report should check its ID/version and treat unknown statuses as unverified.
Future incompatible report semantics require a report version change and consumer
tests. Local preview artifacts have new hashes; no registry package is published.
