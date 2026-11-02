# Host interface acceptance

Use equivalent tasks in a development host and a conversation host. The initial
worker packet and its historical scores remain below. A separate routing,
worker and inventory packet completed its Claude trial on pinned evidence 0.3.0. The target
labels are Claude Code and ChatGPT desktop; record the exact surface actually
used before counting any result for the second host.

The installed `ocp-native` CLI now provides `serve`, `config` and `doctor`.
For the first connection, follow [local host setup](../users/NATIVE_HOST_SETUP.md).
`doctor --evidence --probe` checks eleven-tool stdio discovery without a solve
or model call. `doctor` alone checks imports/resources and reports the probe
as `NOT_RUN`. Keep this diagnostic scope separate from the trials below.

## Candidate behavior

The default entrypoint still exposes eight tools. `--verification` adds
`ocp_native_verify(domain, job_id)`; the CLI's `--evidence` also enables
preparation and explanation, for eleven tools. Verification is version `0.1.0`
and the current local evidence candidate is version `0.5.0`. These feature versions are separate from the
package version, Core 0.1 and native v1 contracts, and domain profile versions.

Version 0.4.0 adds structured rejection policy, configuration/intrinsic-rule
scope and accepted comparison inputs for the four observed 0.3.0 explanation
errors. It passed 137 fresh local checks; no new model trial has been run on
0.4.0. The historical 20/24 strict explanation score stays attached to 0.3.0.

The next paired packet fixes 12 tasks, two versions and two repetitions for
48 fresh Claude Code sessions on 0.3.0/0.4.0. Its execution-control, reviewer and
actual-MCP fixture checks passed 17 checks; model execution awaits separate
approval. Source 0.5.0 develops extension registration in an independent
installation and is not an arm of that comparison.
Its fresh installation passed 156 local checks, including 19 extension registry
and actual installed-package checks; no model session ran on 0.5.0.

[First-user observation](HOST_USER_OBSERVATION.md) is prepared for one developer
and one conversation user. Neither participant nor a completed session has been
recorded. Real-user usefulness remains separate from these synthetic trials.

The verifier reads the original request and result from the host-configured
tenant's local job store. It returns the job identity and a verification report
with request/result hashes, checker identity, profile/version and the outcomes
for feasibility, objective, optimality and infeasibility. Pending, failed,
cancelled, missing and expired jobs return an error. Unsupported checker
profiles or corrupted results never become a passing report.

`ocp_native_evaluate` remains provider evaluation. A successful tool call is not
itself a successful check: inspect `verification.status` and each check. The
checker covers the declared profile; business requirements omitted from the
request and execution provenance remain outside that evidence.

For a trusted custom extension, use `ocp_runtime.native_extension --extension
MODULE:FACTORY --verification --checker-factory MODULE:FACTORY`. Factories are
host configuration; they cannot be selected in a tool call.

## Prepare an installed candidate

From a source checkout with the development build environment ready:

```sh
python3.12 -B tools/build_native_candidate.py --output /tmp/ocp-host-kit
cd /tmp/ocp-host-kit
python3.12 -B install.py
.native/bin/python -I -B mcp_config.py --evidence
```

Use a new output directory for each build. The last command prints a connection
configuration and does not edit a host. Keep the installed directory available
for the connection. For an offline installation, pass the reviewed wheelhouse
directories using `install.py --offline-wheelhouse`.

The temporary paths above are for reproduction. For a continuing host connection,
build and install in a versioned directory you keep (for example,
`$HOME/ocp-local/preview-1`). Register that installation's absolute Python path.
Reinstall into a new directory when upgrading; moving an installed virtual
environment can break its paths. Keep the prior installation until the new
connection is verified.

For a desktop surface supporting local MCP, the server's command is the printed
absolute Python path; arguments are `-I -B -m ocp_runtime.native_mcp
--verification --evidence`. Enter them through that surface's supported local
MCP configuration. JSON printed by
`mcp_config.py` is a configuration example, not a claim that every host imports
the same JSON format. Host setup varies; see the
[official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp).

