# Project status and verification boundaries

OCP is an **Apache-2.0 open-source developer preview**, not a stable release or
an independently adopted industry standard.

| Item | Current scope |
| --- | --- |
| Source | Public at [GitHub](https://github.com/omelet-ai/optimization-context-protocol); original code is Apache-2.0, with separate third-party notices |
| Documentation site | Public on [GitHub Pages](https://omelet-ai.github.io/optimization-context-protocol/) |
| Installation | Build local preview artifacts from source; no PyPI/npm release or public binary release assets |
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
