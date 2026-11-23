# Knowledge and execution snapshots

Status: **draft extension 0.1.0-draft.1**, implemented in the local Python
0.3.0.dev1 candidate. This does not revise Core 0.1 or Capability Contract v1.

Knowledge helps a host answer “what can this server do?”, read the right input
format, and explain the declared result meaning. A host can read a localized
summary, then request only the input, objective, constraint or interpretation
items it needs. It does not require an LLM, a Studio account, a database or a UI.

## Authoritative data

The existing execution catalog and registered schemas are authoritative.
`ocp_candidate.knowledge.project` generates a bundle from that catalog.
Authors may supply localized titles, summaries and aliases; projected input,
objective, constraint and result definitions must agree with the catalog.
`lint(bundle, catalog=...)` checks both structure and this agreement. Lint without
a catalog explicitly reports that agreement has not been checked.

The common [JSON Schema](../schemas/knowledge-0.1.schema.json) is packaged in the
Python and TypeScript SDKs. Unknown required Knowledge extensions fail. This
initial draft supports numeric objective definitions already represented by Core;
arbitrary categorical comparison and authored bindings/recipes are future work.

## Read interface

`--knowledge` adds `ocp_native_describe` and `context.knowledge`. Default modes
retain their existing tool names and context. Queries take an exact configured
domain, optional section/item, locale, limit (1–20), cursor and expected digest.

Summaries report the actual locale and whether fallback occurred. Technical
schema prose currently remains English and reports `technical_content_locale`.
User labels and descriptions remain data, never executable host instructions.

Cursors bind the domain, requested locale, section, complete bundle fingerprint
and offset. A changed bundle rejects the cursor; callers read a fresh summary.
Responses exceeding 32 KiB fail with a smaller-page/item instruction instead of
truncating content. The summary target is under 8 KiB. Source bundles are bounded
by the 1 MiB fingerprint limit and at most 64 nested levels.

## Fingerprint encoding

`ocp-json-binary64/1` identifies a new encoding. It is **not** native
`catalogDigest`, the legacy checker JSON hash, or a Studio profile digest.
Fingerprint objects contain both `encoding` and the lowercase SHA-256 hex digest.
No Unicode normalization occurs; valid Unicode is encoded in UTF-8. Lone
surrogates, non-JSON values, non-finite numbers and absolute numbers greater than
2^53−1 fail. Integer 1 and float 1.0 have the same encoding; −0 becomes +0.

The hash input begins with ASCII `ocp-json-binary64/1` followed by a zero byte.
Tags are `n` (null), `t`/`f` (booleans), `d` plus big-endian IEEE 754 binary64,
`s` plus an unsigned big-endian 32-bit byte length and UTF-8 bytes,
`a` plus a 32-bit element count and recursively encoded values, or
`o` plus a 32-bit key count and encoded string-key/value pairs. Object keys sort
by unsigned UTF-8 byte order. Array order is significant. Shared Python/TS
vectors include Korean, supplementary characters, −0 and fractional numbers.

## Execution snapshots

`--snapshots` adds `ocp_native_snapshot` and an execution snapshot reference to
submit responses. Before submission the binding validates the exact request and
requires its explicit configuration to match the provider's resolved configuration.
It records the submitted input, selected and effective configurations, original
Core request, identity mapper version and named fingerprints.

This first implementation records the **submitted Core request**. Files and
natural-language intent before mapping are `NOT_RECORDED`. No automatic defaults
or transformations are applied. It preserves omitted/empty/explicit constraint
selection as data; each existing profile still controls which selections are valid.
In particular an empty list does not disable routing.basic's intrinsic rules.

Snapshots are isolated by authenticated binding tenant, domain and job ID. Reads
check the stored job's exact request and any returned effective configuration.
The bounded in-memory store retains uncertain submission intent and never retries
automatically. Caller-initiated replay requires the same key/request/catalog.
Process restart loses records. A snapshot is not a solution check or execution
attestation; independent verification remains separate.

## Compatibility

| Layer | Revision / behavior |
| --- | --- |
| Core | 0.1.0; unchanged |
| Native contract | Capability Contract v1, pinned 7547036d1bc9; unchanged |
| Knowledge / snapshot | Optional 0.1.0-draft.1 |
| Base native tools | 8; + verification = 9; + evidence = 11 |
| Knowledge / snapshot tools | +1 each; evidence plus both = 13 |
| Default domains | Existing three; coordinates require explicit selection |
| MCP transport exercised | Local stdio through installed mcp 2.3.0; 2025-11-25 legacy and 2026-07-28 discovery tested |
| Remote / durable / Analysis | Not implemented by this extension |

The public consumer migration is opt-in flags. Existing Foundry/Studio consumers
do not need to change. Studio discovery namespaces and profile digest encodings
will require explicit import adapters; this draft does not claim wire equivalence.
