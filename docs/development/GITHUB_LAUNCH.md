# GitHub launch preparation

Status: local preparation, not publication authorization. The intended canonical
project is `omelet-ai/optimization-context-protocol`. Its current visibility is
private. `ocp.omelet.ai` is the selected website direction; permanent deployment
remains on hold. A protected, expiring review link is not the public project site.

## The adoption path

GitHub should own source, specifications, versioned releases, issues, contribution
history and eventually discussions. The website explains the value and directs
visitors to three start paths. Registry packages should remove manual wheel
installation after names, rights and an immutable first release are approved.

The README now leads with a checked first success and a concrete comparison with
direct solver calls. Contribution/security guides and issue/PR templates are
prepared locally. GitHub describes how these files support contributions in its
[contributor guidance](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors).
No workflow, repository setting or publication is activated by this plan.

## Response to the external review

The review is useful qualitative feedback. Its author reported browser interaction
and document reading, but did not complete installation or a solve. Record it as
that observation, not an external acceptance pass.

| Finding | Current response | Remaining evidence |
| --- | --- | --- |
| Preview presented as an open-source product | English README and site label say developer preview; no public package claim | Approved public source/license/release |
| Installation too complex | `python3.12 start.py --venv .local` verifies, installs, solves and checks; existing environment preserved | Real download/install in new users' environments |
| Engine substitution unclear | `demo.py` runs one application/input with OR-Tools and a separate enumerating library | An external developer's own engine; no claim that all engines interchange |
| Value over direct solver calls unclear | README explains discovery, rejection, result semantics and checker boundary | Observe whether developers use this in their application |
| Checker independence unproven to reviewer | Checker-only environment tests accept actual results and reject capacity, missing visit and cost corruption | Additional constraints require their own independent checks |
| Non-routing evidence too narrow | Keep `assignment.fixture` explicitly fixture-only | Build a bounded real assignment adapter and changed-input cases before claiming executable multi-domain coverage |
| ZIP returned 403 in reviewer environment | Complete protected URL returned 200 with two user-agent strings and matching ZIP hash from the execution host; the reviewer-specific 403 was not reproduced | Cannot assign a cause to an environment-specific 403 without its response evidence |

The kit's checksums detect changed bytes, not publisher authenticity. Provide the
checksum through a trusted handoff channel. A protected link must retain its
complete prefix and expire as advertised. For HTTP 403, record time/status and
sanitized headers; never request tokens or disable access controls. The next
public delivery should be an immutable GitHub Release asset, after approval.

## Ordered work and exit conditions

1. **First success (H22):** fresh kit installation, two actual engines, input mutation,
   real deadline, checker-only environment, failure diagnostics and no overwrite.
   Run after H21 with current prerequisite evidence. This is machine validation.
2. **Portable installation:** first success now exercised on Linux x86_64 with
   Python 3.12.15 in Docker Desktop on a macOS arm64 host, including public dependency
   download, two actual engines, corrupt-result rejection and a real deadline.
   See [the reproducible Linux probe](LINUX_FIRST_SUCCESS.md). Native Ubuntu x86_64
   and the Linux Node consumer are the next targets; retain macOS arm64 regression;
   Windows only after installer/path/process behavior is implemented and tested.
   Prepare an isolated Linux runner using public dependencies, build the kit from
   the selected source, run `start.py`, then the checker and failure cases. Record
   OS/architecture/package hashes. No Linux or Windows PASS may be inferred from
   a macOS run. A workflow must be separately approved before activation.
3. **Executable second domain:** a tiny assignment solver with changed cost matrices,
   independent result checking and unsupported-input rejection. Keep its profile
   experimental; do not promote the existing fixture into a general standard.
4. **Human first use:** owner invites up to five developers: Python app engineer,
   Node app engineer and solver author, including a Linux user. Give only the
   kit/docs/tasks. Ask them to install, change input, choose another engine, and
   trigger an unsupported request. Observe time/blockers, assistance and exact
   completed steps. Suggested exit: at least four unaided first successes and two
   independent integrations; these are targets, not achieved results.
5. **Public release:** reviewed source and history, rights/license/NOTICE, immutable
   versions and package names, tested reporting channel, then exact publication
   authorization. Verify anonymous clone/download/install after publication.

Measure first checked execution, unaided success rate, independent integrations,
repeat usage and contributions. Stars are an interest signal, not adoption proof.
No analytics is added to the preview site by this plan.

## Concrete release decisions

The owner is already assigned. Do not request that assignment again.

- **Rights:** Apache-2.0 remains the proposed project license direction accepted
  for preparation. It has not been applied as a rights determination. Review each
  selected source's ownership, dependency notices and patent implications; prepare
  LICENSE/NOTICE only for an approved scope. Never copy a dependency's license to
  the whole project as permission.
- **History and scope:** prefer a reviewed publication extraction with fresh history,
  preserving the private workspace and its history. Do not simply flip visibility
  on the current repository. Resolve the exact destination/name migration before
  making any remote changes. GitHub notes that visibility changes expose repository
  content and affect other features in its
  [visibility documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).
- **Version:** existing `0.1.0` artifacts are private candidates; hashes distinguish
  rebuilds. The first public prerelease tag, Python/Node package names and versions
  must be fixed together after name availability and compatibility review. Never
  silently replace a published artifact under the same version.
- **Operations:** validate private vulnerability reporting and an actual maintainer
  response route. Enable issues/discussions and CI only in the approved repository
  with a defined runner/cost scope. Website and hosted trial are separate approvals.

This file, community templates and the release checklist are preparation artifacts.
They neither approve publication nor establish a license, trial service or support SLA.
