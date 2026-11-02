# Preparation and explanation evidence candidate

Version: `0.5.0`, local opt-in experiment, 2026-11-02. This is an additive
binding/implementation proposal, not a revision of Core 0.1 or native v1.
The existing eight tools and optional ninth verification tool remain usable.

## Revision 0.5.0: explicitly registered domain evidence

Worker preparation and detail generation now use the same registration API as
external domains. An independently installed budget evidence package supplies
identity preparation and item-level credit/benefit details through the existing
MCP tools. Each detail result is checked separately and bound to input/result
hashes. Context advertises the selected handler's requirement schema; an
unregistered profile keeps identity preparation and generic checked results.

Registrations match profile/version and evidence feature version. The service
freezes registrations, isolates callback inputs, checks returned proof hashes,
and links preparation reuse to handler metadata and the catalog hash. Invalid
reports, changed catalogs and changed identity inputs fail. Existing worker
details retain their compatibility field. The local CLI now checks the selected
worker context, rather than expecting worker requirements at the domain index.
See [extension authoring and the installed example](NATIVE_EVIDENCE_EXTENSIONS.md).

The 0.3.0/0.4.0 model comparison uses separate pinned installations and is not
changed by this source revision. It has 48 planned sessions and no execution
approval yet. This revision does not implement natural-language requirement
tracking or a remote MCP service.

## Revision 0.4.0: input policy, intrinsic rules and comparison inputs

The completed 0.3.0 multi-domain trial retained correct mathematical results,
but four final explanations misstated rejection behavior, constraint scope or
accepted baseline inputs. This revision adds structured guidance without new
tools, solve behavior, Core/native contract changes or catalog changes:

- `input_policy` states that invalid requests are rejected before job creation.
  Closed-object locations are schema JSON Pointers for `additionalProperties:
  false` declarations, not an exhaustive validator or request field paths.
  Dynamic maps and extension schemas retain their own rules. The provider's
  actual validation response determines acceptance; evidence submit rechecks it.
- `constraint_scope` separates the default configuration selection, advertised
  constraint records and a partial intrinsic-rule summary. A schema `const`
  selection is fixed, not a menu of optional switches. Built-in summaries require
  matching profile version, input/solution schemas and profile semantics.
  Custom or drifted profiles return `NOT_SUMMARIZED`, not “no intrinsic rules.”
- `comparison_inputs` describes complete problem requests and stored job IDs.
  Submit/explain do not accept a supplied assignment as an evaluated baseline.
  A new problem is reoptimized. The guidance also appears when explain lacks a
  baseline, while the difference remains null. Other OCP bindings may support
  direct solution evaluation; this restriction is scoped to these MCP tools.

The optional evidence feature has its own version. Earlier installations and
model transcripts remain pinned; the existing 8/9-tool modes remain unchanged.
New implementation checks are recorded separately from the prior model trial.
A new host trial is needed to measure whether 0.4.0 improves final prose.

## Purpose and acceptance criteria

The first host experiments exposed correct solver results followed by incorrect
alternative costs, and requests whose meaning changed during preparation.
This candidate connects a declared source request, structured requirements,
the exact submitted request, and checked explanation facts. The server does
not parse natural language or certify that the host captured every user need.

Before implementation, the local acceptance criteria are:

1. Preparing an input never submits a job. Keep the source text verbatim as
   unverified context and hash the original request, requirements and output.
2. Unknown requirements, unsupported combinations, invalid input, or a wrong
   profile version fail without returning a reduced ready-to-submit request.
3. Two bounded worker mappings preserve all feasible assignments and their
   costs, checked independently by finite enumeration: hard fixed breaks and
   soft cost per minute outside availability. Workload remains hard.
4. Explain only stored, tenant/domain-scoped terminal jobs. A supplied
   preparation ID must match the exact stored request. Re-run the checker;
   suppress explanation facts on failed/incomplete verification.
5. Alternative costs and comparisons require separate stored results. Compare
   only matching profile versions, execution profiles, configuration, metric
   definitions and units; preserve null and real zero.
6. Verify an actual installed MCP consumer end to end, as well as the legacy
   tool schemas/catalogs and malformed/tampered/expired/cross-tenant cases.

## Initial bounded mappings

Only `worker.scheduling@0.1.0` fixed-time inputs are mapped. At most one
requirement is accepted per record; combinations require a separate versioned
implementation and checker. An empty requirement list preserves any supported
domain request byte-for-value in JSON.

- `fixed_breaks`, hard: remove worker/task eligibility pairs overlapping a
  declared break, including their cost entry. Keep availability, workload,
  task coverage and original times. Half-open intervals may touch. This avoids
  the zero/eight-window limitation of splitting availability intervals.
