# Domain descriptions and coordinate routing preview

This guide is for a **locally built 0.3.0.dev1 candidate**, not the currently
published release. Install the generated kit using its `install.py`. No Node,
Studio checkout, account or model key is needed for the Python path.

## Connect and explore

Use the candidate environment's executable:

```sh
.native/bin/ocp-native doctor --domain routing-coordinates --evidence --knowledge --snapshots --probe
.native/bin/ocp-native config --domain routing-coordinates --evidence --knowledge --snapshots
```

Copy the resulting MCP configuration into a host that supports local stdio.
Keep that server process alive while working with its jobs and snapshots.

Try these questions:

- “What optimization can this server do, and what data do you need?”
- “이 서버가 지원하는 경로 계획과 필요한 자료를 한국어로 설명해줘.”
- “Read the input template. Explain the distance calculation and current limits before solving.”

The host can first read `ocp_native_context`, then `ocp_native_describe` in `en`
or `ko`. Descriptions and schemas do not spend solver compute. An unsupported
language falls back explicitly; technical schema text remains English.

Without a host, inspect the same installed description:

```sh
.native/bin/ocp-native describe --domain routing-coordinates --locale ko
.native/bin/ocp-native describe --domain routing-coordinates --section input --item schema
```

## Prepare your CSV data

The included synthetic example has one depot, four visits and two vehicles.
Columns state the required units. Missing demand/capacity is an error; zero is a
real value and is preserved. Addresses must first be converted to explicit
coordinates by a separately selected source.

```sh
.native/bin/python coordinates.py --depot coordinates-depot.csv --visits coordinates-visits.csv --vehicles coordinates-vehicles.csv --distance-model haversine --request-id my-coordinate-example > coordinate-request.json
```

This prepares and validates a full request; it does not solve. Supply that JSON
to your host and ask it to validate, submit once, retrieve the result, and run
independent verification. The host should retain `job.jobId` and the idempotency
key, and use `ocp_native_snapshot` to recover the exact submitted configuration.
Ask it to explain the checker scope alongside the result. A feasible solution
is not a proof of optimality.

This profile supports 2–16 vehicles, 1–64 visits and integer kg. It uses spherical
Haversine distances with radius 6,371,000 m, rounding each edge up to integer
meters. It does not provide road travel times or time windows. Use routing.basic
with an explicit road-distance matrix, or an engine/profile that declares the
additional features, when those are required.

## Provide your own domain

An existing installed extension factory can opt into the same description and
snapshot services with `--knowledge --snapshots`. Projection uses that domain's
registered catalog; no routing branch is required in the common runtime.

Export and check a bundle before supplying customized descriptions:

```sh
.native/bin/ocp-native describe --domain routing-coordinates --bundle > knowledge.json
.native/bin/ocp-native lint knowledge.json
```

Add `--catalog catalog.json` to check agreement with the exact execution catalog.
The developer API accepts a localization map when constructing `KnowledgeService`.
The default extension CLI supplies a generic English description for unknown
profiles and reports fallback honestly.

## Preview scope

Snapshots are process-local and retain the submitted Core request, not the source
CSV or a proof of natural-language interpretation. This preview adds descriptions,
coordinate preparation and request preservation. Automated comparison plans,
restart recovery, remote HTTPS host setup and independent human trials remain
separate work. Existing published installation instructions remain valid for the
published release; these flags require this development candidate.
