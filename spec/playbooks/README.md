# Optimization playbooks — draft extension

A playbook explains a question, prerequisites and interpretation. An executable
recipe adds versioned binding changes, preserved input/configuration, metrics,
candidate generation and call/time budgets. Explanatory playbooks need not be
executable; their status must be explicit.

A plan pins baseline, schema, recipe and API versions. Execution preserves
conditions outside the named bindings, records child jobs, and reports partial
failure. Comparing candidates does not establish global optimality. Changed
weights require comparison through common business metrics or a fixed evaluator;
weighted objective values with different definitions are not directly ranked.

This extension does not prescribe charts, UI or a Studio-specific workflow.
The executable runtime and conformance are tracked by FMT06. This draft
descriptor is not evidence that an authored recipe has executed.

## Implemented draft recipe forms

`independent_variations` changes each named binding from the same baseline.
`grid` evaluates a bounded Cartesian product. Both include the baseline, remove
identical requests, validate every candidate, and enforce declared preserved
pointers. Selection uses existing entity IDs; it cannot fabricate or duplicate
entities. Other recipe kinds require a versioned extension and are rejected by
this runtime. These two finite forms do not claim support for arbitrary workflow
scripts, adaptive search or application business processes.

Planning performs no solve. It records exact requests, descriptor and recipe
fingerprints, metrics and call/time/concurrency limits. Running a stored plan
requires its fingerprint, checks for drift, and creates real native child jobs.
Plans and child IDs persist in a single-host SQLite store. Stable submission keys
recover a lost acknowledgement; failed or uncertain calculations are not retried.
Time budgets stop new submissions and terminate supported local processes;
shutdown may use the runner's bounded termination grace. External execution is
reported uncertain until its connector reconciles it.

`comparison_basis: invariant` explicitly declares that a metric retains its
meaning across configuration changes. The default `same_configuration` prevents
ranking changed weights by their differently weighted objective. A ranking metric
must be selected explicitly from the playbook's metrics. Otherwise the report is
a comparison table. Null, failed, unknown and failed-checker outcomes are not
ranked. Reports retain every candidate and describe any best result as the best
completed eligible candidate, never a global optimum or universally best weight.
