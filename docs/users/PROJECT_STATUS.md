# Project status and verification boundaries

OCP is an **Apache-2.0 open-source developer preview**, not a stable release or
an independently adopted industry standard.

| Item | Current scope |
| --- | --- |
| Source | Public at [GitHub](https://github.com/omelet-ai/optimization-context-protocol); original code is Apache-2.0, with separate third-party notices |
| Documentation site | Public on [GitHub Pages](https://omelet-ai.github.io/optimization-context-protocol/) |
| Native v1 | Public source candidate aligned with pinned Capability Contract v1; explicit native SDK/MCP entrypoints; not stable v1 or the full gateway/ocps1 profile |
| Installation | [Native prerelease ZIP](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1) or source build; no PyPI/npm release |
| Runtime examples | Routing, fixed-time worker assignment and deterministic inventory replenishment; bounded reference profiles |
| Omelet trial | Separate invitation, environment and operating limits; no public self-service signup |
| Compatibility | Preview contracts, explicit profile versions and artifact hashes; not a frozen stable API |
| Verification | Automated local consumer and checker tests; each report names its actual scope |
| Adoption | Agent rehearsals and SDK tests are not external developers independently integrating their own engines |

The website displays precomputed synthetic routing, worker and inventory examples,
calculated and independently checked during its build. It runs no live solver in
the browser. Source installation executes real engines locally. MCP SDK connections
verify protocol behavior; actual LLM behavior needs a separately scoped model
evaluation. Provider evaluation and independent checking are different operations.

The constraints in a profile are part of its current contract. Small reference
limits do not promise production-scale scheduling, uncertain-demand inventory,
or routing time windows. Adding such behavior requires a declared compatible
profile, an implementation and appropriate verification.

Use the public README and user guides to get started. Contributor gate names such
as H00/H31 describe repository development checks. They are not prerequisites for
using OCP, a badge of engine certification, or evidence of external acceptance.
Internal source snapshots and private evidence are intentionally absent from GitHub.

Documentation, source, registry artifacts and hosted services have different
publication scopes. A locally generated artifact does not publish itself, and
the source license does not activate a hosted trial or grant a service credential.

For synchronous Core calls use the original quickstart. For native jobs and eight
MCP tools, use [the native source quickstart](https://github.com/omelet-ai/optimization-context-protocol#native-v1-from-public-source).
Both build locally from the same public repository without a Foundry checkout.
Selected native source rights, Apache-2.0 and patent disclosure were confirmed
on 2026-10-28; [the publication record](https://github.com/omelet-ai/optimization-context-protocol/blob/main/provenance/PUBLICATION_APPROVAL.md)
distinguishes source and Pages from registry/releases and hosted trials.


The first immutable asset release is `v0.1.1-preview.1`; see the
[preparation and verification scope](https://github.com/omelet-ai/optimization-context-protocol/blob/main/docs/development/PREVIEW_RELEASE.md). It is
a developer prerelease delivered through [GitHub assets](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1), not a registry release. Exact candidate checks and the refreshed
local harness are separate evidence records. Actual external developer and
internal business-owner acceptance remain pending; the blank forms do not imply
that a participant has performed the tasks.
