# Model-visible MCP context candidate revision

The resource-only request guide depended on the host choosing to attach a resource to model context. The five operation tools accepted generic Core dictionaries, so a tools-only host could leave the model without the input schema or request construction rules.

Add `ocp_context()` as the sixth optional MCP tool. It and the existing resource return the same provider-specific guide. Include capability, requirements, a compact canonical request schema with all reachable definitions, known profile input schema, template, interpretation rules and execution steps. Unknown input profiles remain explicit; there is no assumed routing fallback. Both lookup paths redact unexpected provider exceptions and neither invokes a solver.

This is an additive revision of the unfrozen private 0.1.0 candidate. Core, domain profile, execution and binding wire versions remain unchanged. The original five tool names, arguments and Core envelope responses remain unchanged. Consumers discover tools by name rather than requiring an exact count of five. Successful `ocp_context` returns a guide object, not a Core envelope; its failure returns a Core failure with `is_error=true`. Resource readers must also detect that failure before using a template. The resource's existing schema/default/template fields are retained; schema definitions unrelated to requests are omitted.

Pin the new artifact by hash and rerun installed Python/TypeScript/MCP, local trial and onboarding consumers. H23 covers real server behavior and first-use context. H24 separately tracks actual model decisions and answers. Passing SDK calls is not evidence that a language model used the context correctly. See [the validation method](../development/LLM_CONTEXT_VALIDATION.md).

Read-only annotations and explicit compute/quota descriptions help hosts expose the tools accurately. They are hints; authorization, input validation, quota and expiry remain server responsibilities. Provider evaluation is explicitly distinct from an independent checker. MCP remains optional, and no language model or Omelet environment becomes a Core dependency.
