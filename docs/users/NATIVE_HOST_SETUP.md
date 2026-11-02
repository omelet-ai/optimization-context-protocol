# Connect an installed OCP server to a local MCP host

This guide accompanies **v0.2.0-preview.1**, with the
`ocp-native` command. The immutable `v0.1.1-preview.1` ZIP does not contain this
CLI. Use that ZIP's own README and `mcp_config.py`, or build a new candidate.
No PyPI package or `uvx` command is being published by this change.

For the first routing-focused delivery, start with `NATIVE_ROUTING_QUICKSTART.md`
in the source user guides, or `ROUTING_START_HERE.md` inside a kit.
Use `--domain routing-basic` consistently with `serve`, `config`
and `doctor` to expose only that domain. Omit it to retain the existing three-domain
reference. Selection is server configuration, not a change to the OCP contract.

## Check the installation

From a newly built kit, after `python3.12 -B install.py` succeeds:

```sh
.native/bin/ocp-native --version
.native/bin/ocp-native doctor --evidence
.native/bin/ocp-native doctor --evidence --probe
.native/bin/ocp-native config --evidence
```

`--evidence` selects preparation, checked explanations and independent
verification together. It is supported by `serve`, `config`, `doctor` and the
kit's `mcp_config.py --evidence` wrapper. The generated server command includes
both `--verification` and `--evidence`; existing host settings are not edited.

`doctor` reports the interpreter, package versions, selected features and their
versions, wire contracts and profile versions separately. `--version` remains
the installed package version, not the evidence-feature version.
`--probe` also starts a temporary server, connects over stdio and
reads the tools and all advertised catalogs. It submits no jobs and calls no
model. A passing probe checks this local connection; a host conversation and a
real solve are separate steps. Use `demo.py` to check the supplied solve examples.

Expect eleven tools with `--evidence`, nine with `--verification` alone, and
eight with neither flag. Discovery checks the selected feature versions and
domain scope as well as tool names. Provider evaluation remains separate from
independent verification. Existing eight/nine-tool configurations keep working.
Without `--probe`, `probe.status` is `NOT_RUN` even when the environment passes.
`--timeout 30` sets the probe deadline in seconds; valid values are 1–120.

The equivalent module command works without adding the environment to PATH:

```sh
.native/bin/python -I -B -m ocp_runtime.native_cli doctor --evidence --probe
```

`config` prints JSON with the installed Python's absolute path and arguments.
It does not edit host settings. `--name my-optimization` changes the generated
server name. The existing `mcp_config.py` wrapper produces the same default
configuration. Keep the installation in a permanent directory outside the
source checkout; install into a new directory for upgrades rather than moving
an existing virtual environment.

## Codex and local desktop MCP configuration

