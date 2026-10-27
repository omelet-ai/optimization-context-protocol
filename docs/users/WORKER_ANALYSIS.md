# Analyze a worker assignment, end to end

This synthetic warehouse example shows six fixed-time tasks and three workers.
It demonstrates data preparation, explicit constraint inputs, scenario changes,
actual solving, independent checking and result interpretation. It is not a
production staffing model. Task times are fixed; OCP does not invent shifts,
skills, costs, breaks or fairness constraints.

Complete the GitHub README Python setup, then run from its generated kit:

<!-- ocp:worker-analysis -->
```sh
.agent/bin/python -I -B worker_analysis.py --workers worker-workers.csv --tasks worker-tasks.csv --costs worker-costs.csv --scenarios worker-scenarios.json --output worker-analysis-first --run-id worker-first
```

Read `worker-analysis-first/analysis.md` for the comparison and assignment tables.
`analysis.json` contains exact OCP requests/results, changed inputs, SHA-256 hashes
of all four input files, provider evaluation and the independent check. No model,
Node, account or key is used. Copy the input files before changing them; use a new
output directory and run ID for a changed job. Existing output is never overwritten.

| Scenario | Actual expected status | Checked cost | Difference |
| --- | --- | --- | --- |
| baseline | optimal | 12 cost_unit | 0 |
| changed-cost | optimal | 14 cost_unit | +2 |
| later-availability | infeasible | null | null |

In the second scenario, Alice's cost for receiving rises from 2 to 9. The solver
reassigns tasks; total cost rises by 2, rather than keeping the old assignment
and adding 7. In the third, Bob becomes available only after these tasks finish.
The overlapping receive/inspect tasks can then use only Alice, so no assignment
satisfies the declared constraints. This conclusion is independently enumerated.
It is not inferred from a timeout. A timeout without a solution remains unknown.

## Input contract

- `worker-workers.csv`: `worker_id,available_start,available_end,max_minutes`.
  Multiple rows may describe one worker's non-overlapping availability intervals;
  every row for that worker must have the same workload limit.
- `worker-tasks.csv`: `task_id,start,end,eligible_workers`. Eligibility is explicit,
  separated by `|`; it is not guessed from missing costs. Intervals are half-open,
  so a task ending at 60 does not overlap one starting at 60.
- `worker-costs.csv`: `task_id,worker_id,cost`. Supply exactly one integer cost for
  every eligible pair. Missing and duplicate costs are errors, not zero cost.
- `worker-scenarios.json`: explicit `minute` and `cost_unit`, plus up to five
  named scenarios. Each starts from the baseline, not the preceding scenario.
  `set_cost` changes an already eligible task/worker pair; `set_availability`
  changes one worker's intervals. Unknown operations are rejected.

All baseline and scenario inputs are validated before the first solve. CSV headers
must match exactly. This importer accepts UTF-8 (optional BOM), simple identifiers
`[A-Za-z0-9_-]{1,40}`, nonnegative decimal integers and at most 128 KiB per file.
These are importer rules, not new Core requirements. The profile still limits
inputs to eight tasks and four workers; its workload, time and cost bounds apply.

Costs are compared only within the same profile/version, objective definition and
unit. If a scenario has no solution, cost and delta stay unavailable. PASS means
the supplied transcripts passed their checks; it does not imply all scenarios
have a solution. The checker covers coverage, eligibility, availability, overlap,
workload and total cost; bounded enumeration checks optimality/infeasibility.
Provider evaluation is separately labeled and is not the independent checker.
Each scenario also has a `verification` report and a Markdown table separating
feasibility, cost recomputation, optimality and infeasibility. Execution attestation
remains NOT_CHECKED. See VERIFICATION_SCOPE.md in the kit for full interpretation.

The same request/input objects can be passed to the multi-domain app or MCP
`ocp_validate`/`ocp_execute` tools. The CSV importer is application code: another
app can load its own database without changing the optimization contract.