Record the exact desktop surface. A tool call in a Codex agent conversation
establishes that surface's connection; ordinary ChatGPT Chat, web, and another
host still need their own checks. A smoke test in the implementation conversation
is useful for debugging but is separate from the fresh-session trials below.

## New multi-domain packet, 2026-11-02

Prepare this separate packet with the installed candidate's Python:

```sh
/absolute/path/to/kit/.native/bin/python -I -B tools/prepare_multidomain_evaluation.py \
  --output /tmp/ocp-multidomain-evaluation
```

It contains twelve new synthetic tasks: four each for routing, worker scheduling
and inventory. Each domain has two calculation/infeasibility/comparison tasks,
one missing-data task and one unsupported-rule task. Independent exhaustive
checkers produce reviewer answers; participants receive only prompts and inputs.
The second-host label defaults to `chatgpt-desktop`; use `--second-host codex-cli`
when that is the actual target. Do not relabel a Codex test as ChatGPT acceptance.

Two repetitions per host produce 48 planned rows, initially `NOT_RUN`.
Per-host targets are at least 11/12 accurate calculation tasks, 6/6 required
clarifications without submission, 6/6 unsupported cases without submission,
and zero critical invented-data or unsupported numerical/scope claims.
The routing oracle supplies a best possible value but accepts independently
checked feasible results without an optimality claim. All claims in the final
answer are reviewed, not just the primary objective. These tasks measure
multi-domain behavior; they are not a paired version-improvement experiment.

Fresh installed checks passed 53 base regressions, 15 CLI checks and 3 packet
checks. The last group exercised seven computation scenarios and six invalid
inputs through actual MCP. This is scripted-client evidence; model and
first-user results remain pending. The current desktop context still exposes
verification 0.1.0 without evidence, so a fresh connection to the new candidate
must be confirmed before a second-host trial. Connection examples were prepared
without changing existing registration.

After explicit approval, the 24 Claude Code/Sonnet sessions for this packet
completed on the fixed 0.3.0 installation. Correct calculation/infeasibility/
comparison completion was 12/12, missing-data clarification without submission
6/6, and unsupported-requirement clarification without submission 6/6. All
14 submitted jobs preserved the supplied scenario and had matching explicit
validate observations and binding receipts. Independent checks passed.

Strict agent review of all final claims and suggested next actions passed
20/24 answers (11/12 calculation answers). Three unsupported-case explanations
misstated rejection versus ignoring, or configurable versus intrinsic rules.
One otherwise correct routing answer suggested submitting an arbitrary baseline
assignment as a job; the API accepts a problem, not a supplied result. No case
actually submitted after dropping the unsupported requirement. Keep these
explanation defects separate from mathematical correctness and no-submit scores.

There were 93 tool calls, zero tool errors/timeouts/retries, and USD 1.4247095
CLI API-equivalent cost against the approved USD 5 target. Mean session time was
16.33 seconds. This is not actual subscription billing or a version comparison.
The new tasks required no preparation mapping, so they do not extend that
feature's transformation evidence. The second host and external-user exercises
remain NOT_RUN. Local report:
`.harness/work/claude-multidomain-20261102/REVIEW.md`.

## Input diagnostics

The validation response keeps its existing `valid` and `issues` shape. A missing
field or unsupported field now points to the field itself using an escaped JSON
Pointer. Examples are `/tasks/0/costs/alex` for an absent pair cost and `/breaks`
for an unsupported rule. Schema errors identify missing values, wrong types,
choices and bounds without repeating the submitted values in messages.

Domain input paths are relative to `input`; envelope paths refer to the whole
request. Consumers should use the declared schema and structured issue code/path
rather than match message text. Validation never supplies a missing value or
removes a rule. Ask for the missing data, or explain the unsupported requirement
and choose a profile that can express it.

These are diagnostic improvements in the Python reference implementation. They
do not alter the Core/native schemas, profile meaning, status values or pinned
contract package. Core and native Python consumer tests cover compatibility;
they do not claim identical diagnostic wording in every language implementation.

