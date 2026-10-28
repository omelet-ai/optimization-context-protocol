# Native dependency review

The following additional public packages are installed separately from the native
source candidate. Their licenses were read from the exact wheel METADATA or npm
package metadata used in local checks; no dependency is relicensed by OCP.

| Package | Version | Declared license | Scope |
| --- | --- | --- | --- |
| FastAPI | 0.135.1 | MIT | Python native HTTP router |
| annotated-doc | 0.0.4 | MIT | FastAPI dependency |
| Zod | 4.6.7 | MIT | TypeScript native contract validation |
| Uvicorn | 0.54.0 | BSD-3-Clause | Native local HTTP server, independent of the MCP extra |

The TypeScript build dependency graph is pinned by `build-package-lock.json` in
the TypeScript folder and the existing Core SDK lock. Python pins are retained
in `tools/native-dependencies.json`, `tools/dependency-wheels.json`, and the kit's
constraints.txt. Linux has a separate hash inventory. Dependency distributions
carry their own notices and binary redistribution conditions. This source review
includes no downloaded dependency wheels or node_modules directories.

The owner approved the selected Foundry-derived Python/TypeScript source rights,
Apache-2.0 distribution and patent disclosure on 2026-10-28. See LICENSE_SCOPE.md
and the repository approval record. Each extracted package includes LICENSE,
NOTICE and THIRD_PARTY_NOTICES.md; the final archive check verifies their bytes.
The recorded source pin and explicit TypeScript proposal provenance are retained.
