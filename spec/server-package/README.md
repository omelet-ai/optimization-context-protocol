# OCP Server package descriptor — draft 0.1

Status: **implementation draft 0.1.0-draft.2**. Core 0.1 and the pinned native v1
wire contract remain unchanged. A descriptor is domain content; it is not a
mandatory endpoint layout or a Studio plugin.

The [JSON Schema](../schemas/server-package-0.1.schema.json) describes server/API
and profile versions, arbitrary API input/configuration/result schemas,
capabilities, units, metrics, input formats, playbooks and optional extensions.
The Python validator additionally checks references, defaults, schema pointers,
IDs, unit declarations and required extension support. An optional authoritative
API contract comparison checks the declared API, schemas and capabilities.
Descriptor validation alone cannot prove a solver implements its advertised math.

An author supplies API schemas and meanings; no vehicle, nurse, ward, shift or
single objective-value field is required by the common schema. Results may have
continuous values, categorical metrics, multiple objectives or partial solutions.
Optional capabilities are advertised only when the adapter actually implements
them. Customer database mapping, mutable business state and visualization belong
to applications. Official file-to-API conversion belongs to domain content.

API/profile/package/input-format/recipe versions are distinct. Changes to units,
defaults, feasible-set meaning, objective terms or interpretation require a
profile/API compatibility decision, not just a package version bump. Existing
`routing.basic` meaning is not changed by this descriptor.

This portable draft uses JSON Schema 2020-12 with document-local JSON Pointer
references. It does not fetch remote schemas or execute metadata. Unsupported
required extensions fail; optional extension data is retained as descriptive
data and cannot silently change execution. Installed connectors and hooks are
trusted deployment configuration, not functions selected by an API request.

Configuration defaults may be partial. Explicit top-level configuration values
replace defaults; nested objects are not implicitly merged. The effective
configuration is validated and returned before execution. Parameter ranges are
API schema constraints; allowed combinations are explicit configuration rules.

Binding and metric pointers address the API document. This draft requires an
unambiguous property/items schema path for editable bindings. APIs with unions
can expose a stable binding or an installed domain transformation; unsupported
ambiguous bindings are rejected rather than inferred. This restriction concerns
editable bindings, not arbitrary API input/result schema validation.

Fingerprint objects include their encoding name. `ocp-json-binary64/1` is not
Foundry `catalogDigest` or a Studio digest. Reference checks compare ID, version
and the complete digest object; equality of hex strings alone is insufficient.

## Draft 2 capability selection

Draft 2 preserves draft 1 descriptors and adds accurate constraint-mode declarations.
`kind: ["hard", "soft"]` advertises modes the API can select per constraint instance;
it does not declare that either mode was enforced by a particular run. Single-mode
`"hard"` and `"soft"` declarations remain valid. `kind: null` means the API uses a
domain-specific classification, which its definition and input schema must explain.
The exact API schema and API validation still govern allowed combinations and
parameters. Empty, duplicated and unknown mode arrays are rejected. An array or
null requires `format_version: "0.1.0-draft.2"`; draft 1 semantics stay unchanged.
The common runtime does not infer or change the requested mode.

Draft 2 also permits an explicit `result_role` in the connector outcome. A feasible
or optimal result is a `solution`. An `unknown` outcome may preserve a schema-valid
`candidate` (for example a partial or relaxed schedule) or `diagnostics`; an
`infeasible` outcome may preserve only `diagnostics`. These roles require a non-null
result and never turn the outcome into feasible. Without an explicit role, the
existing non-solution/null rule stays unchanged. Candidates can be checked but
are excluded from feasible-result ranking. Authors must disclose violated or
relaxed requirements in their result schema. Draft 1 connectors retain their
original five-field outcome. Native job terminal success means processing ended,
not that a feasible solution exists.
