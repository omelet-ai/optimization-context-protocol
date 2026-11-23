# OCP Server integration baseline IB-1.1

**Use this baseline to build a domain package and start consumer integration.**
It freezes the existing generic Python template and its interfaces for this
integration cycle. Studio and Foundry acceptance proceeds against these pinned
interfaces; unfinished product features do not require redesigning the template.

IB-1.1 is a local integration baseline, not a new published release or a claim of
full product compatibility. The wire versions below retain their existing draft
status. The local delivery includes exact file and wheel checksums.

## Pinned interfaces

| Layer | Pinned version | Contract |
| --- | --- | --- |
| Generic Python runtime | `0.4.0.dev11+publicformat2` | `ocp-candidate[server]` |
| Generated template | `0.1.0-draft.4` | [Template](../../templates/ocp-server/README.md) and generation record |
| Server descriptor | `0.1.0-draft.2` | [Package contract](../../spec/server-package/README.md) |
| Optional operation extension | `0.1.0-draft.2` | [Operations](../../spec/operations/README.md); opt in per package |
| Routing example package | `0.1.0.dev2` | [Runnable content](../../examples/routing-ocp-server/content/README.md) |
| Existing contracts | Core `0.1`, pinned native `v1` | Existing meanings remain unchanged |

Use the version **and** artifact checksum when installing a local candidate.
Do not combine an older native kit with the generic candidate by changing its
dependency pin. Native and generic installation paths are separate.

### Changes from IB-1

IB-1 (`publicformat1`, template draft.3, Routing dev1) remains an immutable
integration artifact. IB-1.1 fixes startup diagnostics without changing the
descriptor, operation extension or wire contracts:

- `doctor` and `serve` reject missing or mismatched advertised file converters,
  including converters declared by optional operations.
- `host-config` validates the factory reference, state settings and HTTP port
  before printing a configuration. It does not load connector code or secrets.
- Authoring rejects package names that a wheel build would reject, and the
  generated guide distinguishes a blank config from a content-supplied example.

Existing content can be regenerated from its preserved content directory with
the new runtime. Use a new output directory and install the matching runtime
and domain wheels together. Keep an IB-1 consumer on its pinned artifacts until
its domain package has been rebuilt and its consumer checks pass; do not override
an existing domain package's runtime dependency to force an upgrade.

## What is fixed

The common package supplies a launcher, trusted connector loading, descriptor
validation, discovery, execution state and transport bindings. The author owns
the optimization API's schemas, supported capabilities, connector, meanings,
official input formats, checker and optional playbooks inside `content/`.

```text
Customer application / MCP host
  customer data mapping, identity, permissions, UI and visualization
                     |
                OCP interface
                     |
  generic runtime + installed domain content
  discovery -> prepare/validate -> execute/job -> result/evaluation
                     |
              Optimization API
```

- API input/configuration/result schemas are arbitrary JSON schemas within the
  documented supported schema vocabulary. No routing, nurse, ward or UI fields
  are mandatory in the common descriptor.
- Official CSV/XLSX-to-API transformations can be domain content. Customer-specific
  database/ERP mappings and result visualization stay in the application.
- Only explicitly installed connectors execute code. Metadata and uploaded files
  cannot select a Python import, endpoint or credential.
- Optional query/command operations and playbooks are discovered and versioned.
  A host checks support before exposing them. An operation acknowledgement does
  not establish an observed state change; a playbook does not grant execution
  permission or an unlimited retry budget.
- Preserve the complete execution/operation report. A completed job, a feasible
  solution, a provider claim and independent evaluation are separate facts.
  Preserve `unknown`, `null`, unsupported constraints and explicit empty choices.
- Transport and product authorization remain consumer/deployment responsibilities.
  Studio, Foundry, a specific identity system and a cloud account are not required
  by the generic template.

## Start integration now

1. Run the [source quickstart](../../README.md#author-a-server-for-your-optimization-api--local-review-candidate)
   or install the two reviewed wheels supplied with the local integration kit.
2. Follow the [authoring guide](../users/SERVER_FORMAT_PREVIEW.md) to create a new
   project and supply domain content. Reuse the runtime unchanged.
3. Follow the [consumer guide](../users/SERVER_FORMAT_INTEGRATION.md) to register
   the installed package, discover exact schemas and connect one complete task.
4. Validate the same installed artifacts in each consumer. Keep its existing
   authentication and data/UI ownership. Add further operations after that first
   task succeeds.

## Acceptance is scoped

| Baseline evidence | Product integration still required |
| --- | --- |
| Standalone build/install; verbatim quickstart; official MCP SDK; actual Routing solve and independent check | Actual target host configuration and user workflow |
| Content stripping/reinjection; a separate continuous blending example | Each new optimization API's own implementation and meaning checks |
| Descriptor, configuration, status, idempotency and error checks; isolated IB-1 Nurse execution followed by a separate saved-result continuation | Complete Studio feature parity, including repair/playbooks and an uninterrupted execute-to-save journey |
| Consumer adapters and recorded isolated experiments | Foundry's actual OIP/OpenFGA/Product DB and customer application acceptance |

The earlier IB-1 combined source candidate passed 504 checks on macOS arm64/Python
3.12.15. The local IB-1 report separately identifies its own source hashes,
targeted rerun and unchanged implementation evidence. Neither result marks the
legacy full-product campaign complete. Other OS, TypeScript, remote MCP, actual
model-host UI and human acceptance have their own checks.

## Change rule during integration

Keep these interfaces fixed while consumers integrate. Record a reproducible
contract defect before proposing a breaking change. A semantic change to input,
units, constraints, result interpretation or operations needs an explicit version
and consumer migration decision. Additional domain content and application UI
work do not require a common-template revision. Publish a successor baseline
with new checksums instead of silently replacing an accepted artifact.
