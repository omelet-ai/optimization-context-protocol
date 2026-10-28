/**
 * Capability Contract v1 (M16): what every Optimization API answers, as the OCP domain servers and
 * the Vertical backends read it. The normative text and the OpenAPI document are in
 * shared/ocp-contracts/capability-contract; these schemas follow the OpenAPI components
 * (tests/contracts/capability-contract.test.ts holds them to it).
 *
 * The API computes catalogDigest; a client compares it, as a string, with the digest it pinned.
 */
import { z } from 'zod';

export const CAPABILITY_CONTRACT_VERSION = '1';
/** The OIP tenant a job belongs to (jobs, results, evaluations, repairs). */
export const CAPABILITY_TENANT_HEADER = 'X-OIP-Tenant-Id';
/** Unique within (tenant, problem type): the same key and request name the same job. */
export const CAPABILITY_IDEMPOTENCY_HEADER = 'Idempotency-Key';
/** "true" when a submission's key already named the job answered. */
export const CAPABILITY_REPLAYED_HEADER = 'Idempotent-Replayed';

export const CAPABILITY_JOB_STATUSES = ['queued', 'running', 'succeeded', 'infeasible', 'failed', 'cancelled'] as const;
export const CAPABILITY_TERMINAL_STATUSES = ['succeeded', 'infeasible', 'failed', 'cancelled'] as const;

const code = z.string().regex(/^[A-Z][A-Z0-9_]*$/);
const timestamp = z.string().min(1);

export const capabilityIssueSchema = z.object({ code: z.string(), message: z.string(), fieldPath: z.string().optional() }).passthrough();

/** Every error an API answers. */
export const capabilityErrorEnvelopeSchema = z
  .object({
    code,
    message: z.string(),
    requestId: z.string().regex(/^[\w.:-]{1,128}$/),
    retryable: z.boolean(),
    fieldPath: z.string().optional(),
    issues: z.array(capabilityIssueSchema),
  })
  .strict();

export const capabilityJobStatusSchema = z.enum(CAPABILITY_JOB_STATUSES);

/** Why a job failed: a code the solve declared, or SOLVE_FAILED, SOLVER_CRASHED, ATTEMPTS_EXHAUSTED, BAD_OUTCOME. */
export const capabilityJobErrorSchema = z
  .object({ code, message: z.string(), retryable: z.boolean(), issues: z.array(capabilityIssueSchema) })
  .strict();

/** A job's state; never its problem or result. */
export const capabilityJobSchema = z
  .object({
    jobId: z.string().uuid(),
    problemType: z.string(),
    status: capabilityJobStatusSchema,
    attempt: z.number().int().min(0),
    cancelRequested: z.boolean(),
    createdAt: timestamp,
    updatedAt: timestamp,
    startedAt: timestamp.nullable(),
    finishedAt: timestamp.nullable(),
    expiresAt: timestamp,
    error: capabilityJobErrorSchema.optional(),
  })
  .strict();

export const capabilityJobResultSchema = z
  .object({ jobId: z.string().uuid(), status: z.enum(['succeeded', 'infeasible']), result: z.record(z.string(), z.unknown()) })
  .strict();

/** The catalog: digests cover everything but catalogDigest itself and api.baseUrl. */
export const capabilityCatalogSchema = z
  .object({
    contractVersion: z.literal(CAPABILITY_CONTRACT_VERSION),
    problemType: z.string().regex(/^[a-z][a-z0-9-]*$/),
    catalogDigest: z.string().regex(/^[0-9a-f]{64}$/),
    api: z.object({ version: z.string().optional(), baseUrl: z.string().optional() }).passthrough().optional(),
    objectives: z.array(z.unknown()).optional(),
    constraints: z.array(z.unknown()).optional(),
    parameters: z.array(z.unknown()).optional(),
  })
  .passthrough();

export const capabilityValidationSchema = z.object({ valid: z.boolean(), issues: z.array(capabilityIssueSchema) }).passthrough();

/** At least status ok and the service; an API that had its own /health keeps its fields. */
export const capabilityHealthSchema = z.object({ status: z.literal('ok'), service: z.string() }).passthrough();

export const capabilityReadinessSchema = z
  .object({ ready: z.boolean(), service: z.string(), checks: z.array(z.object({ name: z.string(), ok: z.boolean() }).strict()) })
  .strict();

export const capabilityVersionSchema = z.object({ service: z.string(), build: z.string() }).passthrough();

export type CapabilityIssue = z.infer<typeof capabilityIssueSchema>;
export type CapabilityErrorEnvelope = z.infer<typeof capabilityErrorEnvelopeSchema>;
export type CapabilityJobStatus = z.infer<typeof capabilityJobStatusSchema>;
export type CapabilityJob = z.infer<typeof capabilityJobSchema>;
export type CapabilityJobResult = z.infer<typeof capabilityJobResultSchema>;
export type CapabilityCatalog = z.infer<typeof capabilityCatalogSchema>;
export type CapabilityValidation = z.infer<typeof capabilityValidationSchema>;

export function isTerminalCapabilityJobStatus(status: CapabilityJobStatus): boolean {
  return (CAPABILITY_TERMINAL_STATUSES as readonly string[]).includes(status);
}
