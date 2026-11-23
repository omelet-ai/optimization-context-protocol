# routing-ocp-server

This project uses the generic OCP Server template. Your optimization API's
schemas, connector, official file formats, checker and optional playbooks live
in `content/`. Customer data integration and visualization belong to the
consuming application. A blank project has no default domain or solver.

## Author and install

Keep editable domain content in a separate directory and generate this project
from it with `python -m ocp_runtime.authoring init --content ...`. After content
changes, generate a new output directory. This preserves the common template
and the `.ocp-generation.json` record used by strip/reinject checks.

Install the reviewed runtime and this package into the same Python environment,
then run:

```sh
routing-ocp-server check
routing-ocp-server describe
```

`check` validates the descriptor; it does not call the engine. A blank descriptor
reports `UNCONFIGURED` until you supply the API contract and connector.

## Configure a local instance

Copy the content's `configuration.example.json`, when supplied, to a private
location outside this project. Otherwise start from `config.example.json`.
The common configuration is deliberately blank: copying it alone does not
configure an engine.

Set these values explicitly:

- `connector_factory`: your installed Python `module:function`. For a factory
  in `content/adapter.py`, this is
  `ocp_routing_ocp_server.content.adapter:create_bundle`.
- `state_directory`: an absolute path to a private directory for job state.
- `transport`: `stdio` for a host that launches a local MCP process.

The factory receives the local configuration and returns `connector`, plus
optional `checker`, `converters` and `operations`. For a local engine,
`api_endpoint` and `credential_environment_variable` can remain `null`.
For a remote engine, supply its endpoint and the **name** of the environment
variable containing its credential. Keep the secret value outside this project.
`allowed_local_roots` can stay empty when supplying file bytes through MCP.

```sh
routing-ocp-server doctor --config /absolute/path/local-config.json
routing-ocp-server host-config --config /absolute/path/local-config.json
```

Expect `doctor` to report `READY` and `execute_calls: 0`. It checks connector
metadata and registration without solving. Add the generated `mcpServers`
entry to a compatible local stdio host. The host launches `serve`; if you run
it directly, stdout carries MCP protocol messages.

For Streamable HTTP, configure the documented bearer-identity setting and
port, then start `serve` yourself. The reference binds to loopback. Public HTTPS
and host-specific authentication require their own deployment setup.

## Optional capabilities and further guidance

Official file conversion and playbooks are domain content. APIs that also need
queries or commands can opt into the versioned `ocp.operations` extension;
its trusted connector registration and authorization are separate from file
preparation. The blank template does not require operations.

Use the matching OCP source delivery for `docs/users/SERVER_FORMAT_PREVIEW.md`
(authoring), `docs/users/SERVER_FORMAT_INTEGRATION.md` (consumer setup), and
`spec/operations/README.md` (optional operations). These paths belong to that
source delivery, not to this generated project.

Template revision: 0.1.0-draft.5. Content stripping writes a separate
copy and verifies the generation record; it never removes the original project.
