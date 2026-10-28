# Native candidate: independent developer evaluation

This is a local review candidate. Sharing requires approval for the exact bundle
and its newly extracted contract sources. No participant has been assigned yet.
The public Core 0.1 release is a separate path; these instructions do not claim
that native artifacts have been published to GitHub or a package registry.

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
