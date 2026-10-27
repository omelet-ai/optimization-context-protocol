# inventory.replenishment 0.1.0

Status: private candidate. Additive deterministic finite-horizon order-quantity
profile; distinct from an (s,S) policy and from demand forecasting. Core is unchanged.

Input: 1–4 independent products, 1–6 equal daily periods indexed 0..periods-1,
nonnegative integer items, monetary values in a single cost_unit. Demand is
provided future demand, never inferred from sales history. Each product supplies
all fields in the schema, including zero scheduled receipts where none exist.
All demand/receipt arrays have length periods and product IDs are unique.

At the start of day t, scheduled_receipts[t] and orders[t-lead_time] arrive;
then all demand[t] is served; holding cost is charged on end-of-day inventory.
For lead_time=0 today's order arrives before today's demand. Initial inventory
is immediately before day 0 receipts. Initial inventory and inventory just after
receipts must be <= storage_capacity. No negative inventory, backlog or lost sales.
End inventory[t] = previous inventory + receipts + arriving order - demand.
End inventory[last] >= terminal_min_inventory. Orders arriving outside the horizon
must be zero; previously committed arrivals are explicit scheduled_receipts.

Minimize sum_t(unit_order_cost * orders[t] + fixed_order_cost * (orders[t]>0)
+ holding_cost * ending_inventory[t]). Costs are nonnegative integer cost_unit,
<=100000; max_order_quantity is 0–5 items, inventory capacity <=50. Products have
no shared budgets, storage, substitution or uncertainty. Those require a new
profile/version; these constraints must not be silently accepted.

Solution has exactly one plan per product with orders and ending_inventory arrays.
The total_cost definition is inventory.replenishment.total_cost.v1; constraints
use inventory.replenishment.<id>.v1, count. Count violating product-periods per
constraint (terminal_inventory counts products); balance checks the submitted
trajectory against the exact recurrence. Invalid shape/unknown products reject.

Reference dynamic programming has a 1–5000 ms monotonic budget. A partial product
plan is not a feasible full solution. Deadline => unknown with null solution unless
a complete incumbent exists. Completed proof method=bounded-order-enumeration,
scope=inventory.replenishment:0.1.0, evidence={objective: optimum or null}.
The independent checker enumerates <=6^6 order vectors per product (no solver
imports) to establish optimal/infeasible claims. Empty feasible state space is
infeasible only with this independently verifiable proof. A timeout is never that proof.