- `outside_availability_cost`, soft: for explicitly rated workers, add the
  original task's minutes outside original availability times the declared
  integer rate to its pair cost, and relax availability within the existing
  time horizon. Keep eligibility, non-overlap, workload and times unchanged.
  Unrated workers retain hard availability. Rates use cost units per minute.

The checker evaluates the original requirement directly, separately from the
mapping algorithm, over at most 4^8 assignments. It validates both profile
inputs and all unchanged request fields. This proves equivalence for that
finite input; it does not verify natural-language interpretation.

## Application boundary

Preparation records belong to one server process and tenant/domain. They are
bounded in memory and do not change job storage, submit signatures, or engine
contracts. Ordinary submits remain available. Without a matching preparation,
explanation scope is the submitted problem only. This is traceability, not a
policy that forces every host to use a particular conversation flow.

An explanation contains structured checked facts, not generated prose. It
cannot stop a host from adding unsupported sentences. A difference between two
checked objectives is arithmetic across the two recorded scenarios, not a
causal savings claim. Model-host behavior requires a subsequent separate test.

The local implementation checks and model-host evaluation are separate scopes.
The separately approved comparison below did not change user server registration
or publish the candidate.

## Paired Claude Code pilot, 2026-11-01

Completed 24 explicitly approved fresh sessions on Claude Code 2.1.309 with
`claude-sonnet-5-5`: six synthetic worker tasks, two repetitions per mode, using
the same installed runtime with nine tools or eleven. Order was reversed in
the second repetition. Runtime, prompts and execution controls stayed pinned.
No session was rerun; all completed within the 180-second and USD 0.20 settings.
The new phase's total CLI API-equivalent cost was USD 1.9796254, below USD 5.
This does not measure incremental subscription billing.

| Measure | Nine tools | Eleven tools |
| --- | ---: | ---: |
| Calculation tasks completed with correct results | 8/8 | 8/8 |
| Missing/unsupported tasks clarified without submission | 4/4 | 4/4 |
| Final calculation answers without numerical/scope errors | 7/8 | 7/8 |
| Transformation tasks using prepare and explain | Not available | 4/4 |
| Ready preparations exactly submitted and linked to explanation | Not available | 6/6 |
| CLI API-equivalent cost | USD 0.8398421 | USD 1.1397833 |
| Mean session time | 23.768 seconds | 28.060 seconds |

All submitted transformations preserved the original finite assignment set and
costs under a separate standard-library enumeration. Final prose was reviewed
by the agent, not an external human participant. One baseline answer added an
incorrect alternative-cost explanation; one candidate answer attributed an
all-constraints feasible count to the break alone. The main solutions were
correct in both cases. These errors differ in severity; the strict score includes
both and is not a general failure-rate estimate.

The candidate supplied traceable preparation records but did not demonstrate
higher explanation accuracy in this small sample. It cost about 35.7% more in
CLI-equivalent terms. In the four normal/infeasible candidate sessions the host
used existing verification instead of explain. Both break sessions initially
sent a bare domain input to prepare, then corrected the full request envelope.
Missing-input diagnostics also caused redundant calls. Some calls failed within
a session; this is distinct from rerunning a session.

Prioritize clearer request schemas and field-level preparation diagnostics,
checked per-assignment facts and explicit count scopes, and less redundant
context/verification. Keep this version as an opt-in candidate while evaluating
those improvements. The local execution record is
`.harness/work/claude-evidence-comparison-20261101/REVIEW.md`; its raw transcripts,
reviews, counterexamples and integrity hashes remain local. This pilot does not
complete the 20-by-3 plan, another host/domain, or real-user acceptance.

## Revision 0.3.0: scope, validation receipts and explanation sources

Version 0.3.0 addresses the three remaining observations from the completed
0.1.0/0.2.0 comparison below. Its changes apply when `--evidence` is enabled:

- `context.evidence.capability_scope` separates all configured domains from
  the selected domain/profile and its catalog. Direct engine support comes
  from that catalog; optional preparation mappings are a separate capability.
  A custom profile can use identity preparation and its own checker without
  supporting the worker mappings.
- `submit.input_validation` records a fresh provider validation of the exact
  request before submission. Invalid requests return field diagnostics without
  creating a job. Request, catalog and validation hashes identify the check.
  `explicit_validate_observed` separately reports a retained, matching host
  validate call; preparation's internal checks do not count as that call.
