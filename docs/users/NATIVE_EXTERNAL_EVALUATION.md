# Native candidate: independent developer evaluation

Core and native sources are public under Apache-2.0; the native source rights
and notices were approved in October 2026. Download the native ZIP and checksum
from the [first GitHub prerelease](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1).
A separately rebuilt evaluation bundle is a different artifact; do not replace
the published checksum with its hash. No independent participant has been assigned yet.
The release kit includes START_HERE.md and a blank REVIEW_FORM.json. Record
actual outcomes and help needed; automated tests never populate human acceptance.

## Start without project assistance

Use a new directory and Python 3.12. Read the bundle's README and run its install
command. Python and MCP do not need Node, an Omelet account or a model API key.
Follow WORKED_EXAMPLES for routing, fixed-time worker assignment and inventory
ordering. Save the command, OS/architecture, Python version, elapsed time and
first error. Do not send credentials, customer data or the contents of HOME.

macOS arm64 and Linux amd64 are the local harness targets. Linux verification
runs in an offline Docker container on an arm64 host, using amd64 emulation.
Windows and native Linux arm64 are separate, unverified targets. MCP SDK calls
do not prove that an LLM independently selected and interpreted the tools.

## Task A: your application

Pick one domain. Create a different synthetic input rather than copying an
expected answer. Write a small app that discovers capabilities, obtains required
input fields, validates, submits with a stable idempotency key, waits and saves
the result. Change one meaningful condition and compare the outcomes. Report
job status, mathematical status, objective value and unit separately.

Submit a deliberately invalid unit. Confirm an actionable field error and no
solver execution. Submit a valid infeasible problem and explain its proof.
Corrupt a returned objective or remove an assignment and check that the
independent checker rejects it. Do not treat provider evaluation as independent.

## Task B: your engine

The bundle includes `native_server_template.py`, a runnable registration example:

```sh
.native/bin/python -I -B native_server_template.py worker-input.json
```

It reuses the reference worker provider and therefore is **not an independent
engine**. Replace it with your own provider implementing describe, requirements,
validate, execute and evaluate. Keep the declared profile only if its semantics
are preserved. Reject unsupported constraints instead of ignoring them. The
same app must work with the reference engine and your engine for the common
supported profile. The shared native router, job lifecycle and SDK should not
need a fork. Retain the script's main guard for spawned solver processes.

Small fixed-time tasks are enough: no nurse-specific or production scheduling
rules are required. Record time unit, eligibility, overlap, availability, maximum
working time, cost semantics, supported size and termination/proof semantics.
If your algorithm cannot prove optimality, return feasible with an honest
termination reason. A timeout without a solution is unknown, not infeasible.

Acceptance needs your code and a reproducible run. Changing an engine ID while
still calling the reference solver does not satisfy this task. No need to share
proprietary solver internals: disclose the tested interface and give the owner
a reproducible permitted integration or an appropriately limited test artifact.

## Task C: MCP and feedback

Generate the configuration using the README and connect a real MCP SDK client.
Discover all three domains and the eight native tools, then run the same input.
Repeat submit with the same key and payload and confirm the same job. Explain
why a completed job does not automatically mean an optimal mathematical result.
Do not run a model without a separately approved task count and usage scope.

Record each obstacle before asking for help. Use these fields for each finding:
task, environment, first command, observed result, expected result, help needed,
time to first verified solution, reproducible example and severity. Mark each
task as NOT_STARTED, BLOCKED, PASS or FAIL. Do not mark a task passed solely
because this project's own harness passed. The maintainer records human
acceptance only after reviewing an actual participant's submission.

## TMS integration evaluation

This exercise helps a delivery-app developer evaluate the public native preview.
Use the published `v0.1.1-preview.1` ZIP, its checksum and bundled installation
instructions. Record the exact artifact hash. It runs a local reference engine,
not Omelet's commercial TMS engine; no customer system or model is called.

### Run, change and explain a delivery problem

From the freshly installed native kit directory, use new input/output names:

```sh
.native/bin/python -I -B scenarios.py --output tms-inputs
.native/bin/python -I -B demo.py --domain routing-basic --input tms-inputs/routing-basic-base.json --output tms-base-result.json
.native/bin/python -I -B demo.py --domain routing-basic --input tms-inputs/routing-basic-changed.json --output tms-changed-result.json
.native/bin/python -I -B demo.py --domain routing-basic --input tms-inputs/routing-basic-infeasible.json --output tms-infeasible-result.json
.native/bin/python -I -B demo.py --domain routing-basic --input tms-inputs/routing-basic-invalid.json
```

