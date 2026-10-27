# Contributing to the OCP developer preview

Thanks for helping make optimization integrations easier to use and verify.
This repository is a private candidate. Public contribution intake and the
project-wide license are not active yet. Do not assume a dependency's license
licenses this repository or submit third-party code without its provenance.

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
Until public intake is enabled, contact the person who invited you through the
same private channel. No response-time commitment or support SLA is promised.
