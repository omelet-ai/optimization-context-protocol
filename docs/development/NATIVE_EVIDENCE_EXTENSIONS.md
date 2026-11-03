# Add a domain's preparation and explanation behavior

Local source candidate: evidence feature **0.5.0**, registration API **0.1.0**.
The immutable published preview ZIP does not contain this extension API.
Core 0.1, native v1, domain schemas and the existing eight/nine tools retain
their contracts. This API applies to the optional eleven-tool evidence mode.

An installed package can register requirement validation, input preparation,
independent preparation checks, mapping facts, solution details and an
independent detail checker for an exact profile/version. Applications use the
same context → prepare → validate → submit → explain flow. No MCP server edits
are needed to add the package. The host explicitly selects trusted factories.

## Try the separately packaged budget example

Build and install a fresh native candidate following its README. Inside the
generated kit, install all four example wheels into that same environment:

```sh
.native/bin/python -I -B -m pip install --no-index --no-deps --no-compile \
  ocp_budget_profile_example-0.1.0-py3-none-any.whl \
  ocp_budget_engine_example-0.1.1-py3-none-any.whl \
  ocp_budget_checker_example-0.1.0-py3-none-any.whl \
  ocp_budget_evidence_example-0.1.1-py3-none-any.whl
```

Configure the MCP host with the absolute path to that installation's Python and
these arguments; the command starts a stdio server and waits for a client:

```sh
.native/bin/python -I -B -m ocp_runtime.native_extension \
  --extension ocp_budget_engine.registration:extension \
  --verification --checker-factory ocp_budget_check:registry --evidence \
  --evidence-factory ocp_budget_evidence:registry
```

For `budget-selection`, context advertises an empty requirements list: this
example preserves the problem unchanged and adds checked item-level details.
Fill `catalog.requestTemplate.input` with `budget-input.json`, call prepare with
`requirements=[]`, validate and submit the returned problem, wait for completion,
then explain with its job and preparation IDs. `facts.domain_details.data`
contains the chosen items, used/remaining credit capacity and total benefit.
`facts.domain_details.verification` identifies the independent detail checker
and hashes of the request, result and details. Credit and benefit units remain
distinct. Registration alone does not prove the extension's correctness.

## Registration contract

Create an `EvidenceRegistry`, or start with `builtin_evidence()` to retain the
worker handlers, and register these fields:

| Field | Meaning |
| --- | --- |
| `profile`, `feature_version`, `identity` | Exact domain ID/version, explicitly supported evidence feature version, handler ID/version |
| `requirements_schema` | Self-contained JSON Schema for an array; schema references are unsupported in this first API |
| `mapping_supported` | Whether nonempty requirements and transformations are supported |
| `validate(request, requirements)` | Validate structured requirements; raise `ContractError` on mismatch |
| `prepare(request, requirements)` | Return `(prepared_problem, {id, version})` |
| `verify_preparation(original, requirements, prepared)` | Independently check meaning preservation and return a PASS report with checker identity and all three hashes |
| `mapping_facts(original, requirements, proof)` | Derive mapping explanation fields from the checked preparation; the trusted extension owns their semantics |
| `solution_facts(request, result, objective, preparation)` | Build domain-specific details after successful independent result verification |
| `verify_solution_facts(request, result, objective, preparation, details)` | Independently recompute detail fields; return PASS with checker identity and request/result/details hashes |

Extensions declare a literal feature version they have tested, rather than
automatically adopting the installed runtime's version. Duplicate registrations
and mismatched versions fail. The service freezes a snapshot of registrations;
callers cannot mutate stored schema/identity data through returned objects.
Callbacks receive isolated copies. Input mutation, exceptions, malformed reports,
wrong hashes or non-JSON results stop the operation. A failed detail check returns
an error instead of an explanation with unchecked extension details.

An empty requirements list always preserves the exact problem, regardless of
the selected extension. With no evidence handler, valid configured domains keep
identity preparation and generic checked result facts. Nonempty requirements
need a handler that advertises mappings. The built-in worker handler retains
its two checked mappings and the legacy `facts.worker_assignment` field;
new integrations read `facts.domain_details`.

Preparation records include selected handler metadata and the catalog hash.
Changing the request, catalog, handler metadata or recomputed mapping facts
invalidates reuse of that record. These are process-local records: unchanged
metadata is not cryptographic proof of the installed callback code. Release
artifacts and test environments must be pinned separately. Host-selected Python
extensions execute trusted code in the server process; this is not a sandbox
for user-submitted code. Factories never come from tool arguments or payloads.

## Verification and remaining work

`tests/runtime/test_native_evidence_registry.py` covers registration isolation,
wrong versions, schema references, callback mutation/failure, catalog drift,
invalid preparation/detail reports, suppressed details on failed result checks,
and the separately installed budget package's actual MCP flow. Run it with a
fresh candidate outside the checkout, alongside the existing evidence tests.

This increment provides the registration API and one independent example.
Natural-language requirement tracking, a second host's acceptance, remote MCP
deployment and external-user usefulness remain separate work.