- `explain.explanation_basis` identifies the current and optional baseline
  jobs with the request/result hashes and verification statuses. Without a
  baseline job, `comparison` is `UNAVAILABLE`, its difference is null, and its
  reason is `BASELINE_NOT_PROVIDED`. Additional prose stays `NOT_CHECKED`.

Validation receipts are scoped by tenant/domain/job and checked against the
stored request when explaining. `SUBMIT_PRECHECK` means the binding checked the
input without a retained explicit host call; `EXPLICIT_VALIDATE_THEN_SUBMIT`
records both. Provider validation checks input acceptance, while the independent
result checker verifies the stored solution; neither establishes that every
user requirement was captured. The binding does not add an automatic retry.

Replaying a job retains its original receipt. If that receipt is absent, the
new request check is `REPLAY_CHECK_ONLY` with
`checked_before_original_submit=false`. An explanation without a retained
receipt reports `NOT_RECORDED`, with unknown history represented as null.
Validation observations and job receipts each retain up to 128 records by
default, evicting the oldest retained entries. A false explicit-observation
flag means no matching observation was retained, not proof the host never
called validate. Receipts live in memory and their hashes detect accidental
record changes; they are not signed execution attestations.

The 8/9-tool interfaces and provider catalogs remain unchanged. The 11-tool
evidence mode gains response metadata and a submit precheck, with no new tool
or Core/native wire-contract revision. The evaluated 0.1.0/0.2.0 installations
and their model-session results remain pinned; those results do not measure
the 0.3.0 host's use of this new metadata.

## Try the installed candidate

The 0.2.0 through 0.4.0 improvements below remain in 0.5.0. They address the pilot's observed
diagnostics and explanation issues within the optional evidence binding. The pinned
0.1.0 installation and all 24 model results remain unchanged; the model scores
above do not describe 0.2.0. The Core/native wire contracts, profile semantics,
and existing 8/9-tool definitions are unchanged.

The prepare tool advertises the full canonical Core request schema. Start with
`catalog.requestTemplate`, replace `input`, and keep its envelope fields. A bare
domain input remains invalid. Preparation errors preserve the original error
code and now include the provider validation's `issues[].fieldPath` and message,
including missing worker costs. Correct that field or ask for its value; do not
discard the envelope or guess a replacement value.

`detail="compact"` omits only the repeated `original_problem` and `source_text`
from the returned preparation. The complete record stays on the server; full
and compact requests produce the same preparation ID, submitted problem,
requirements and verification. The default remains `full` for existing callers.

Explanations add `facts.worker_assignment` for the exact supported worker
profile: assignment times, duration and cost; per-worker assigned/remaining
minutes; and the checked total. A linked overtime preparation adds the original
pair cost, outside minutes, rate and increment. Without a link, that original
decomposition is not asserted. Other profiles or results with no solution return
null for this worker-specific field. Failed/incomplete verification still
suppresses all solution facts.

`preparation.mapping_facts` distinguishes every task overlapping a break from
the eligible worker/task pairs removed by that break. Its feasible count covers
**all original constraints plus declared requirements**. A rule-only count is
null with `NOT_COMPUTED`; identity preparation does not enumerate feasibility.
These fields explain checked facts; they do not verify additional model prose.

Build and install with the independent instructions in
[LOCAL_RUNTIME.md](LOCAL_RUNTIME.md). Use a fresh native kit built from this
source; the previously published ZIP does not contain these tools. The installed
CLI accepts `ocp-native config --evidence` and `ocp-native doctor --evidence --probe`.
Evidence implies verification in this CLI; diagnostics check feature versions
and capability scope for every configured reference domain. For the module
entrypoint, enable both flags:

```sh
/absolute/path/to/kit/.native/bin/python -I -B -m ocp_runtime.native_mcp --verification --evidence
```

This exposes 11 tools: the original 8, optional verification, and the two new
tools below. Without `--evidence`, tool schemas and profile catalogs are
unchanged. For an installed custom profile, the same flag works with
`ocp_runtime.native_extension` and its host-selected checker factory.

1. Read `ocp_native_context(domain)` and
   `evidence.requirements_schema`. Fill its original request template.
2. For extra requirements, call `ocp_native_prepare(domain, problem, requirements, source_text, detail="compact")`.
   Keep the returned `preparation_id`, `verification` and `problem`. `READY`
   means preparation succeeded, not that a feasible solution exists.
3. Validate and submit that exact returned problem using the existing tools.
   Retain the idempotency key and job ID; poll to a terminal status.
4. Call `ocp_native_explain(domain, job_id, preparation_id)`. It reads the
   original job record and rechecks the result; it accepts no replacement
   result, free-form assignment or claimed objective from the caller.
