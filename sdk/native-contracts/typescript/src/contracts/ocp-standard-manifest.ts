/**
 * OCP Standard v1 domain manifest: what a stateless OCP domain server serves at GET /manifest.
 *
 * `domain`, `endpoint`, `tools`, and `execution` are what the OIP gateway needs to register the
 * domain. `catalog` is passed through by the gateway (GET /catalog) and carries the complete OCP
 * profile, the legacy tool contract, and the digests that pin it to the engine, so clients read
 * metadata from the gateway instead of from an OCP server. A domain that keeps session state as
 * `ocp_state` (ADR-0051) says so in `catalog.stateEnvelope`.
 */
import { z } from 'zod';

import { OCP_STATE_ARGUMENT, OcpStateEnvelopeCatalogSchema } from './ocp-state-envelope.js';
import { type ContractValidationResult, validateContractSchema } from './validation.js';

export const OCP_STANDARD_V1 = 'foundry-ocp-standard/v1';

const SHA256_HEX = /^[0-9a-f]{64}$/;

const ToolInputSchema = z
  .object({
    type: z.literal('object'),
    properties: z.record(z.string(), z.unknown()),
    required: z.array(z.string()),
  })
  .passthrough()
  .refine((schema) => schema.required.includes('project_id') && 'project_id' in schema.properties, {
    message: 'every tool input requires project_id, which the gateway checks and removes',
  })
  .refine((schema) => !schema.required.includes('session_id'), {
    message: 'no tool may require session_id: domain servers keep no sessions',
  });

export const OcpStandardToolSchema = z.object({
  name: z.string().regex(/^[a-z][a-z0-9_]*$/, 'tool names are lower_snake_case'),
  description: z.string().min(1),
  inputSchema: ToolInputSchema,
});

export const OcpStandardCatalogSchema = z
  .object({
    standard: z.literal(OCP_STANDARD_V1),
    legacyServerId: z.string().min(1),
    capabilityDigest: z.string().regex(SHA256_HEX),
    engineCapabilityDigest: z.string().regex(SHA256_HEX).optional(),
    /** Legacy tool name -> this domain's tool name. */
    tools: z.record(z.string(), z.string()),
    /** The tool that reads the legacy MCP resources. */
    resources: z.string(),
    /** Legacy REST route -> this domain's tool name. */
    rest: z.record(z.string(), z.string()),
    legacyTools: z.array(z.object({ name: z.string().min(1) }).passthrough()),
    /** The domain keeps session state as `ocp_state` (ADR-0051). */
    stateEnvelope: OcpStateEnvelopeCatalogSchema.optional(),
    objectives: z.unknown(),
    constraints: z.unknown(),
    solverParameters: z.unknown(),
    profile: z.record(z.string(), z.unknown()),
  })
  .passthrough();

export const OcpStandardDomainManifestSchema = z
  .object({
    domain: z.string().regex(/^[a-z][a-z0-9-]*$/, 'domain ids are lower-kebab-case'),
    endpoint: z.object({ baseUrl: z.string().url() }),
    tools: z.array(OcpStandardToolSchema).min(1),
    execution: z.object({ tool: z.string().min(1) }),
    catalog: OcpStandardCatalogSchema,
  })
  .superRefine((manifest, context) => {
    const names = manifest.tools.map((tool) => tool.name);
    const declared = new Set(names);
    const issue = (path: (string | number)[], message: string) =>
      context.addIssue({ code: z.ZodIssueCode.custom, path, message });

    if (declared.size !== names.length) issue(['tools'], 'tool names must be unique');
    // Tool names are global across the domains behind one gateway, so each domain namespaces them.
    const prefix = manifest.execution.tool.endsWith('solve') ? manifest.execution.tool.slice(0, -'solve'.length) : '';
    if (!prefix) issue(['execution', 'tool'], "the execution tool is the domain's <prefix>solve");
    names.forEach((name, index) => {
      if (prefix && !name.startsWith(prefix)) issue(['tools', index, 'name'], `tool '${name}' lacks the domain prefix '${prefix}'`);
    });
    if (!declared.has(manifest.execution.tool)) issue(['execution', 'tool'], `execution tool '${manifest.execution.tool}' is not declared`);

    const { catalog } = manifest;
    for (const [legacy, tool] of Object.entries(catalog.tools)) {
      if (!declared.has(tool)) issue(['catalog', 'tools', legacy], `legacy tool '${legacy}' maps to undeclared tool '${tool}'`);
    }
    for (const [route, tool] of Object.entries(catalog.rest)) {
      if (!declared.has(tool)) issue(['catalog', 'rest', route], `route '${route}' maps to undeclared tool '${tool}'`);
    }
    if (!declared.has(catalog.resources)) issue(['catalog', 'resources'], `resource tool '${catalog.resources}' is not declared`);
    // A server that still advertises replay serves a contract that no longer exists (ADR-0051).
    if (Object.hasOwn(catalog, 'replayableTools')) issue(['catalog', 'replayableTools'], 'catalog.replayableTools was removed: replay was replaced by ocp_state (ADR-0051)');

    const envelope = catalog.stateEnvelope;
    if (envelope) {
      const byName = new Map(manifest.tools.map((tool) => [tool.name, tool]));
      envelope.tools.forEach((legacy, index) => {
        const mapped = catalog.tools[legacy];
        if (!mapped) {
          issue(['catalog', 'stateEnvelope', 'tools', index], `state tool '${legacy}' is not a mapped legacy tool`);
        } else if (!(OCP_STATE_ARGUMENT in (byName.get(mapped)?.inputSchema.properties ?? {}))) {
          issue(['catalog', 'stateEnvelope', 'tools', index], `state tool '${legacy}' maps to '${mapped}', which does not declare ${OCP_STATE_ARGUMENT}`);
        }
      });
    }
  });

export type OcpStandardDomainManifest = z.infer<typeof OcpStandardDomainManifestSchema>;

export function validateOcpStandardDomainManifest(value: unknown): ContractValidationResult<OcpStandardDomainManifest> {
  return validateContractSchema(OcpStandardDomainManifestSchema, value);
}