## Two participant tasks

An operations participant asks for a complete assignment of six fixed-time
inspection tasks to three workers, then changes availability or workload.
A developer uses the same input in an existing application, preserving errors,
nulls, job states and verification details. Each later supplies an input they
prepared themselves and records assistance and willingness to reuse the tool.

The synthetic source uses integer minutes from the same local day 00:00,
explicit eligible workers and whole-task costs. It has no travel, breaks,
overtime, fairness or automatic shift generation. A real task needing those
rules should select another supporting profile rather than discard the rules.

Generate the shared test packet from the checkout, using the candidate's
installed Python/checker environment:

```sh
/tmp/ocp-host-kit/.native/bin/python -I -B tools/prepare_host_evaluation.py \
  --conversation-host chatgpt-desktop --output /tmp/ocp-host-evaluation
```

Give the host only `participant/README.txt`, the chosen case's prompt and
`input.json`. Keep `reviewer/answers.json` and `reviewer/runs.json` outside the
host task's accessible folder. A facilitator supplies the recorded clarification
only after the host asks. A field absent from a case must not be filled from
another case. Expected objective values come from independent enumeration.

## Trial and scoring

Run 20 cases per host, three repetitions in fresh sessions: 10 normal, five
missing-data and five unsupported-requirement cases. Retain failures and partial
attempts. Record host/model/version, timestamps, tool transcript, assistance,
cost and final answer. Each case counts as one completed task only when its
constraints, result meaning and requested verification are correct.

| Measure | Initial acceptance target |
| --- | --- |
| Normal tasks | At least 27/30 per host |
| Missing information | Required clarification before calculation in at least 14/15 per host |
| Unsupported requirements | Zero executions claiming success after dropping required rules, across 15 cases per host |
| Critical errors | Zero invented data, unsupported optimality claims or timeout-as-infeasible claims in the trial |
| First connection | Four of five new participants connect and calculate within ten minutes after runtime readiness; also record total time from opening instructions |
| Usefulness | One operations user and one developer complete their own input; record assistance and reuse intent |

An explicitly empty eligibility list in N04 is a valid problem with no feasible
assignment. It is different from missing eligibility or costs. N05 has genuine
zero costs; absence of a solution still has a null objective. Automated negative
input checks require zero accepted jobs, including when validate is bypassed.

Feature-only questions, uncertain retries, cancellation and altered-result
checks supplement these tasks. Report them separately from the 20-case score.
Repeated runs do not increase the count of distinct task designs.

## Findings from the first Claude Code experiments

The 2026-10-31 local experiments covered the 20 original cases once, a separate
catalog question, five selected instruction-revision checks and two active
overtime boundary cases. These 28 fresh CLI sessions are exploratory evidence;
they do not fill the three-repetition matrix or another host's results.

All ten normal cases returned the expected result and passed independent
profile verification. Three final answers nevertheless added incorrect
alternative assignments or costs. All five missing-data cases asked for the
missing field without submitting. Every original unsupported-field case was
submitted after transformation or reduction, failing the original zero-submit
criterion. Some transformations preserved the original requirement exactly on
the finite input; the variable-start task instead lost its required goal.

Preserve those original scores. Before a new evaluation version, separate:

- raw unsupported payloads, which must fail validation unchanged;
- requirements that admit a documented, checked transformation;
- requirements that cannot be represented, which require clarification or a
  different supporting profile before solving a reduced problem.

Check the final answer as well as the tool result. A correct verified result
does not validate numerical claims the host adds about a partial assignment,
an alternative plan or a different problem's cost. A caveat saying that an
estimate is unverified does not make an incorrect number acceptable. Record
the original requirement, submitted request and the exact claims checked.
Transformation checks and profile result verification need separate outcomes.