The last command is intentionally rejected and exits nonzero. Keep that outcome;
do not silently discard the bad unit or turn a rejected request into a solve.

| Scenario | Expected interpretation |
| --- | --- |
| Base | Three 2 kg deliveries, one 6 kg van; feasible, 12 meter distance, feasibility and objective independently checked, optimality not claimed |
| Changed | Farthest point moves from 6 to 10 meters; all related matrix entries change; feasible, 20 meter distance |
| Infeasible | One mandatory delivery is 7 kg and the van holds 6 kg; independently checked capacity proof, no solution or numeric objective |
| Invalid | Matrix unit is `km`; validation rejects the input before a solver job is submitted |

These are deliberately tiny synthetic distances, not road-network distances.
The 12-to-20 change is a changed-input example, not a savings percentage or an
engine-quality comparison. Do not claim global optimality from a feasible result.
Inspect the mathematical response and verification dimensions separately from
the completed job status. The independent checker verifies supported claims;
it does not attest that a commercial service executed the request.

Next, create a different synthetic input and a minimal consumer owned by your
app project. Document its expected constraints before running. Exercise an invalid
input and preserve errors and null values in the app. Replaying these sample
commands counts as sample replay, not independent app integration.

### Map your application's requirements before connecting an engine

| TMS input or behavior | Current basic routing exercise | Additional integration work |
| --- | --- | --- |
| Delivery IDs and quantities | Unique visit IDs, nonnegative integer kg demands | Define order aggregation, explicit unit conversion and ID mapping |
| Vehicle IDs and capacity | Positive integer kg capacities; one depot and one trip per vehicle | Document fleet selection; do not drop volume, mixed loads or multi-trip rules |
| Distances | Explicit integer-meter matrix covering every depot/visit pair | Record the source/version of road data, directionality and rounding outside the profile |
| Time windows, travel/service time, shifts, breaks, skills | Unsupported | Agree a suitable profile, implementation and independent checking scope; do not remove required constraints to fit the example |
| Result | Visit order, total distance, status and separate checks | Map to a draft dispatch plan; business approval and operational dispatch belong to the app |
| Execution | Local preview jobs with bounded, volatile state | Assess persistence, authentication, isolation, retries, monitoring and support for the intended deployment |

The basic profile allows at most 64 visits and 16 vehicles; inspect the selected
engine's advertised limits, which may be narrower. Only compare engines on an
explicit common profile, units, objective, constraints, input and execution budget.
Keep this mapping in an independent app project. This exercise requires no
changes to an existing Foundry repository or product deployment.

### Record adoption evidence

Use the bundled `REVIEW_FORM.json` and record the release/hash, OS/architecture,
Python version, first attempted command, first error, support interventions and
result files. Record elapsed time both from opening the instructions and, as a
separate measurement, after Python 3.12 is ready. Retain failed and incomplete
attempts. Do not combine different releases or assisted/unaided results into one
success rate. Record later attempts separately instead of replacing the first.

Maintain separate outcomes for installation, sample replay, own input, own app,
own engine and business-owner review. Mark unperformed tasks NOT_STARTED or
NOT_RUN. Automation is an automated rehearsal, never an external participant.
Thirty minutes after runtime readiness is a proposed TMS onboarding observation
target, not a measured result or a change to the existing H12 criteria. Actual
participation, consent and review remain necessary for human acceptance.

### Discuss commercial fit

For a commercial TMS or engine integration, [contact Omelet](https://www.omelet.ai/en/contact/)
with approximate daily stops/vehicles, required constraints, current dispatch
workflow, preferred deployment environment and a proposed success measure.
Use descriptions or permitted synthetic examples for the first conversation;
agree access and handling before sharing customer records or credentials.

Assess integration effort, planning time and comparable route quality separately.
Agree the business baseline and acceptance criteria before a customer pilot.
Inquiry is not OCP trial enrollment or confirmation that a feature is available.
The OCP trial remains recommended when invited. The protocol and local/BYO paths
do not require purchasing an Omelet product.
