# Foundry native v1 binding candidate

Status: public source implementation candidate, not a stable new standard or full gateway release.
Authority: pinned Foundry Capability Contract v1. Existing Core 0.1 remains a
separate supported entrypoint; choosing this binding is explicit.

The shared contract defines catalog, validation, configuration/data-requirement
resolution, jobs, results, cancellation, evaluation, service authentication,
tenant scope and idempotency. Python uses the original packaged OpenAPI and
original server implementation. TypeScript uses the original native validators
and SDK. Neither language hand-maintains a second wire schema.

| Boundary | Representation |
| --- | --- |
| Outer catalog/job/error | Capability Contract v1, `contractVersion: "1"` |
| Reference problem body | `domainPayloadFormat: "ocp-core-request/0.1.0"`; complete original request |
| Reference job result | Original Core result under native `JobResult.result` |
| Outer execution | Real queued/running jobs processed by a killable solver process |
| Inner execution profile | The synchronous provider invocation, not the HTTP/MCP job lifecycle |
| Job succeeded | Computation completed; inspect inner feasible/optimal/unknown/infeasible semantics |
| Domain selection | Explicit problem type/path; no guessed profile or engine fallback |
| Optional operations | Compilation, repair and ocps1 state are not advertised by these references |
| Local environment | Volatile two-hour records, bounded session job count, ephemeral bearer token |

Core request identity, capability/profile versions, configuration, metric units,
proof claims, termination and null values are retained. This binding does not
turn matrix routing into Foundry coordinate routing or worker allocation into
nurse scheduling. Each engine declares its actual domain payload. MCP forwards
the declared selection and problem body without inventing a common mathematical
model or mandatory company workflow.

The native MCP interface is a stateless local binding with explicit tools for
context, requirements, validate, submit, job, result, cancel and evaluate. It is
not a claim of the full `foundry-ocp-standard/v1` gateway/state profile. Credentials
and tenant come from the trusted host, not tool arguments. A cancellation request
must be followed by terminal-state confirmation. Read-only context does not solve.

Legacy clients keep their existing imports, payloads and synchronous semantics.
Native consumers explicitly import `ocp_candidate.native` or `ocp-candidate/native`.
The TypeScript native entry is included in the native candidate build, which
retains the original root entry. Python's optional native dependency is separate.
The selected native sources are approved for Apache-2.0 publication in this repository;
local compatibility checks do not authorize registry publication.

## Adoption and version policy

Native v1 is the recommended target for new Foundry-compatible job integrations
using a kit built from the public source. The published Core 0.1 quickstart
remains usable independently. No removal date for its existing entrypoints has
been set. A change in default imports, payload shape or supported behavior needs
an explicit versioned migration and consumer tests.

Contract version (`"1"`), domain profile version (`0.1.0`) and package version
identify different things. Local packages pin the Foundry commit. A reviewed
patch candidate receives a distinct prerelease version and artifact digest;
it must never replace the bytes behind the baseline version. Patch candidates
are proposals until the upstream owner accepts them.

Before upgrading, capture installed versions/hashes, validate the catalog and
profile intersection, run public and isolated internal consumer tests, and
exercise the exact changed behavior. Preserve the previous bundle and lockfile.
Rollback reinstalls those exact artifacts and reruns the same regression suite;
it does not assert that a defect present in the baseline has disappeared.

Domain feasibility/optimality checker code stays independently implemented.
Sharing wire contracts and SDKs must not make a solver its own independent judge.

Known pinned TypeScript SDK issue: its timeout exception text can say a job was
cancelled even when the cancellation request failed. Treat the job's terminal
state as evidence, never that exception text. The local `cancel-uncertainty-1`
proposal changes only this explanation and its API comment; it keeps error codes,
wire schemas and behavior. The default Foundry pin is preserved until upstream
review. The proposal and rollback results are separate from baseline conformance.

The portable source-review build explicitly selects `cancel-uncertainty-1` in
TypeScript prerelease `.review.1`. It never reuses baseline artifact versions.
The outer wire contract and existing Core imports are unchanged. This is an OCP
publication proposal; no upstream Foundry source or service is modified.
