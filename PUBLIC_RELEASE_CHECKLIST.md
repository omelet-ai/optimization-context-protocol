# Public release checklist

OCP is already an Apache-2.0 public-source developer preview. This checklist
separates source availability, an installable preview release and actual adoption.
The owner is assigned; do not request that assignment or confirmed source rights
again. The [first preview plan](docs/development/PREVIEW_RELEASE.md) fixes the
local candidate and its intended delivery channel.

| Area | Current state | Remaining exit |
| --- | --- | --- |
| GitHub source and license | Core/native source public; approved Apache-2.0 notices and explicit selection | Review and approve any subsequent source push separately |
| Preview version and files | [v0.1.1-preview.1](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.1.1-preview.1); selected source ZIP, native kit, hashes and blank review form | Preserve tested bytes; a changed candidate needs a new version |
| Installation and consumers | H63 builds from public selection and tests the same extracted ZIP | Current PASS for this exact candidate, not a historical build |
| Platform scope | macOS arm64 Python/Node; Linux amd64 Python/MCP under Docker emulation | Record actual PASS per artifact; Windows/native Linux arm64/Linux Node remain unverified |
| Independent checking | Real domains, separate checker, corrupted-result probes and bounded proof scope | State exact profile/constraint limits; no engine certification claim |
| Foundry alignment | Pinned Capability Contract v1 and isolated consumer rehearsal | Shared original repositories remain untouched; broader upstream adoption is separate |
| Site | Existing GitHub Pages site public | 2026-10-29 update approved; verify deployed content after publication |
| Registry and release assets | First GitHub prerelease approved; PyPI/npm remain unpublished | Verify anonymous asset download; registry naming/ownership/order needs separate review |
| External human use | Agent feedback and automated installation evidence exist | Real participant's unaided app/engine integration; NOT_RUN until documented |
| Internal business acceptance | Synthetic inspection exercise and owner review form ready | Actual owner's business review; NOT_RUN until documented |
| LLM use | Scoped historical model pilots and real MCP SDK tests | No blanket current-host claim; additional model runs require separate approval |
| Community and support | Issue/PR templates, contribution/security routes; no SLA promised | Validate actual reporting and response flow during first human trials |

A GitHub source preview does not require every future OS, registry or trial
service. Keep the declared scope narrow and accurate. A stable production claim
requires evidence beyond this preview. No automated checker fills a human review
or authorizes uploading, deploying or spending.

For current technical results, run the documented environment's harness and the
exact candidate checks. `STALE` means source/environment/prerequisite identity
changed; it must not be relabeled PASS. Source inventory changes also invalidate
old evidence. Logs and completed execution evidence stay outside public assets.