The native MCP guidance now reinforces exact requirement preservation,
validation before submission and evidence-backed numerical explanations.
Selected revision checks improved three of five observed cases but left two
explanation errors. This is not a complete remedy or a statistical success
rate. Tool input/output schemas, annotations and profile catalog digests remain
unchanged; server instructions and tool descriptions changed. Further work should provide checked preparation records and
structured explanation facts while retaining useful supported transformations.

The local candidate implements those records and facts as two opt-in tools:
see [Preparation and explanation evidence](NATIVE_EVIDENCE_CANDIDATE.md). Its
deterministic installed/MCP tests do not change the original model scores or
fill another host's acceptance matrix.

On 2026-11-01, a separately approved 24-session paired pilot compared nine and
eleven tools on the same installation: six synthetic worker tasks and two
repetitions per mode. Both modes completed all eight calculation tasks with
correct results, preserved the requirements in all twelve sessions, and asked
before submitting in all four missing/unsupported cases. Strict final prose
review passed seven of eight calculation answers in each mode. One baseline
answer added a wrong alternative calculation; one candidate answer misstated
the scope of an assignment count. Their primary solutions remained correct.

All four candidate transformation sessions used preparation and explanation;
six ready preparation records were exactly submitted and correctly linked.
The four normal/infeasible candidate sessions used existing verification instead
of explain. The candidate incurred about 35.7% more CLI API-equivalent cost in
this sample. Total cost was USD 1.9796254, separate from the earlier 28 sessions
and not an actual subscription billing statement. No session was rerun.

Original/submitted finite semantics were checked with independent arithmetic;
final answers were agent-reviewed. These observations establish useful trace
records, not better general explanation accuracy, a statistically powered
comparison, another host's acceptance, or completion of the original matrix.
The next changes should improve request-shape diagnostics, scope-specific
explanation facts and call efficiency, followed by a separately versioned trial.

The subsequent local 0.2.0 evidence candidate implements these changes:
canonical full-request tool schemas, field-level validation issues, checked
assignment costs/workloads and explicitly scoped mapping counts. Compact
preparation retains the submitted problem and verification while omitting
repeated source input/text. Explain supplies the stored result and independent
verification without requiring duplicate result/verify/evaluate calls.

A fresh macOS installation passed 92 checks (53 installed regressions,
32 evidence/MCP checks and 7 verification regressions), including compatibility
with the previous 8/9-tool schemas/catalogs and a custom profile. A single
fixed-break response was 28.73% smaller than the prior full response. That local
checkpoint made no model calls, so those checks do not update the pilot's answer
scores or establish lower model cost. See
[the candidate and reproduction instructions](NATIVE_EVIDENCE_CANDIDATE.md).

The subsequent explicitly approved 24-session comparison of evidence 0.1.0 and
0.2.0 (eleven tools each, unchanged six questions, two counterbalanced repeats)
completed on Claude Code/Sonnet. Both achieved requirement preservation 12/12,
correct calculation/infeasibility completion 8/8 and no-submit clarification
4/4. Final calculation prose scored 6/8 versus 8/8 under agent review; both
baseline errors concerned break-explanation scope. Calls decreased 88→63 and
CLI-equivalent cost decreased about 13.5%, with USD 2.0804584 total for this new
phase. This is separate from the previous comparison and subscription billing.

The candidate still made an overbroad catalog statement in one clarification,
added a correct but unexecuted counterfactual, and omitted explicit validate
before one of ten submissions. All submitted inputs/results independently
checked correctly. Report these limitations alongside the successful task
metrics. The small same-host worker sample leaves other domains, hosts and
external-user acceptance unfilled; the original matrix is unchanged.

## Reproduce local checks

The subsequent 0.3.0 implementation addresses those three observations with
explicit capability scope, provider-input validation receipts and job/hash-bound
explanation sources. A missing baseline is explicitly unavailable. Submit
validates the exact input and separately records whether a matching host
validate call was retained; this is not independent result verification.

