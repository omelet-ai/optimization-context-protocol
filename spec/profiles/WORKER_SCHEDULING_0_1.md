# worker.scheduling 0.1.0

Status: public developer preview contract, not a stable standard. Additive profile; Core 0.1.0 and assignment.fixture are unchanged.

A fixed-time assignment problem, not shift generation. Input limits: 1–8 tasks,
1–4 workers. Time is an integer minute offset from the same planning origin,
0–10080; no timezone or calendar interpretation. Every interval is half-open
[start, end), start < end. Adjacent tasks may share a worker. Availability
intervals must not overlap; a task must fit wholly inside one interval.

Every task must be assigned exactly once to a known eligible worker. A worker
may perform several non-overlapping tasks; their summed duration must be <=
max_minutes. Worker/task IDs are unique within their respective collections.
Each task's costs keys must exactly equal eligible_workers, whose IDs must exist.
An empty eligible set is valid data that can make the problem infeasible.

Minimize sum of the selected task-worker costs (nonnegative integer cost_unit,
<=100000 per pair). All five constraints in the configuration schema are hard.
No weights other than 1, preferences, overtime, breaks, travel or implicit
constraint relaxation. Missing inputs and wrong units are validation failures.

The solution is an unordered assignments list. The total_cost metric uses
worker.scheduling.total_cost.v1, cost_unit. Constraint definitions use
worker.scheduling.<id>.v1, count, violations counted per offending assignment,
overlapping task pair, or over-limit worker. All are enforced and evaluated.

Reference search budget: 1–5000 ms, measured with a monotonic clock. A deadline
returns feasible with an incumbent or unknown without one, termination=time_limit.
Completed search may claim optimal/infeasible with proof method
bounded-assignment-enumeration, scope=worker.scheduling:0.1.0, evidence containing
exactly objective (integer optimum or null for infeasible). The independent
checker enumerates the <=4^8 assignments itself and checks the proof and cost.
A feasible witness alone does not prove optimality. No result is engine certification.
