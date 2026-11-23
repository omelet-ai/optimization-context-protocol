# Routing content

This complete example keeps the API contract, actual OR-Tools implementation,
official file converters, independent checker and executable playbooks inside
`content/`. The generic template and runtime do not contain routing fields.

The profile is **routing.matrix.weighted 1.0.0-draft.1**, distinct from the older
`routing.basic` profile. It supports up to 64 mandatory visits and 16 heterogeneous
vehicles, integer kg capacity, a directed integer-metre matrix, depot return,
weighted distance and active vehicle cost. Time windows, service times, driver
hours, multi-depot operation and road lookup are outside this example's profile.
These are example limits, not limits of the generic OCP format.

## Input and use

Use `examples/matrix/input.json` directly, or prepare the `.csv` files or
`routing.xlsx` in that directory. Its official format IDs are
`routing-matrix-csv` / `routing-matrix-xlsx`, version `1.0.0`.

`examples/coordinates/` accepts explicitly supplied latitude/longitude. The
converter uses a sphere of radius 6371008.8 metres and rounds half up to integer
metres. It preserves the coordinates and derivations, and verifies the generated
matrix against that declared formula. This is not a road-distance or address
geocoding service. Corresponding format IDs are `routing-coordinates-csv` /
`routing-coordinates-xlsx`, version `1.0.0`. Workbook `_ocp` metadata identifies
the format. Unknown columns, missing pairs and unsupported versions are errors.

An MCP client uses `ocp_context`, `ocp_describe`, `ocp_prepare`, `ocp_validate`,
`ocp_submit`, `ocp_job`, `ocp_result` and `ocp_evaluate`. Upload file bytes through
`ocp_artifact`, or explicitly allow a local data directory for stdio. Preparation
does not consume solver time. Customer-specific file mappings belong to the
application that produces these official inputs.

Use `configuration.example.json` as a local configuration guide; set its private
state directory. The local library connector requires no account, key or endpoint.
Install the reviewed generic runtime wheel with its `[server]` dependencies and
this Routing wheel, whose metadata declares OR-Tools. The generic runtime carries
its worker contract: this local example needs no legacy native-contract package,
key or internal catalog. Use the generated project's `check`, `doctor` and
`host-config` commands before connecting an MCP host. The source-tree quickstart
in the top-level README builds and installs these exact local candidates; neither
package is a published PyPI release.

For a configured stdio host, send `ocp_context`, inspect this API with
`ocp_describe`, then validate the supplied synthetic matrix input with
`ocp_validate`. Submit that validated request with `ocp_submit`, inspect
`ocp_job` until terminal, and retrieve `ocp_result`; use `ocp_evaluate` to inspect
the independent checker result. File preparation uses `ocp_artifact` and
`ocp_prepare`; allowed local directories are opt-in. Host-specific setup and
user acceptance are separate from the local install and doctor checks.

## Analysis and interpretation

Four executable playbooks compare actual vehicle sets, vehicle penalties,
objective settings and solver time budgets. Call `ocp_plan`, inspect its requests
and budget, then `ocp_run`, `ocp_analysis` and `ocp_compare`. Fleet defaults use the
bundled synthetic IDs `van_a`, `van_b`, `truck`; supply explicit existing-ID sets
for other inputs. Ranking is optional and must name a fixed metric. Across weight
changes, compare raw distance and vehicle count; differently weighted objective
scores are not comparable rankings. No universally best weight is claimed.

The solver reports feasible heuristic solutions. Only simple capacity bounds or
the empty problem carry explicit infeasibility/optimality evidence. A search
timeout without a solution is unknown. The independent checker recomputes visit
coverage, fleet uniqueness, loads, matrix distances and weighted arithmetic. It
does not prove global optimality, validate business requirements omitted from
the request, or certify that a supplied matrix represents actual roads.

## Another API shape

The optional `http_api` module exposes the same real engine through durable
asynchronous jobs on loopback. Set a server-side `OCP_ROUTING_API_TOKEN`, then run
the installed module with `--state /private/computation/path --port 8088`.
Configure the OCP factory with that endpoint and the **name** of a credential
environment variable. It reads API metadata, validates, submits once and polls
the real upstream job. Uncertain submissions retain their upstream key/job ID
for reconciliation and are not retried automatically. Killing the client does
not prove the remote calculation stopped. This demonstrates API connector
interchangeability for one engine; it does not demonstrate two different solvers
or a production Internet deployment.

Applications own visualization, customer data connections and business actions.
