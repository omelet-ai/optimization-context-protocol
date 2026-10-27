# Three-domain executable candidate

Status: private technical decision, 2026-10-27. User authorized local implementation
and staged verification, not additional LLM execution, cost, sharing or deployment.

Add worker.scheduling and inventory.replenishment 0.1.0 without changing Core or
assignment.fixture semantics. Add stable $id metadata to the fixture schemas.
The reference algorithms are newly authored here: worker depth-first branch and
bound, inventory dynamic programming over stock states. Foundry's generic shift
builder and (s,S) inventory API informed the boundary review; no internal solver
source or data is copied or imported. Public dependencies are unchanged.

Both profiles are bounded so a separate checker can enumerate small complete
search spaces. The checker shares schemas/envelope utilities, not provider cost,
constraint or optimization functions. The checker wheel must work without the
provider wheel, OR-Tools, MCP or runtime. Provider evaluation explicitly uses
source=engine. Optimal/infeasible claims require the documented proof and an
independently recomputed optimum; feasible/unknown deadlines need no such claim.

MCP context uses an explicit offline registry keyed by exact profile version.
Single-provider tools remain compatible; optional profile selectors on context,
describe and requirements enable an explicitly configured multi-provider server.
The six tool names and Core requests remain unchanged. Missing registration or
schema drift fails closed. Third-party registration never downloads or executes
code. HTTP retains one selected provider per process and the existing client flow.

Compatibility checks: existing Core/routing/coordinate/assignment cases, Python
and Node consumers, actual stdio MCP, source-only builds and independent checker
installation. Candidate package 0.1.0 is still unfrozen; pin the exact new artifact
and schema hashes. Public versioning policy is unchanged. Larger models and
business-specific policies need explicit profile/capability evolution.

H26 → H27 → H28 → H29 → H30 covers contracts, worker, inventory, common consumers
and a fresh evaluation kit. H24 model and H12 human acceptance remain separate.
The [quickstart](../users/MULTI_DOMAIN_QUICKSTART.md) states exact limits and commands.

Provider discovery exceptions are handled inside the MCP protocol error boundary,
including multi-provider catalogs. A failing provider prevents catalog-based
execution; exception text is not included in the response. The original single
provider exception regression and a multi-provider no-execution regression cover
this boundary. Scenario guidance requires matching profile versions, units and
metric definitions, with explicit changed inputs.
