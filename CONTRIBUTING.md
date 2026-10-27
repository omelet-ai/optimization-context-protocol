# Contributing to the OCP developer preview

Thanks for helping make optimization integrations easier to use and verify.
This developer preview is licensed under [Apache-2.0](LICENSE). Contributions
intentionally submitted for inclusion follow that license's contribution terms.
Only submit work you have the right to contribute, and preserve the provenance
and applicable notices of third-party code.

Start with a small synthetic example and describe the application or engine you
want to connect. Keep Core, domain profiles, bindings and provider policy separate.
A proposal for a new domain needs explicit input semantics, units, supported
constraints, result meaning and an independently checkable example.

For a change:

1. Read [AGENTS.md](AGENTS.md), [the task ledger](TASKS.md) and the affected specification.
2. Follow [fresh-checkout development](docs/development/LOCAL_RUNTIME.md). An exported checkout cannot claim original snapshot verification.
3. Add a meaningful regression for changed behavior. Include rejection paths, result semantics and consumer compatibility when the contract changes.
4. Describe the before/after behavior, commands actually run, platform, and limitations in the pull request. Never mark a skipped or unavailable check as passed.
5. Include only selected source and documentation. Keep keys, customer inputs, internal snapshots and generated run evidence out of the patch.

Use a reproducible bug report or integration report with synthetic input, version,
profile and error code. Security issues follow [SECURITY.md](SECURITY.md).
Use this repository's issues for non-sensitive bugs and integration feedback,
and pull requests for proposed changes. No response-time commitment or support
SLA is promised.
