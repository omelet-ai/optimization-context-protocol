# Connect a routing solver to your MCP host

This guide accompanies `v0.2.0-preview.1` (Python package
`0.2.0a1`, evidence feature `0.5.0`). This routing setup is not included
in the published `v0.1.1-preview.1` ZIP. The first delivery connects a local OR-Tools
routing solver through OCP, with independent result checking. No account or key
is needed. OCP's contracts and extension API remain usable for other domains
and engines.

## Install and check

Use Python 3.12 on macOS or Linux. In a fresh extracted candidate directory:

```sh
python3.12 -B install.py
.native/bin/ocp-native doctor --domain routing-basic --evidence --probe
.native/bin/ocp-native config --domain routing-basic --evidence --name ocp-routing
```

The probe should report `PASS`, eleven tools and only `routing-basic` in its
catalogs. It does not solve a problem. Copy the generated command and arguments
into a host that supports local stdio MCP; the command does not change host
settings. See `HOST_SETUP.md` for host-specific instructions.

Without `--domain`, the existing three-domain reference remains available.
Repeat `--domain` to select several distinct built-in domains. Unknown or
duplicate selections fail; a routing-only server rejects other domains.

## Ask what it can solve

> Use OCP to describe the routing inputs, objective and supported rules.
> Do not run the solver yet.

The available profile is `routing.basic@0.1.0`: one depot, 1–64 mandatory visits,
1–16 vehicles, integer kg demands/capacities and an explicit directed integer
meter distance matrix. Each vehicle starts and ends at the depot, makes one
trip, and may remain unused. The objective is total distance, not monetary cost.

Addresses and latitude/longitude are not distance matrices. Supply a matrix
from your application or a separately documented distance service; the host
must not invent distances. Time windows, service times, driver shifts, multiple
depots and optional visits need another supporting profile and solver.

## Solve and understand a result

Supply the bundled `routing-input.json` to your host with this request:

> Keep the supplied distances in meters and capacities in kg. Find routes that
> visit every location once, respect vehicle capacity and return to the depot.
> Validate before submitting. Explain the routes and independently checked total
> distance, and state whether optimality was proved.

The bundled synthetic input has a checked result of 18 meters. `feasible` means
the reported solution satisfies the profile; it is not a general optimality
guarantee. A job marked `succeeded` only says computation finished. For an
infeasible result, inspect the proof; timeout or no incumbent stays `unknown`.

To test the real MCP calculation without an LLM:

```sh
.native/bin/python -I -B mcp_walkthrough.py --domain routing-basic --input routing-input.json
```

This existing walkthrough selects routing requests on the default reference
server. The generated `ocp-routing` configuration above restricts discovery and
execution to routing. A successful walkthrough is separate from a host conversation.

For a comparison, provide a second complete problem with the changed data and
keep both job IDs. The host must validate and solve both and compare checked
results. An arbitrary proposed route is not a new optimization problem to submit.

## Try your own data

First record your mandatory business rules, then check that this profile can
represent them. Match depot/visit IDs to every matrix row and column, retain
units and supply all vehicle capacities. Missing data should produce a question;
unsupported rules should be reported before a reduced problem is attempted.

Use the catalog's request template rather than guessing an envelope. Independent
checking covers the submitted problem and result; compare them with the original
requirements as part of review. Keep customer data out of public issues.

## Delivery status

This is a local developer preview with volatile jobs. Save results you need
before stopping the server. Remote MCP hosting, authentication and recovery are
separate deployment work. The current reference solver is OR-Tools; replacing
it requires an adapter implementing the exact advertised profile and an
independent checker. This is not an assertion that every routing solver accepts
the same problem. Invited users may separately evaluate the Omelet trial.