Fresh installed local validation passed 110 checks: 53 base regressions,
35 evidence checks, 15 validation-receipt regressions and 7 verification
regressions, with no failures/errors/skips. The existing 8/9-tool definitions
and catalogs match the prior 0.2.0 installation. Three reference domains and a
custom profile work through actual MCP. This adds no model-host acceptance
results to the preceding table; the next host trial should examine whether
the model uses the explicit scope/baseline metadata in its final answer.
See [the current evidence candidate](NATIVE_EVIDENCE_CANDIDATE.md).

The existing installed-candidate checker covers the default binding and three
reference domains. The new tests additionally require the checker wheel, MCP
and the three budget example wheels included in the candidate kit.
Start the following commands from the source checkout; after copying the test
files, run them in the scratch directory with the installed candidate:

```sh
python3.12 -B tools/check_native_candidate.py --kit /tmp/ocp-host-kit \
  --wheelhouse /path/to/reviewed-wheels --output /tmp/ocp-host-install-check
mkdir /tmp/ocp-host-checks
cp tests/runtime/test_native_verification.py tests/runtime/test_host_cases.py \
  tests/runtime/test_input_diagnostics.py \
  tools/native_tests/inputs.json examples/native/budget-input.json /tmp/ocp-host-checks/
cd /tmp/ocp-host-kit
.native/bin/python -I -B -m pip install --no-index --no-deps --no-compile \
  ./ocp_budget_profile_example-0.1.0-py3-none-any.whl \
  ./ocp_budget_engine_example-0.1.0-py3-none-any.whl \
  ./ocp_budget_checker_example-0.1.0-py3-none-any.whl
cd /tmp/ocp-host-checks
/tmp/ocp-host-kit/.native/bin/python -I -B test_input_diagnostics.py
/tmp/ocp-host-kit/.native/bin/python -I -B test_native_verification.py
/tmp/ocp-host-kit/.native/bin/python -I -B test_host_cases.py \
  --evaluation /tmp/ocp-host-evaluation --report /tmp/ocp-host-case-results.json
```

These commands use local loopback servers and synthetic inputs. They execute no
model and do not fill participant acceptance. The report retains the actual
tool events and explicitly identifies the automated-client scope.

The installed CLI regression uses `tests/runtime/test_native_cli.py` with
`--kit KIT --output NEW_DIRECTORY --wheelhouse WHEELS
--without-mcp-python PYTHON`. Pass the `without-mcp/venv/bin/python` produced
by `check_native_candidate.py`. The output directory must be outside the source
workspace because the regression creates a separate environment without the
checker. It covers real eight/nine/eleven-tool probes, selected feature versions
and catalog scope, console protocol output, missing optional dependencies and
child cleanup after intentionally broken startup. An evidence-mode console
journey submits and explains a real local job. The CLI's own `--help` works
when MCP is absent. To reproduce the packet checks, copy
`test_multidomain_evaluation.py`, `prepare_multidomain_evaluation.py` and
`multidomain-evaluation.json` into a scratch directory and run the test there
with the installed candidate's Python using `-I -B`.

## Paired evidence comparison reviewed 2026-11-03

Forty-eight new Claude Code 2.1.309 / claude-sonnet-5-5 sessions compared evidence
0.3.0 and 0.4.0 on the same 12 synthetic tasks, twice per version, with balanced
version order. Each version passed 12/12 normal calculation/comparison tasks,
6/6 missing-data questions and 6/6 unsupported-request/no-submit tasks.
Independent structured checks passed 24/24 per version. Full-answer review by
the implementing agent passed 22/24 for 0.3.0 and 23/24 for 0.4.0.

The older version misstated constraint and product-field scope. The newer
version proposed 600–630 instead of the supplied alternative 570–600 in one
worker answer; it submitted no unsupported job. Both miss the 24/24 prose
target. The one-answer difference is diagnostic, not an established general
improvement. Total CLI API-equivalent cost was USD 3.0489965, distinct from
subscription billing. No retries were used. This is not blind, external-human,
second-host or evidence-0.5.0 acceptance. Next review must bind proposed
alternatives and explanatory numbers back to the original input.