In a desktop environment with local MCP settings, open Settings → MCP servers,
add a STDIO server, and enter the command and arguments from `config`. Save and
restart the server; inspect `/mcp` before trying a prompt. Local desktop, CLI
and IDE configuration sharing is described in the
[official OpenAI MCP guide](https://learn.chatgpt.com/docs/extend/mcp).

If the Codex CLI is available, the same registration can be made from the kit
directory with these commands. They change the named server's configuration:

```sh
OCP_PYTHON="$(.native/bin/python -I -B -c 'import sys; print(sys.executable)')"
codex mcp add ocp-native-local -- "$OCP_PYTHON" -I -B -m ocp_runtime.native_mcp --verification --evidence
codex mcp get ocp-native-local
```

The official guide distinguishes locally configured MCP servers from ChatGPT
web plugins. A remote MCP endpoint alone does not establish web-plugin support.
This release prepares the local stdio path; it does not provide a hosted endpoint.

Record the exact surface used for testing. A successful Codex desktop tool call
does not establish a result for every ChatGPT mode or the web client. A process
already running in a conversation can retain its old installation until it
reconnects.

## Claude Code

After installing Claude Code through its official setup instructions, run from
the kit directory:

```sh
OCP_PYTHON="$(.native/bin/python -I -B -c 'import sys; print(sys.executable)')"
claude mcp add --transport stdio --scope user ocp-native-local -- "$OCP_PYTHON" -I -B -m ocp_runtime.native_mcp --verification --evidence
claude mcp get ocp-native-local
```

User scope keeps this personal connection outside a repository's shared
configuration. In Claude Code, use `/mcp` to inspect connectivity. These commands
follow the [official Claude Code MCP guide](https://code.claude.com/docs/en/mcp);
registration and a successful model task should be recorded separately.

## First host interaction

Start with a question that needs no computation:

> Use OCP to list the supported optimization domains and the data each needs.
> Do not solve anything yet.

Then supply one of the kit's input JSON files and ask the host to select its
exact domain, resolve requirements, validate, solve, retrieve the result and
independently verify it. If data is missing, supply it after the host asks.
If a required rule is unsupported, choose a supporting profile or engine.

With evidence enabled, use `ocp_native_explain` after completion to retrieve
the solution and independent checks together. It identifies the exact job and
input/result hashes. A comparison needs a second completed job; an absent
baseline stays unavailable. For supported additional requirements, use
`ocp_native_prepare`, then validate and submit its returned problem unchanged.
Preparation mappings are optional and profile-specific; the selected catalog
describes direct engine support. Submit rechecks input and separately records
whether a matching explicit validate call was observed. The detailed source
guide is `docs/development/NATIVE_EVIDENCE_CANDIDATE.md`.

The 0.4.0 evidence candidate also provides `input_policy`, `constraint_scope`
and `comparison_inputs` in context. Fields disallowed by the selected schema
are rejected, not silently ignored. Configuration entries are distinct from
intrinsic profile rules: routing, for example, requires all visits exactly once
and closed depot routes in addition to vehicle capacity.

For comparisons, give `explain` two completed job IDs. To create a baseline job,
supply a complete baseline problem and validate/solve it first. An existing
assignment alone cannot be submitted as a problem; submitting a new problem
reoptimizes it and does not evaluate that supplied assignment. This input limit
belongs to these MCP tools, not to every OCP binding.

Source-built evidence 0.5.0 candidates additionally support explicitly installed
domain evidence handlers. The kit's `EVIDENCE_EXTENSION.md` shows a separate
budget package supplying checked item-level explanations through the same tools.

For a developer host, the same request/result flow can be used in an existing
application. Keep `jobId`, the original idempotency key, null values, terminal
states and the verification scope when displaying or storing results.

## Troubleshooting

| Diagnostic | Next step |
| --- | --- |
| `PYTHON_3_12_REQUIRED` | Install the reviewed kit with Python 3.12 and use that environment's executable. |
| `MISSING_DEPENDENCY` / `DEPENDENCY_IMPORT_FAILED` | Read the named package; reinstall the complete reviewed kit into a fresh environment. |
| Missing checker with `--verification` or `--evidence` | Install the kit's independent checker, or use the eight-tool connection when verification is not needed. |
| `MCP_PROBE_TIMEOUT` | Inspect server stderr and local resource limits. Correct the cause before retrying. |
| `MCP_PROBE_FAILED` | Check that localhost process/socket access is allowed and review server stderr. |
| `MCP_TOOL_MISMATCH` / `MCP_CONTEXT_INVALID` | Check that the SDK, reference profiles and contract packages came from a matching kit. |
| `MCP_FEATURE_MISMATCH` | Reconnect to the matching installation; the server's selected features, versions or domain scope differ from the requested mode. |
| Host still shows old tools or errors | Confirm its configured absolute path and restart/reconnect that MCP server. |

The console `serve` command starts the same local stdio binding. An apparently
idle terminal is expected because it is waiting for an MCP client. Use `doctor
--probe` for a human-readable startup check. Keep stdout available for protocol
traffic; diagnostics go to stderr.
