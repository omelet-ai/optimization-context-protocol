# Portable native v1 source review

Status: public source candidate; source rights and Apache-2.0 notices approved 2026-10-28.
This is a source developer preview proposal, not a stable v1 or production service.
The original Core 0.1 quickstart remains available alongside the native source path.

## What changed

The candidate contains the native Python SDK/server/MCP, three reference-domain
examples and an engine registration template. `sdk/native-contracts/` contains
the pinned shared contracts and SDK required to build independently. It needs
neither a Foundry checkout nor an import from a local reference tree. Only the
explicit contract selection is included; private routing engines are excluded.

The Python SDK build has version `0.1.1.dev1`. The extracted Python dependency
has version `0.0.0+foundry.7547036d1bc9.review1`. TypeScript native artifacts use
`.review.1`, preserving the original Core root export and opt-in `/native` export.
The explicit `cancel-uncertainty-1` proposal corrects the timeout description:
a failed cancellation cannot claim computation stopped. Its upstream acceptance
is false. No Foundry source, Git metadata, shared dependency or service is changed.

Routing provider measurements now use `source=engine`, including provider
evaluation. An independent checker is installed separately, reruns its own checks
and rejects deliberately corrupted results. This is a correction to provenance
reporting within the existing Core schema; it changes no field or enum shape.

The native extra now explicitly depends on Uvicorn. A fresh `[native,reference]`
installation previously could not start the local API unless MCP was also
installed. A separate no-MCP installation regression reproduces that failure and
checks all three actual reference solves after the dependency correction.

## Build from this candidate tree

Prerequisite: Python 3.12 with the exact development requirements installed.
Use a fresh output path. These commands build local review artifacts and never
publish anything. Run from this repository after checking out the native source update.
The README native quickstart uses fresh temporary directories to avoid collisions.

```sh
python3.12 -m venv /tmp/ocp-native-build-env
/tmp/ocp-native-build-env/bin/python -m pip install -r tools/requirements-dev.lock
/tmp/ocp-native-build-env/bin/python -B tools/build_native_candidate.py --output /tmp/ocp-native-kit
cd /tmp/ocp-native-kit
python3.12 -B install.py
.native/bin/python -I -B demo.py
.native/bin/python -I -B mcp_config.py
```

Python/MCP need no Node. For optional TypeScript artifacts, use Node 24/npm and
add `--with-typescript` to the build command with a new output directory. The
builder uses the committed npm locks, disables install scripts, and retains
only archives in the kit. Optional `OCP_NODE`, `OCP_NPM`, `OCP_NPM_CACHE` and
`OCP_NPM_OFFLINE=1` select explicit tools and a prepared offline cache.

## Check the exact artifacts

`tools/check_native_candidate.py` accepts `--kit`, `--output` and one or more
`--wheelhouse` paths. It uses a fresh HOME and installed environment, requires
Python installation without Node on PATH, and tests actual jobs, cancellation,
idempotency, tenant isolation, all three domains, real stdio MCP and independent
corrupt-result rejection. `--node` and `--npm` add the installed TypeScript and
upstream SDK regressions. Controlled transport/cancellation fixtures are labelled.

The wheelhouses must be reviewed public dependencies matching
`tools/dependency-wheels.json` and `tools/native-dependencies.json`; installed
artifacts carry their original notices. `tools/check_native_linux.py` runs the
same kit's input scenarios in the exact image and dependency selection recorded
in `tools/linux-dependencies.json`, with no network and no project checkout mount.
Linux amd64 on an arm64 Docker host is emulation, not native arm64 evidence.

These are standalone checks against the exact candidate; they do not refresh or
promote the historic H37–H62 chain. External-human acceptance and LLM/host
acceptance of this exact portable candidate remain NOT_RUN; historical tests of
other artifacts do not transfer to this candidate. No participant has been
assigned. They are limits to
the preview claim, not invented proof of independent adoption.

### Portable inspection checks

The public builder includes the independent project, inspection CSV application,
and optional worker/budget example wheels. The example SDK dependency accepts only
the tested `0.1.0` through `0.1.1.dev1` interval; `pip check` must pass after installation.
The public native SDK remains `0.1.1.dev1`; no registry artifact has been published.

`tools/check_inspection_candidate.py` runs the H61/H62 inspection exercise using
only the generated kit and the public `tools/native_tests/inspection_suite.py`.
It performs 13 checks of actual jobs/MCP, CSV errors, changed conditions and
independent report validation, then checks optional dependencies and the custom
budget profile. It requires a fresh output path and reviewed dependency caches:

```sh
python3.12 -B tools/check_inspection_candidate.py --kit /tmp/ocp-native-kit --wheelhouse /path/to/python-wheels --wheelhouse /path/to/native-wheels --output /tmp/ocp-inspection-macos
python3.12 -B tools/check_inspection_candidate.py --kit /tmp/ocp-native-kit --linux --wheelhouse /path/to/linux-wheels --output /tmp/ocp-inspection-linux
```

The Linux command requires the already available image and exact wheel hashes in
`tools/linux-dependencies.json`. It never pulls an image or enables container
networking. Neither command needs `tools/foundry_convergence/`, internal plans,
Foundry snapshots, keys, execution evidence, an external participant or a model.
The historical harness plan retains local-only stages for owners who hold those
materials; public clones use these standalone checks and do not claim H00
snapshot validation or internal adoption.

## Publication scope

The owner approved the 28 extracted sources for Apache-2.0 distribution, patent
disclosure, GitHub `main` publication, and the documentation Pages update on
2026-10-28. See [the approval record](../../provenance/PUBLICATION_APPROVAL.md).
The reviewed candidate had 301 files; adding the six required package license
and notice files makes the final explicit inventory 307. The rights note is
renamed LICENSE_SCOPE.md. Original source hashes remain fixed.

Run `python3 -B tools/check_native_publication.py --require-approval`,
`python3 -B tools/verify_repository.py --index` and
`python3 -B tools/check_public_release.py` against the final selected source.
These checks verify the recorded scope; they do not manufacture legal approval.
Registry packages, release assets, trial hosting and model calls are excluded.
Generated kits are for local builds; their artifact-posting flag remains false.
Never reuse a prerelease version after its artifacts are publicly distributed.
