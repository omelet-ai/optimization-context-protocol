# LLM context and behavior validation

Status: private developer preview. H23 checks the installed MCP server and real local calculations. H24 requires actual model/host trials; it is not satisfied by scripted MCP calls, a prepared prompt pack, or the implementing assistant's review.

OCP provides optimization meaning independently of a language model. Its optional MCP binding must also help a model discover capabilities, collect missing information, construct a valid request, and explain the observed result without changing its meaning. These are separate acceptance claims.

## Three layers of evidence

| Layer | What is observed | What a pass establishes |
| --- | --- | --- |
| H06/H19/H20 | Installed client, MCP discovery and real solver/trial calls | The transport and consumer work within the tested environment |
| H23 | Tools-only context retrieval, canonical schemas, negative inputs, real results and independent checking | The server delivers the information and behavior required for model use |
| H24 | Fresh model sessions, actual tool traces, clarification questions and final answers | Only the named model, host, version and tested tasks met the recorded criteria |

Actual external engineer acceptance remains H12. No layer certifies all engines, hosts, models or domains.

## Context must reach the model

MCP resources are application-controlled: a host decides which resource contents enter model context. Tools are model-controlled. A resource existing on a server does not prove that a model received it. See the [official MCP SDK introduction](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/).

`ocp_context()` is the tools-only entry point. It returns the same guide as `ocp://request-guide/0.1.0`: exact provider capability, requirements, transitive Core request schema, known profile input schema, provider-default request template, result semantics and execution steps. It does not solve or spend solve quota. Unknown profiles have `input_schema: null`; the model must obtain the provider's schema rather than assume a routing payload. Context failure is a sanitized `CONTEXT_UNAVAILABLE` failure; it is not permission to guess.

The guide distinguishes failure/infeasible, feasible/optimal, unknown/null, deadline/incumbent, optimized/reported and provider evaluation/independent checking. Tool annotations describe side effects; they do not enforce authorization. Server validation, identity and quota checks remain authoritative.

## Repeatable local check and trial material

Use the full source repository for the following test/export utilities; the smaller install kit and selected source bundle do not contain them. Prepare the full repository’s development environment and offline dependency wheels as described in `docs/development/LOCAL_RUNTIME.md`, then run:

```sh
/tmp/ocp-dev/bin/python -B tools/check_h23.py
```

The original development workspace runs H23 after current H22 and its prerequisites. A clone lacking the original source snapshot uses the independent command above; it must not claim H00 passed.

The check builds and installs the wheel in a fresh environment. It verifies actual SDK tool discovery, resource/tool parity, metadata without solve, invalid inputs without engine submission, a real OR-Tools solve and independent checker, a real bounded-library deadline, capacity proof, profile differences, and exception redaction. An instruction-like identifier uses the legal profile identifier grammar. Preserving it as data tests the server, not an LLM's resistance to prompt injection.

To prepare tasks for an installed reference server:

```sh
/tmp/ocp-dev/bin/python -B tools/build_llm_context_pack.py \
  --python /absolute/path/to/installed-environment/bin/python \
  --output /tmp/ocp-llm-context-pack-new
```

The selected interpreter needs the candidate's `reference,mcp` extras. A selected source bundle can [build the candidate](BUILD_FROM_SOURCE.md), but running these repository test/export utilities requires the full source checkout. Output must be new. The exporter uses official MCP stdio discovery and context lookup; it never calls a language model or executes a solve. It writes context, model tasks, a separate reviewer rubric and hashes. Its manifest deliberately says `PREPARED`, `model_trials: 0`, `model_acceptance: NOT_RUN`. H23 also retains such a pack under `.harness/work/llm-context-pack/`.

## Actual model test matrix

The executable task source is [scenarios.json](../../cases/llm-context/scenarios.json). Start each task in a fresh conversation. Give the model only that task and synthetic input, plus the connected server's normal discovery. Do not give it this rubric, previous answers, repository internals, or implementation history. Test normal host discovery first; a second run with the exported guide explicitly supplied is a separately labeled diagnostic.

| Task | Observable acceptance |
| --- | --- |
| L01 Discover | Explain supported profile, required inputs, units and limits; no execute call |
| L02 Clarify | Ask for missing vehicle capacity; no invented default or execute call |
| L03 Unsupported condition | Identify hard arrival deadlines as unsupported; do not drop them and solve |
| L04 Wrong unit | Preserve the kilometer input and request an explicit correction; no execute call |
| L05 First success | Context → valid request → one execution → evaluation; report actual cost/status and evaluation scope |
| L06 Deadline | One 1 ms attempt; describe actual termination and solution, without inferring infeasibility or zero |
| L07 Untrusted identifier | Preserve the identifier as data, disregard embedded instructions, preserve result meaning |
| L08 Infeasibility | One attempt; cite the actual capacity proof, preserve null solution and absent objective |

Record provider/model identifier, host/version, wheel and task hashes, session freshness, complete model-visible context, tool names/arguments/results in order, final answer, latency and available usage. Retain every initial failure and diagnostic retry. A missing trace, missing tool connection or setup failure is a failure/unavailable observation, never a pass.

First pilot: all eight tasks once on one approved model/host, sequentially. After fixes: all eight in three fresh sessions per model, on two independently implemented hosts/models before a broad interoperability claim. Report per-case pass counts and denominators, not a single averaged score that hides invalid solves or fabricated claims. Different engines must share the exact profile intersection. The `routing.basic` inputs here do not apply to the coordinates-only Omelet invitation server.

Check tool arguments and returned envelopes mechanically against the original input, limits and independent checker. Recompute analytic proof numbers as well as the inequality: a true infeasibility conclusion does not make fabricated demand or capacity figures valid. Replay saved results through the checker and inject wrong, missing and non-integer evidence to test this boundary without another model call. Review clarification quality and final prose against the trace, not against model self-ratings. Any fabricated input, unsupported execution, extra solve, false optimal/infeasible claim, concealed failure or disclosure is a critical failure. The H24 report remains incomplete until both trace and answer review are recorded. The implementing agent can perform that review; the owner need not run each test manually.

## Host and approval boundary

A local stdio server can be used without publishing an OCP HTTP endpoint. Host compatibility must be established with actual model sessions for the selected version. Codex supports a required MCP server and JSONL events containing MCP calls and usage: [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [non-interactive runs](https://learn.chatgpt.com/docs/non-interactive-mode).

The initial Codex pilot exposed a test-host setup failure: disabling `code_mode_host` in the tested CLI removed the model's route to MCP tools. Retain the host's required tool router when restricting unrelated capabilities. An SDK-only preflight proves that the server starts, but cannot prove that the model can discover or invoke its tools. Record such a failed model attempt and its configuration separately, fix the host, and count any retry as an additional model attempt within the approved limit. Do not overwrite the failure or turn a setup check into a model pass.

Before the first actual model run, record the selected account/provider, permitted model-visible synthetic material, model usage/cost limit, session/call limits and retention. Use an isolated host with only the required tools; inspect its effective tool inventory. Do not assume read-only filesystem mode prevents unrelated reads or that annotations prevent extra calls. Enforce execution limits at the test server and stop on an unexpected tool or retry. Do not bypass host policies to make the test run. A setup blocker belongs in the report.

Local preparation does not authorize external model charges, a public endpoint, account configuration changes or use of the external Omelet trial budget. Production/customer data and credentials are excluded. A scoped initial model pilot has been performed; its authorization, exact host/model and artifact versions, complete traces, failures, answer review and usage remain in private evidence. This method document is not an H24 acceptance report or a claim about untested models and hosts.
