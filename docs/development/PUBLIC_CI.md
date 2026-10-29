# Public source CI

The workflow at `.github/workflows/public-ci.yml` checks an ordinary public
checkout. It never reads a Foundry checkout or private migration snapshot, calls
a model, deploys a site, or posts a package. It does not run H00 or manufacture
historical harness acceptance. H64 separately checks this implementation in the
maintainer workspace after the current H00 baseline passes.

## Matrix and evidence

| Lane | Execution | Meaning of success |
| --- | --- | --- |
| `ubuntu-24.04` | Python 3.12.15, Node 24.22.0, native Linux x64 runner | Public build, fresh installation, real three-domain jobs/MCP, independent checker, optional Node consumer, inspection CSV regressions |
| `macos-14` | Same runtimes, macOS arm64 runner | Same checks on macOS |
| `windows-2022` | Python 3.12.15, no dependencies installed | Both installers reject the unsupported platform before creating output and preserve existing files |

These are configured lanes, not a claim that a hosted run has passed. A local
container rehearsal is emulated Linux, not a native hosted runner result.
Windows installation, Linux arm64, human adoption and new model-host acceptance
remain unverified. Only an actual run for the exact commit establishes hosted CI
success. Initial workflow activation and changes to required branch checks are
separate repository actions; this document does not perform them.

`Public CI required` fails unless every lane succeeds, including when another
lane is skipped or cancelled. It is a status signal that can be selected in
branch protection; it does not by itself prevent administrators from merging
or publishing. There is no release/deployment job.

## Reproduce from public source

Use Python 3.12 on macOS/Linux. Node 24/npm are optional for the second command.
The checker creates a fresh build environment and copies only explicitly listed
public source to a disposable directory. It downloads the exact versions in
the development lock from public PyPI, records the downloaded wheel hashes, then
installs tests and native consumers offline. This records the resolved wheel
bytes; it is not a claim that all supported platforms share one wheel hash or
that the dependencies are cryptographically authenticated by OCP.

```sh
python3.12 -B tools/check_public_ci.py --output /tmp/ocp-public-ci-python
python3.12 -B tools/check_public_ci.py --output /tmp/ocp-public-ci-node --with-typescript
```

Outputs must be new paths outside the checkout. For offline Python dependencies,
add `--wheelhouse /path/to/reviewed-wheels` (repeat for additional directories).
For offline Node builds, set `OCP_NPM_CACHE` and `OCP_NPM_OFFLINE=1` after preparing
the pinned package-lock dependencies. A missing dependency is a failure, not a
skipped check. Existing output is never overwritten.

The suites cover Core contract regressions, real solvers, native Python/Node
clients, eight-tool stdio MCP, idempotency, cancellation/failure semantics,
independent rejection of changed results, BYO worker replacement and CSV
inspection scenarios. Python-only installation is tested with Node absent from
the executable search path even when the runner itself has Node installed.

`result.json` binds counts to source and kit digests, runtime/platform and wheel
hashes. Detailed logs remain in the output directory. The workflow uploads no
artifacts; its console contains synthetic test summaries and failures. Test
counts do not certify an engine or establish external-human acceptance.

## Execution policy

The workflow runs on pull requests, main pushes and manual dispatch using only
standard GitHub-hosted runners. It has `contents: read`, no service secrets,
no persisted checkout credential, no privileged pull-request trigger, finite
timeouts and pinned Action commit SHAs. New pushes cancel obsolete runs.
The file uses JSON syntax, a valid YAML subset, to permit standard-library policy
parsing. The source-selection guard permits this one checked workflow; other
workflow paths remain excluded.

GitHub documents [standard public repository runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [workflow security practices](https://docs.github.com/en/actions/reference/security/secure-use).
No self-hosted or larger runner is requested here. Existing immutable prerelease
assets and the Pages site are unchanged by running these tests.
