# Routing preview preparation

**v0.2.0-preview.1 is the routing-first GitHub developer prerelease.**
The owner approved its main push, four release assets and Pages update on
2026-11-03; see the [publication record](../../provenance/PUBLICATION_APPROVAL.md).
Older v0.1.1-preview.1 assets remain unchanged.

## Delivery

The target is a GitHub developer prerelease in
`omelet-ai/optimization-context-protocol`, with these four assets:

- `ocp-native-v0.2.0-preview.1.zip`: Python kit, routing quickstart and notices.
- `ocp-source-v0.2.0-preview.1.zip`: explicitly selected source snapshot.
- `preview.json`: version, source and archive hashes.
- `SHA256SUMS`: checksums for the two ZIP files.

The [version plan](preview-release.json) pins Python package `0.2.0a1`, evidence
feature `0.5.0`, native contract `1` and Core/domain payload `0.1.0`. The first
recommended configuration uses OR-Tools with `--domain routing-basic --evidence`.
Optional TypeScript remains a separate source build. PyPI/npm and hosted trials
are outside this delivery.

## Prepare and inspect

Use the [local development environment](LOCAL_RUNTIME.md), then:

```sh
python -B tools/verify_repository.py --selection provenance/routing-preview-selection.json
python -B tools/prepare_preview.py build --directory /tmp/ocp-routing-preview
python -B tools/prepare_preview.py verify --directory /tmp/ocp-routing-preview
```

Choose a new output directory. Preparation uses only the explicit candidate
selection and never uploads or modifies a host configuration. Installation tests
must use the exact extracted native archive on each declared platform. Record
macOS arm64 and Linux amd64 Docker emulation separately. Verify routing-only
catalogs, calculation, comparison, invalid/missing inputs, idempotency and
independent rejection of corrupted results. Human review forms stay blank until
participants actually complete them.

## Source and notices

`provenance/routing-preview-selection.json` and the canonical source allowlist
record the approved 392-file inventory. Builder plan flags stay false because
creating another local artifact does not authorize its publication. LICENSE, NOTICE and THIRD_PARTY_NOTICES are unchanged;
pinned contract sources and their notices remain intact. Dependencies install
separately under their own licenses. Native contract registry-upload guards
remain enabled. Local build metadata is preparation evidence, not live GitHub
publication state.

For future updates, review the source changes and obtain the exact main push,
release and Pages scope before publishing. Reconcile the approved source
allowlist, rerun the index/source guards and archive checks, then check the live
version, checksums, installation links and bilingual site.
See the [routing delivery scope](ROUTING_FIRST_RELEASE.md).