5. For a comparison, also pass `baseline_job_id` and, when present,
   `baseline_preparation_id`. The returned difference is current minus
   baseline. An unavailable comparison returns null and a reason.

For a plain supported request, validate and submit directly, then call explain
without a preparation ID. Explain already retrieves and independently checks the
stored solution; separate result/verify/evaluate calls are not required to get
the same explanation. Provider evaluation remains useful when that separate
operation is specifically requested. Reduced response bytes or fewer scripted
calls are not evidence of lower model cost or improved host answer quality.

Example structured requirements (each is a separate preparation):

```json
[{"id":"lunch","kind":"fixed_breaks","enforcement":"hard",
  "breaks":[{"worker_id":"alex","start":600,"end":630}]}]
```

```json
[{"id":"overtime","kind":"outside_availability_cost","enforcement":"soft",
  "worker_rates":{"alex":1},"unit":"cost_unit_per_minute"}]
```

Times use the original problem's minute origin. Overtime rates replace hard
availability only for the named workers; `max_minutes` remains a hard limit.
The mapper returns `PREPARED_INPUT_OUT_OF_SCOPE` when computed pair costs exceed
the profile limit. Unknown rules or combinations return errors without a
reduced request. No rule is silently ignored.

Preparation records are process-local, capped at 128 by default. Repeating the same
preparation is idempotent within the same tenant/domain; caller mutations do
not modify the stored record. Restarting the server loses these records and
the local reference jobs. A preparation ID is a content digest, not a signature
or portable execution certificate.

## Local implementation validation

Evidence 0.5.0 passed 156 checks on a fresh offline macOS arm64 / Python 3.12
installation: 53 base checks, 35 preparation/explanation checks, 15 validation
receipt checks, 7 independent verification checks, 12 guidance checks,
19 registration/installed-extension checks and 15 CLI checks. Final runs had
no failures, errors or skips. The earlier CLI run exposed a worker-only resource
assumption; the corrected diagnostic now inspects selected-domain context.
The failed log is retained separately from the final results.

The budget evidence wheel was installed separately and completed the actual
eleven-tool MCP flow. Legacy 8/9 definitions and catalogs match installed 0.4.0.
The new tests include malformed profiles, reference-free schema registration,
callback mutation, catalog/handler drift, identity preservation and rejected
detail proofs. This is local implementation evidence, not a new host score.
Records: `.harness/work/evidence-extension-20261102/REVIEW.md`.

On 2026-11-02, evidence 0.4.0 passed 137 checks on a new offline macOS arm64 /
Python 3.12 installation: 53 base installation/binding checks, 35 evidence
checks, 15 validation-receipt checks, 7 independent-verification checks,
12 guidance/actual-MCP regressions and 15 CLI checks. No failures, errors or
skips remained in these completed runs. An initial installation attempt lacked
the second offline dependency folder; the fresh retry used the same two folders
as the previous validated installation, without changing dependency versions.

The new tests reproduce rejection of variable-start and quantity-discount
fields, reject supplied solutions as submit input, check mandatory routing
visits and depot costs, and verify exact schema/profile guards for intrinsic
summaries. The installed budget extension still completes its own solve/check
flow with `NOT_SUMMARIZED` intrinsic rules. Existing 8/9-tool definitions and
catalogs match the prior installed 0.3.0 candidate; checked two-job comparison
still works. Prior trial inputs, runtime and raw results are unchanged.
Local records: `.harness/work/evidence-behavior-20261102/REVIEW.md`.
These checks made no model calls and do not establish improved host prose.

Earlier on 2026-11-02, the 0.3.0 CLI integration passed a separate fresh installation with
53 base checks, 15 CLI checks and 3 new multi-domain packet checks. The latter
used actual MCP for seven computation scenarios and six invalid inputs. The
four evidence runtime modules in that installation remained byte-identical to the 110-check checkpoint
below; those 110 tests are historical results, not added to the fresh count.
The new 12-task model packet subsequently completed 24 separately approved
Claude Code/Sonnet sessions. Correct calculations were 12/12 and no-submit
clarification 12/12, while strict final explanation/next-action review passed
20/24. The four findings concern rejection policy, intrinsic constraints and
baseline submission shape; the fixed candidate was not changed during the trial.
See [host acceptance](HOST_INTERFACE_ACCEPTANCE.md) for criteria and scope.

