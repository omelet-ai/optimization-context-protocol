# OCP Server integration baseline IB-1.2

IB-1.2 adds a current authorization policy hook to the generic MCP binding.
Use it when access to an optimization request, saved job, analysis or result
can change after the server starts. Domain content supplies the policy; the
runtime supplies the enforcement points. No project, hospital, ward, identity
provider or cloud service becomes mandatory in the common format.

This is the **public source integration baseline** for generic OCP Servers. Build
the runtime and the domain wheel from the same source revision. This table is the
version reference for the authoring and integration guides. The [Native ZIP](https://github.com/omelet-ai/optimization-context-protocol/releases/tag/v0.2.0-preview.2)
has its own installation path. When upgrading from [IB-1.1](TEMPLATE_INTEGRATION_BASELINE.md),
match the package versions and checksums.

| Component | Version |
| --- | --- |
| Generic runtime | `0.4.0.dev12+publicformat3` |
| Routing example | `0.1.0.dev3` |
| Generated template | `0.1.0-draft.5` |
| Server descriptor | `0.1.0-draft.2`, unchanged |
| Optional operations | `0.1.0-draft.2`, unchanged |
| Core and pinned native contract | Unchanged |

## Configure the policy in installed content

A trusted connector may implement the synchronous method
`authorize(principal, action, resource) -> bool`. Only the literal `True` permits
the action; a denial or exception fails closed. The principal comes from the
binding's authentication mechanism. Uploaded JSON cannot select policy code,
provide a trusted identity or grant itself permission.

The action identifies the binding operation: `describe`, `prepare`, `validate`,
`submit`, `job`, `result`, `evaluate`, `cancel`, `plan`, `run`, `analysis`,
`compare`, `stop_analysis`, `prepare_operation` or `operation.<declared-id>`.
The resource includes the supplied input/configuration or operation context.
For saved jobs it also includes the server-stored original request and owner;
for saved analyses it includes the stored plan. Policies should use that stored
scope to evaluate access, rather than trusting a caller's identifier alone.

The binding checks before dispatch and again before disclosing the response.
Large responses retain a server-owned policy context with their artifact.
Reading a chunk or reusing that artifact as an input rechecks the current
policy, including after a restart. Once a state directory has used an
authorization hook, removing that hook does not expose its saved data: startup
rejects the missing policy. A changed contract cannot read an old protected
artifact under a different meaning.

If permission is revoked after dispatch, the response has code
`AUTHORIZATION_REVOKED_AFTER_DISPATCH`, outcome `requires_observation`, and
`retryable: false`. Effects may already have occurred. Retain the original
request identifier/idempotency key and reconcile under valid authority;
do not submit a replacement automatically.

## Execution and compatibility boundaries

The optional hook guards the MCP binding. Direct SDK calls and a queued
worker's later provider call are separate execution boundaries: the installed
connector must check current authority immediately before its own effects.
The hook does not replace transport authentication or the consumer's permission
checks. Packages without a hook retain their existing local behavior.

To upgrade, rebuild the domain wheel against the successor runtime and run its
consumer checks. Keep the descriptor, schemas and operation references stable
unless their meaning actually changes. Do not force an older domain wheel to
use a different runtime by ignoring its dependency pin.

The installed public acceptance suite includes policy denial, saved-request
scope, revocation, restart, artifact reuse, analysis access and ambiguous
post-dispatch outcomes. Domain-specific grants and real product/host acceptance
remain checks of the corresponding deployment.
