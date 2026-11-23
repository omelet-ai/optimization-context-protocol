# OCP Server format preview

Use an optimization API from an MCP host, or package your own API using the same
template. The public source includes working Routing and cutting-stock examples.
The common runtime handles discovery, official input files,
validation, jobs, independent checks and bounded playbook comparisons.

The [IB-1.2 integration baseline](../development/TEMPLATE_INTEGRATION_BASELINE_IB12.md)
lists the compatible versions. Build the generic template and runtime from public
source. For a new problem type, start with [the cutting-stock walkthrough](../../examples/cutting-stock/README.md).
It shows the solver, descriptor, adapter and independent checker, then follows an order
from a desktop prompt to a saved job. For Native v1 use its [separate ZIP](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.2.0-preview.2).

## Start with the working example

Run the [generic Routing quickstart](../../README.md#build-an-ocp-server-for-your-algorithm)
from the reviewed source checkout. That exact command block builds the runtime and
Routing wheels, installs them into `.quickstart-venv`, checks the API agreement
and writes `.quickstart/host-config.json`. It needs Python 3.12 and no Omelet
account, API key or existing service. The verified platform is macOS arm64;
other platforms and individual host interfaces need their own checks.

Keep that environment active for the commands below:

```sh
. .quickstart-venv/bin/activate
routing-ocp-server check
routing-ocp-server doctor --config "$PWD/.quickstart/local-config.json"
routing-ocp-server host-config --config "$PWD/.quickstart/local-config.json"
```

Add the generated `mcpServers` entry to a host that supports local stdio MCP.
The host launches the installed server. To launch it directly, use
`routing-ocp-server serve --config "$PWD/.quickstart/local-config.json"`;
stdout then carries MCP messages. The example uses local OR-Tools.

## Use the server

1. Ask the host to inspect `ocp_context` and `ocp_describe` for `routing.example`.
2. Supply API JSON, or upload all files from a declared CSV/Excel format using
   `ocp_artifact`, then call `ocp_prepare`. Preparation does not solve.
3. Check missing fields and units, call `ocp_validate`, then `ocp_submit` with a
   stable idempotency key. Poll `ocp_job` and fetch `ocp_result`.
4. Read `solution_status`, `termination_reason`, metrics and checker scope.
5. For comparisons inspect a playbook with `ocp_describe`, call `ocp_plan`, inspect
   exact candidates/budgets, then `ocp_run`, `ocp_analysis` and `ocp_compare`.

The bundled files are installed inside
`ocp_routing_ocp_server/content/examples/{matrix,coordinates}`. They are synthetic.
You can find their location with:

```sh
python -I -B -c 'from importlib.resources import files; print(files("ocp_routing_ocp_server").joinpath("content", "examples"))'
```

The Routing API supports a directed integer-metre matrix, mandatory visits,
integer-kg capacities, depot returns, distance or explicit weighted cost, up to 64
visits and 16 vehicles. Coordinate files compute spherical straight-line distance
using radius 6,371,008.8 metres and half-up integer rounding. They do not supply road
travel times. Time windows and driver shifts are outside this example's profile.
Other APIs can define richer profiles without changing the general format.

### API execution and MCP jobs

The `interpretation.execution` item describes the underlying optimization API.
For this Routing example it is a synchronous call without API-level cancellation.
The MCP binding wraps it in an asynchronous job: submit, poll, read the result,
or request local worker cancellation with `ocp_cancel`. Read `ocp_context.binding`
for that binding's capabilities. SQLite persists job records; it does not promise
uninterrupted computation or automatic resumption. A local cancellation does not
prove that a separately hosted engine stopped.

For CSV or Excel, pass each file's base64 bytes to `ocp_artifact` first. Then map
each declared filename in `ocp_prepare.files` to the complete returned reference
object (`artifact_id`, `sha256`, `media_type`, `size_bytes`). Raw base64 strings
are not artifact references. Canonical JSON goes in `input_value` instead.

To override playbook candidates, `ocp_plan.variables` takes objects such as
`[{"binding": "vehicle_weight", "values": [0, 10000]}]`, using an ID declared by
that playbook. A bare `[0, 10000]` is not a valid variables list. Omitting
`variables` uses the playbook's recipe. Compare raw metrics on a common basis.

## Package your own optimization API

The problem solver supplies the domain content. The common runtime supplies the
server lifecycle and bindings. There is no required routing or scheduling model.

| Author supplies | Where it goes |
| --- | --- |
| API identity/version, input/configuration/result schemas, units, capabilities and result meanings | `content/manifest.json` |
| Local engine or remote API client, selected by a trusted connector factory | `content/adapter.py` and domain modules |
| Official CSV/XLSX definitions, samples and pure conversion to API input, when needed | Manifest `input_formats`, `content/input_files.py`, `content/examples/` |
| Independent result checks, when provided | `content/checker.py` |
| Reusable analyses, such as comparing resource counts or objective weights | Manifest `playbooks` and declared bindings/metrics |
| Content-specific Python dependencies | `content/python-dependencies.json` |

Customer database mapping, customer-specific spreadsheets, visualization and
business actions stay in Studio, Foundry or another consuming application.
An official file converter is part of the server's content: it accepts the
advertised format and produces API input with provenance; it does not solve.

### 1. Create a blank project and author its content

After the generic quickstart, these commands use the installed authoring CLI.
Run them from the repository root, using new output directories:

```sh
python -I -B -m ocp_runtime.authoring init --output ./blank-server --name my-optimizer
cp -R ./blank-server/content ./my-content
```

The blank manifest deliberately has `configured: false`. Fill `my-content/`
using the [package descriptor](../../spec/server-package/README.md),
[official input format](../../spec/input-formats/README.md) and
[playbook](../../spec/playbooks/README.md) specifications. The
[Routing content](../../examples/routing-ocp-server/content/README.md) is a
complete example; replace its schemas and behavior with your API's definitions.
A blank server reports `UNCONFIGURED` and cannot execute a solver.

Keep your editable content in `my-content/`. Generate a new project after each
content change; this keeps the common template and its provenance intact:

```sh
python -I -B -m ocp_runtime.authoring inject --project ./blank-server --content ./my-content --output ./my-server
python -m build --wheel --no-isolation --outdir ./my-wheels ./my-server
python -m pip install --find-links .harness/work/dist ./my-wheels/my_optimizer-0.1.0.dev3-py3-none-any.whl
my-optimizer check
```

`build` uses the build tools installed by the quickstart. `check` validates the
completed descriptor; it does not establish agreement with the live engine.
The generated project has this structure:

```text
my-server/
  server.py                 common entrypoint; keep unchanged
  pyproject.toml            derived package/dependency metadata
  config.example.json       local settings template
  .ocp-generation.json      generated-file provenance
  content/                  all domain code, schemas, playbooks and samples
```

The trusted connector factory accepts the local configuration and returns a
mapping containing `connector`, plus optional `checker` and `converters`.
See the [Routing factory](../../examples/routing-ocp-server/content/adapter.py)
and [connector execution contract](../../runtime/python/ocp_runtime/execution/service.py)
for the actual Python contract. Metadata and uploaded files cannot import code.

### 2. Set the local connection and check it

Create a private local configuration outside `my-server/`:

```sh
cp ./my-server/config.example.json ./my-local-config.json
```

Set `connector_factory` to your installed factory, for example
`ocp_my_optimizer.content.adapter:create_bundle`; set `state_directory` to a
private computation-state directory. A local engine can leave `api_endpoint` and
`credential_environment_variable` as `null`. A remote API uses its endpoint and
the **name** of a credential environment variable; keep the secret value outside
the project. `allowed_local_roots` stays empty unless local file access is needed.
Relative paths resolve beside the configuration file.

```sh
my-optimizer doctor --config "$PWD/my-local-config.json"
my-optimizer host-config --config "$PWD/my-local-config.json"
```

`doctor` must report `READY` with zero execution calls before connecting a host.
It checks metadata/API agreement and registration without solving.
`host-config` emits the installed server's launch configuration. Then use the
same discovery → prepare/validate → submit → job/result → evaluate flow as above.

### 3. Keep content dependencies and template reuse explicit

Declare libraries imported by your content, for example:

```json
{
  "schema": "ocp-python-dependencies/v1",
  "requires-python": ">=3.12",
  "requires": ["ortools==9.15.6755"]
}
```

The generator writes these requirements into the wheel's `Requires-Dist` metadata
alongside the pinned runtime's `server` extra. Use only the libraries your API
needs. `requires-python` can narrow Python 3.12+; direct URL/file requirements and
runtime overrides are rejected. Private wheels can be provided through pip's
`--find-links`; installer credentials remain outside content.

To prove the relationship using the reviewed Routing content:

```sh
python -I -B -m ocp_runtime.authoring init --name routing-ocp-server --content ./examples/routing-ocp-server/content --output ./routing-generated
python -I -B -m ocp_runtime.authoring strip --project ./routing-generated --output ./routing-blank
python -I -B -m ocp_runtime.authoring inject --project ./routing-blank --content ./examples/routing-ocp-server/content --output ./routing-restored
```

`routing-blank` is the empty generic template, with its domain dependencies
removed. Reinjection recreates `routing-generated`, including derived metadata.
All commands write new directories. Strip/inject reject edited or unrecorded
project files; use the separate editable content directory to preserve your work.
Choose the license and notices appropriate to your own API/engine before
sharing it.

Optional stateful queries and commands use the
[operations extension](../../spec/operations/README.md). Enable it only when your
API needs those operations; the basic optimization template does not require it.

## HTTP and application integration

The same tools support authenticated local Streamable HTTP at `/mcp`. Configure
`transport`, `http_port` and `http_auth_environment_variable`; that environment
variable contains a JSON map of bearer token to `{tenant, caller, scopes}`. Scopes
are `read`, `execute`, `cancel`. Run `doctor` before `serve`. A public host such as
ChatGPT may require a separately operated HTTPS service and host-specific auth;
local HTTP tests do not establish that product connection.

Studio's presentation/session adapter and Foundry's gateway/state adapter remain
separate bindings. The common package does not require their UI hooks, tool prefixes
or `ocps1` state format. The existing Native v1 path reuses its pinned public
Capability Contract v1 package; the generic local example carries its own worker
contract and does not require that legacy package. Consumer-specific migrations are verified in
isolated environments, preserving the original Foundry repository.

## Recover and upgrade

Install a newer bundle into a new venv and state directory, run doctor and the
installed suite, then change your host entry. Keep the old entry and venv for
rollback. A failed hash, missing setting, unavailable API or unsupported input
returns an actionable error; it does not switch engines or submit another job.
After uncertain execution retain the existing job ID and key and reconcile it.
Uninstalling a venv is separate from deleting its persisted job state.

The independent checker covers the declared request and its checks, not omitted
business requirements or a proof of optimality. Playbook output identifies the
best completed eligible candidate under an explicit metric; it does not prove a
globally best fleet or weight.
