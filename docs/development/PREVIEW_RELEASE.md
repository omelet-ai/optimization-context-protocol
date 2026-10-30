# First immutable developer preview

The release identifier is **v0.1.1-preview.1**, targeting the
[GitHub prerelease](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1) in
`omelet-ai/optimization-context-protocol`. The owner approved this first asset
publication and the existing Pages update on 2026-10-29; see the
[scoped approval record](../../provenance/PUBLICATION_APPROVAL.md). This build
plan never grants authority to publish a future candidate. The machine-readable
[plan](preview-release.json) fixes the package versions without renaming the
Core or Foundry contracts. SDK `0.1.1.dev1`, native contract `1`, Core `0.1.0`
and the release identifier describe different layers.

## Prepare and check locally

Use the [development environment](LOCAL_RUNTIME.md). No original Foundry
checkout is needed by the public preview preparation/checking tools.

```sh
python3.12 -B tools/prepare_preview.py build --directory /tmp/ocp-preview-new --with-typescript
python3.12 -B tools/prepare_preview.py verify --directory /tmp/ocp-preview-new
```

Omit `--with-typescript` for a Python-only kit. Existing output is never
overwritten. Preparation builds from only the explicit public source selection
in a separate directory. `assets/` contains a source ZIP, native ZIP,
`SHA256SUMS` and `preview.json`. The generated `PREPARED_NOT_PUBLISHED` and
`publication_authorized: false` fields describe the local builder output: the
builder neither checks nor changes GitHub publication state. The release page
and its immutable tag establish delivery; these flags are not current repository
visibility or a revocation of the separately recorded approval. The native kit includes a first-use guide,
synthetic tasks and a blank review form. It contains no completed test reports,
internal snapshots, keys or Foundry checkout. Local logs remain outside assets.
ZIP entry ordering and timestamps are deterministic for the same input bytes.
Rebuilding wheels may produce different bytes: test and retain one exact kit;
do not rebuild it after acceptance or claim the checksum authenticates its author.

For the complete local candidate regression, pass reviewed dependency stores:

```sh
python3.12 -B tools/check_preview_candidate.py \
  --wheelhouse /path/to/reviewed-macos-wheels \
  --wheelhouse /path/to/reviewed-native-extra-wheels \
  --linux-wheelhouse /path/to/reviewed-linux-wheels \
  --output /tmp/ocp-preview-checked-new
```

Node 24/npm and a running local Docker daemon with the pinned Linux image are
required for this complete matrix. No image pull, dependency registry upload,
model execution or external service solve occurs. Missing dependencies fail;
they are not skipped. Tests install the extracted native ZIP in fresh homes,
run real three-domain jobs and MCP, test independent rejection of corrupt
results, and exercise the CSV inspection project on macOS and offline Linux
amd64 emulation. Optional Node installation/consumer tests run on macOS.

The source content digest and exact kit manifest digest bind the result to
the candidate. Source or artifact changes require rerunning affected checks.
H63 follows the refreshed local H62 chain and adds this portable public-source
check and release-guard regression tests. A public clone can run it directly;
that does not fabricate H00's private migration evidence or historical gates.

## Supported preview and remaining exits

The intended preview support is Python 3.12/macOS arm64 and the tested Linux
amd64 container environment; Node 24/macOS is optional. Windows, native Linux
arm64 and Linux Node are outside this immutable ZIP's verified matrix. Newer
source commits have a separate native Linux x64 Python/Node CI lane; this does
not extend the published ZIP's acceptance or change its bytes. Compatibility is preview
quality; pin the artifact hash and declared profile. No production SLA or stable
API guarantee is made. Use GitHub Issues for non-sensitive bugs and the existing
security reporting guide for vulnerabilities.

For each subsequent publication, obtain scoped approval for the source, release
tag, tested assets and target actions. A main-source push does not publish these assets. The first
release is deliberately an installable ZIP; PyPI/npm are a later channel that
needs separate package-name ownership, dependency publication order and policy
review. Native contracts retain their `Private :: Do Not Upload` / `private`
guards. Do not remove those guards as part of a ZIP release.

The existing Pages site is live; synchronizing its latest content is a separate
deployment. Neither this plan nor H63 deploys it. Additional model calls are also
held. Actual external developer and internal owner acceptance remain `NOT_RUN`
until real people perform the [review tasks](../users/NATIVE_EXTERNAL_EVALUATION.md)
and [inspection review](../users/NATIVE_INSPECTION_ACCEPTANCE.md). These are
adoption evidence requirements, not reasons to pretend source is still private.
