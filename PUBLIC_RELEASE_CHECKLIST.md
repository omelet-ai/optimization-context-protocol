# Public release checklist

This checklist separates technical evidence from rights, people and publication.
The project owner is assigned. Reconfirming that assignment is unnecessary.

| Area | Current state | Release exit condition |
| --- | --- | --- |
| Owner | Assigned by the user | Publish an agreed contact/support scope |
| Source, kit and site | Core and native source previews approved; Pages published; kits built locally | Exact approved source and immutable artifact hashes |
| Local installation and consumers | Automated harness paths implemented | Current PASS for the release artifact; see H20–H22 |
| Platform coverage | macOS arm64 full regression; Linux x86_64 container first-success path | Native Linux/Node validation; Windows remains unsupported until tested |
| Independent checking | Separate checker and intentional corruption probes | State exact profile/constraint coverage; never general engine certification |
| LLM context and behavior | H23 server/context checks; initial scoped model pilot performed, broader H24 acceptance pending | Named model/host trials with fresh sessions, full traces and answer review before claiming LLM interoperability |
| External human use | Review feedback received; installation not completed by that reviewer | Unaided install and integration tasks with recorded outcomes |
| License, copyright and patents | Owner confirmed original source on 2026-10-27 and 28 additional native sources on 2026-10-28, including Apache-2.0 and patent disclosure | Per-file rights review, approved LICENSE/NOTICE and public allowlist |
| Community | Contribution/security guides and issue/PR templates prepared | Working public reporting route, agreed support scope |
| Publication | GitHub source repository and reviewed history authorized; other publication remains separate | Exact repository/ref/artifacts/settings and actions approved |
| Site and trial | Static Pages deployment approved; hosted trial remains separately scoped | Separate scoped environment, operation and cost approval |

Run the current harness rather than treating this document as a test result.
A private code push, automated local pass, limited preview link and public release
are distinct actions. See the [launch preparation](docs/development/GITHUB_LAUNCH.md),
[publication policy](provenance/publication.json) and
[compatibility policy](docs/users/COMPATIBILITY.md).

Source-only publication is tracked in [the approval record](provenance/PUBLICATION_APPROVAL.md). Broader trial, external-user, registry and other hosted-service gates remain separate.
