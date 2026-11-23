# Integrate an OCP Server

**Author one optimization API in `content/`, install its server package, then
connect it to your application or MCP host.** The same contract supplies discovery,
input preparation, validation, jobs and results. Customer data integration,
identity, permissions and visualization remain in the application.

This guide targets the [public source integration baseline](../development/TEMPLATE_INTEGRATION_BASELINE_IB12.md).
Build its runtime and domain package from the same revision. The Native ZIP has a
separate release and installation path.

## 1. Start with the working example or your own API

| Component | Integration candidate |
| --- | --- |
| Python | 3.12; verified locally on macOS arm64 |
| Runtime, template and descriptor | [Pinned versions in IB-1.2](../development/TEMPLATE_INTEGRATION_BASELINE_IB12.md) |
| Routing example | `routing-ocp-server==0.1.0.dev3` |
| Routing API / profile | `routing.matrix.api` / `routing.matrix.weighted`, `1.0.0-draft.1` |
| MCP SDK | `2.3.0` |

Run the [source installation quickstart](../../README.md#build-an-ocp-server-for-your-algorithm)
first. It builds the runtime and Routing package, checks the descriptor and prints
an MCP launch configuration. This generic installation does not require the
legacy native-contract package, an Omelet account or a key.

For your own API, use the installed authoring command in the same environment:

```sh
python -m ocp_runtime.authoring init --name my-optimization-server --output ./my-optimization-server
```

The blank project reports `UNCONFIGURED` until its domain content is supplied.
Use the [complete Routing content](../../examples/routing-ocp-server/content/README.md)
as a structural example, and fill these parts for your API:

| Author supplies | Purpose |
| --- | --- |
| `content/manifest.json` | API/profile versions, input/configuration/result schemas, supported objectives and constraints, units and result meanings. |
| Installed connector factory | Calls the existing engine. Returns `connector`, optional `checker`, `converters` and `operations`; code is selected by trusted local configuration. |
| Official formats and converters | Optional versioned CSV/Excel-to-API conversion, with file provenance and actionable input diagnostics. |
| Playbooks | Optional explanations and bounded recipes for comparisons such as parameter or resource searches. |
| `content/python-dependencies.json` | Optional domain dependencies used when generating the package. Keep engine dependencies in domain content. |

Keep customer ERP/DB mappings and charts outside `content/`. A production Routing
or Nurse API needs its own complete schemas and connector; the public Routing
example does not replace those APIs. See the [descriptor](../../spec/server-package/README.md)
and [official input format](../../spec/input-formats/README.md) contracts.

## 2. Configure and register the installed package

Install the completed authored project into the environment containing the pinned
runtime (`python -m pip install ./my-optimization-server`). Copy the content's
`configuration.example.json` when supplied, otherwise use the deliberately blank
`config.example.json`. In a private configuration file, set:

- `connector_factory`: the installed domain's `module:function`.
- `state_directory`: a private computation-state directory.
- `transport`: `stdio` or `streamable-http`.
- `api_endpoint` and `credential_environment_variable`: only when the connector
  needs them. Supply the actual secret through the named environment variable.
- `allowed_local_roots`: optional, explicit directories for stdio file access;
  supplied bytes and owner-scoped artifacts work without filesystem access.

```sh
my-optimization-server check
my-optimization-server doctor --config /absolute/path/local-config.json
my-optimization-server host-config --config /absolute/path/local-config.json
```

`check` validates content. `doctor` verifies the configured connector's metadata
and reports `READY` without solving. For stdio, add the printed `mcpServers` entry
to your host; it launches `serve` using the installed Python and absolute config.
For Streamable HTTP, start `serve` yourself and register the printed `/mcp` URL.
The supplied HTTP reference binds to loopback and requires
`http_auth_environment_variable` to name its bearer-identity configuration;
`http_port` selects the port. Public HTTPS and the host's authentication integration
are deployment work.

An application's registration associates the server ID, package hash, API/profile
versions and executable or endpoint with its existing workspace and permissions.
There is no required Studio registry, Foundry gateway or endpoint layout in the
common format. Keep the application's existing authentication. The transport
supplies identity; uploaded input and metadata cannot grant permissions.

## 3. Connect the execution flow

The table uses the generic MCP binding's exact tool names. An in-process or API
adapter should preserve the same contract boundaries rather than imitate a
particular host's UI or tool aliases.

| Step | MCP call | Application behavior |
| --- | --- | --- |
| Discover | `ocp_context` → `ocp_describe` | Select an advertised server/API; pass its `expected_digest` when reading exact schemas and capabilities. |
| Prepare files, if needed | `ocp_artifact` → `ocp_prepare` | Supply declared format/version and configuration; show missing or ambiguous input. Direct API JSON can go to validation. |
| Validate | `ocp_validate` | Preserve effective input/configuration and diagnostics. Invalid input is different from mathematical infeasibility. |
| Submit | `ocp_submit` | Submit the selected input/configuration with an `idempotency_key`; retain the returned job ID. |
| Observe | `ocp_job` | Poll the same job. Request cancellation with `ocp_cancel` and observe termination. |
| Read | `ocp_result` | Retain the full outcome, configuration, termination reason and source identifiers. |
| Check and present | `ocp_evaluate` | Read the recorded checker report and its scope; project the domain output into your application's UI. |

Large responses can return an artifact reference; read the complete artifact with
`ocp_read_artifact` and validate its declared size/hash. Do not treat a truncated
preview as the full result. Preserve `null`, `unknown`, reported versus checked
values, and enforced versus evaluated constraints. A completed job does not by
itself mean a feasible or optimal solution. An uncertain remote submission needs
connector reconciliation, not a fresh calculation under a new key.

## 4. Add optional operations and playbooks when needed

An API with query or context-changing commands can declare
[`ocp.operations`](../../spec/operations/README.md) and register trusted
`OperationConnector` implementations. Discover the exact operation reference and
schema, then use its advertised tool. `ocp_prepare_operation` converts its declared
files without invoking the command. The application checks current permission
before effects and preserves the complete operation report, including
`status`, `effect`, optional `completion`, evidence and data/null.

For [executable playbooks](../../spec/playbooks/README.md), use `ocp_plan`, inspect
the candidate requests and budgets, then `ocp_run` with the plan fingerprint.
Read `ocp_analysis` and `ocp_compare`; `ocp_stop_analysis` requests a stop. The
implemented recipe forms are finite `independent_variations` and `grid`.
Application workflows and adaptive searches can use separate versioned extensions.

## Integration acceptance

For a first desktop solve, ask the connected server to submit an order and return
the job ID, layout and independent checks. Read **that ID** using the same local
configuration and compare the two receipts. The [cutting-stock walkthrough](../../examples/cutting-stock/README.md#4-ask-a-desktop-client)
includes the prompt and lookup command. A correct numerical answer alone cannot
show whether the host submitted the order.

Start with one real input-to-result path in an isolated consumer, then add its
other supported features. Record the exact package, engine, input and result
hashes. Check missing/unsupported input, duplicate submission, timeout/cancellation,
permissions and result reopening before replacing an existing registration.
Keep the prior registration and state available for rollback.

| Latest local evidence | Remaining acceptance |
| --- | --- |
| Generic runtime/example: independent build/install, official MCP stdio Routing solve and independent checker; loopback HTTP API exercise. | External host UI, Internet deployment and other platform/package combinations. |
| Cutting stock on macOS: ChatGPT Work/Codex and Claude Desktop each returned a saved job ID when explicitly asked to submit. A separate lookup reproduced two bars and four passing checks. Plain calculation prompts produced no submitted job. | Human-led onboarding, other client editions and remote MCP transports for this example. |
| Studio with IB-1: actual Routing guided execution; Nurse workbook preparation, apply, submit, execution and result; a separate authenticated continuation saved that result, logged in again, reopened it at desktop/mobile sizes and exported identical JSON. | One uninterrupted Nurse execute-to-save journey; complete existing-feature parity, including repair/playbooks; IB-1.2 domain package migration and consumer validation. |
| Foundry: saved-result consumer with actual MCP/ORM and explicit fixture authorization. | Real OIP/OpenFGA/Product DB environment, product authorization and customer-app workflow. |

The last two rows are consumer experiments, not required fields of the template.
They let integration proceed against a fixed format while product acceptance
continues separately. Source publication and remote deployment are separate from
this local integration baseline.

The Nurse execution and archive continuation are two recorded sessions. The
archive session used the closed execution result without rerunning optimization.
Desktop/mobile DOM and exported bytes were checked; full mobile table visual
review and clinical suitability are separate acceptance tasks.
