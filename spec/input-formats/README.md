# Official input formats — draft extension

An input format is versioned domain content that converts an official file into
the optimization API's canonical JSON. Customer-specific ETL and file upload UI
remain in the application. Direct JSON is a first-class path.

Descriptors declare media type, tables/sheets, columns, types, units, target
pointers, missing/default policies and resource limits. Preparation returns
canonical input plus source-cell provenance and declared transformations; it
does not submit a solve. Domain-specific parsing hooks must be explicitly
installed, never loaded from a spreadsheet or remote metadata.

The Python implementation is `ocp_runtime.inputs.prepare`. CSV accepts supplied
UTF-8 bytes and an explicit format ID/version. XLSX additionally requires the
`_ocp` sheet with `format_id` and `format_version` rows. Tables name their source,
sheet, target JSON pointer, columns, types, missing-value policy, key and optional
references. The same JSON input and effective configuration have the same named
fingerprints regardless of the input path.

Date/time cells use ISO text in this draft; Excel serial-date guessing is not
performed. Naive timestamps require a declared timezone, ambiguous local times
require an explicit fold, and nonexistent local times fail. Decimal scale/offset
and rounding apply only when declared. Null, omission, default and zero remain
distinct. Formula, macro, external-link, entity and oversized archives fail.

Special transformations use an explicitly registered `InputConverter` with ID
and version. The converter returns output plus derivations linking output JSON
pointers to prepared source pointers. Changed values without derivations fail.
The descriptor cannot import a converter by module name or execute file content.

`ArtifactStore` supports owner-scoped byte references for a binding's verified
principal. It does not read remote client filesystem paths or fetch URLs. The
HTTP upload/authentication endpoint is a separate binding concern.