The previous 0.3.0 candidate passed 110 checks after a fresh offline macOS /
Python 3.12 installation: 53 installation/binding regressions, 35 evidence
checks (including five installed MCP tests), 15 input-validation receipt
regressions and 7 independent-verification regressions. There were no failures,
errors or skips in the final runs. This includes all three reference domains,
a separately installed budget profile and prior 0.2.0 8/9-tool compatibility.
Actual MCP tests cover omitted explicit validate, rejection before job creation,
replay preserving the original receipt, and explanation source hashes.
Unit tests additionally cover tenant/domain/catalog/request isolation, drift,
tampering, malformed responses, uncertain submission and bounded eviction.

The earlier model trials and their runtimes are preserved. These 0.3.0 checks
made no model calls and establish local behavior, not a new model-answer score.
Local evidence is `.harness/work/evidence-grounding-20261101/REVIEW.md`.

The 0.2.0 candidate was built and installed afresh on macOS with Python 3.12
on 2026-11-01. All 92 checks passed: 53 installation/binding regressions,
32 evidence feature and actual MCP checks, and 7 verification regressions,
with no failures or skips. Coverage includes the three reference domains, a
separately installed budget profile, legacy 8/9-tool schemas and catalogs,
field diagnostics, compact preparation and checked explanation facts.

For one fixed-break fixture, canonical JSON response size was 3,801 bytes for
0.1.0 full, 4,173 bytes for 0.2.0 full, and 2,709 bytes for 0.2.0 compact.
Compact retained the exact problem and preparation ID: 28.73% smaller than the
previous full response, or 35.08% smaller than the current full response.
Expanded tool schemas and explanation facts also add bytes. This measurement
does not establish a reduction in model tokens, latency or cost.

These implementation checks made no model calls. The preceding pilot scores
remain results for the unchanged 0.1.0 installation. The versioned follow-up
below separately measures answer quality, completion, calls, latency and cost.

The prepared follow-up compares 0.1.0 and 0.2.0 with eleven tools in both arms,
using the same six synthetic questions and two repetitions per arm (24 new
sessions). Order reverses in the second repetition. Preparation checks confirm
identical Python/dependencies, legacy tool definitions and catalogs. The
reviewer accepts result and explain-only retrieval equally, retains null for
unavailable objectives and counts each submitted job once. Eight execution
controls and ten reviewer regressions passed without model calls. These were
preparation checks, separate from the completed model results below.

## Completed revision comparison, 2026-11-01

After explicit approval, all 24 sessions above completed without retries or
runtime changes. Both versions preserved requirements in 12/12 sessions,
completed 8/8 calculation/infeasibility tasks correctly and clarified without
submission in 4/4 missing/unsupported tasks. Agent review of final calculation
prose passed 6/8 for 0.1.0 and 8/8 for 0.2.0. The two baseline errors concerned
break-overlap scope and the scope of feasible-assignment counts; main solutions
remained correct. Independent enumeration checked original/submitted semantics.

Tool calls fell from 88 to 63, average time from 29.34 to 24.34 seconds and CLI
API-equivalent cost from USD 1.1155214 to USD 0.9649370 (13.5% lower). Total
cost was USD 2.0804584, not actual subscription billing. Candidate compact was
used in all four transformation sessions; all four ready records matched exact
submissions and explanations. The baseline also linked all six of its records.

Remaining observations include one overbroad catalog claim in a clarification,
a correct but unexecuted baseline counterfactual, and explicit validate being
called before 9/10 candidate submissions instead of 10/10. These do not change
the verified mathematical results, but constrain claims about explanation
grounding and workflow compliance. Cache use, added schemas and response facts
also affect cost; this small paired sample is not general accuracy, statistical
superiority, another host's acceptance or external-user adoption evidence.

## Reproduce the feature tests

After `tools/check_native_candidate.py` installs the fresh candidate, copy
`tests/runtime/test_native_evidence.py`, `tests/runtime/test_native_evidence_validation.py`,
`tests/runtime/test_native_verification.py`, `tests/runtime/test_native_evidence_guidance.py`,
`tests/runtime/test_native_evidence_registry.py`,
`tools/native_tests/inputs.json`, `examples/native/budget-input.json`, and
`cases/host-interface/evidence-regressions.json` into a new scratch directory.
Install all four budget example wheels (including evidence) from the same kit into that environment
using `pip install --no-index --no-deps --no-compile`. Run the five copied test
files with that environment's Python using `-I -B`, outside this checkout.

To also compare an earlier installed candidate, set
`OCP_TEST_BASELINE_PYTHON` to its Python executable when running
`test_native_evidence.py`. The report distinguishes that comparison from the
current candidate's 8/9/11-tool mode checks. Tests write their JSON evidence in
the scratch directory. Seeded fixtures and injected invalid results are local
regressions; they are not new model-host acceptance runs.
