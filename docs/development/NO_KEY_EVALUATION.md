# No-key evaluation preparation

This is a local preparation workflow. It does not share files, create a release,
launch a model task, authorize rights or complete H12/H24. The operator reviews
the exact artifact, participants, delivery channel and rights scope before sharing.

## Build one frozen package

From a source checkout with the build dependencies in BUILD_FROM_SOURCE.md:

```sh
python3.12 -B tools/prepare_evaluation.py --output /tmp/ocp-evaluation-new
```

The new folder contains a developer ZIP, selected-source archive, SHA256SUMS and
EVALUATION_MANIFEST.json. It includes no key, trial session, internal source
snapshot or execution evidence. The ZIP includes English app/engine/MCP guides,
participant tasks and feedback template. `source-manifest.json` records selected
file hashes and their aggregate digest. `base_commit` is context only: when
selected working files differ, the manifest says so. Without Git, commit state is
null. Candidate 0.1.0 alone is not an immutable identity. Use exact artifact hashes.
Rebuilding may change archive metadata/hashes; freeze once, test that same ZIP,
and deliver only the tested hash after authorization. Never replace a failed run.

## Rehearse the exact ZIP

```sh
python3.12 -B tools/check_kit_environment.py --kit /tmp/ocp-evaluation-new/ocp-developer-kit.zip --work /tmp/ocp-rehearsal-new
```

This requires Python 3.12 and Node 24 on PATH. It creates a fresh HOME, environment
and npm cache, downloads public dependencies, installs both no-key extras, reads
actual MCP context, solves/evaluates/checks, changes input for Python/Node apps,
compiles TypeScript, rejects bad units before execute and checks the BYO path
without OR-Tools/MCP. Only a loopback provider is started and it is stopped on exit.
The report identifies platform, CPU, runtime versions and exact kit/source hashes.
For reviewed offline dependencies, supply `--offline-wheelhouse` and `--npm-cache`;
that mode is recorded separately and does not prove a fresh network download.

For Linux, run the same script and ZIP inside an isolated local container with no
host home, credentials, Docker socket or published ports mounted. Use an immutable
image digest, an unprivileged user and a new temporary filesystem. Record the image
and host architecture separately: x86_64 Linux on an arm64 Mac is emulation, not a
native Linux machine. Linux Node/Python checks do not validate Windows or the full
Foundry/trial integration. Do not mark an unavailable platform as PASS or skip it.

H25 adds 13 automatic regressions, including missing extras, quoted executable
paths, strict JSON, input rejection and packaging boundaries. It uses the reviewed
offline dependencies on the development host. The exact-delivery rehearsal above
is additional evidence; neither is an actual outside developer's acceptance.

`local_agent.py` belongs to the kit's consumer examples, not the SDK/runtime wheel.
It orchestrates the separately installed MCP provider and independent checker.
The candidate wheel retains its no-conformance-import boundary; the provider's
`ocp_evaluate` remains separate from the consumer's independent verification.

## Hand off after approval

Give participants the exact ZIP hash through the trusted delivery channel, the
selected source archive if included in the approved scope, and an anonymous ID.
Use the included tasks and feedback template. Separate setup time, active work,
help and retries. A real no-key cohort is recorded separately from invited Omelet
trials. The existing formal H12 dependency/rights conditions remain unchanged.
Actual model usage has its own host/data/attempt budget; local MCP checks spend
zero model calls. Keep execution reports outside the source repository.
