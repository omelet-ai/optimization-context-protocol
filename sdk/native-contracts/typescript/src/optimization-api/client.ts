/**
 * A client of one problem type's Optimization API (Capability Contract v1, M16), for an OCP domain
 * server or a Vertical backend. Every request carries the caller's service token and the trace of the
 * call being served; job requests carry the tenant that owns the job (the call's verified OIP tenant,
 * caller-trace.ts, or an explicit one) and refuse to go without one. Answers are checked against the
 * contract's schemas (@omelet/ocp-core); an error answer becomes an OptimizationApiError with the API's
 * envelope.
 *
 *   const api = createOptimizationApiClient({ baseUrl: 'http://nurse-api:8189/v3', token });
 *   const { job, result } = await api.solve(problem, { idempotencyKey });
 */
import {
  CAPABILITY_IDEMPOTENCY_HEADER,
  CAPABILITY_REPLAYED_HEADER,
  CAPABILITY_TENANT_HEADER,
  capabilityCatalogSchema,
  capabilityErrorEnvelopeSchema,
  capabilityJobResultSchema,
  capabilityJobSchema,
  capabilityValidationSchema,
  isTerminalCapabilityJobStatus,
  type CapabilityCatalog,
  type CapabilityErrorEnvelope,
  type CapabilityJob,
  type CapabilityJobResult,
  type CapabilityValidation,
} from '../contracts/index.js';
import type { ZodType } from 'zod';

import { currentCallerTrace, outboundTraceHeaders } from '../caller-trace.js';

/** An error answer of the API (its envelope), or no answer at all (status 0). */
export class OptimizationApiError extends Error {
  readonly status: number;
  readonly envelope: CapabilityErrorEnvelope | undefined;

  constructor(status: number, message: string, envelope?: CapabilityErrorEnvelope, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'OptimizationApiError';
    this.status = status;
    this.envelope = envelope;
  }

  /** The API's code, or UNREACHABLE, TIMEOUT, BAD_ANSWER, HTTP_<status> from this side. */
  get code(): string {
    return this.envelope?.code ?? (this.status === 0 ? 'UNREACHABLE' : `HTTP_${this.status}`);
  }

  get retryable(): boolean {
    return this.envelope?.retryable ?? (this.status === 0 || this.status >= 500);
  }
}

export interface OptimizationApiClientOptions {
  /** The problem type's base URL, e.g. http://127.0.0.1:9489/v3. */
  baseUrl: string;
  /** The caller's service token (the API holds its sha256). */
  token: string;
  fetch?: typeof fetch;
  /** Per request (default 30 s). */
  requestTimeoutMs?: number;
  /** First and largest wait between job polls (defaults 250 ms and 2 s). */
  pollIntervalMs?: number;
  maxPollIntervalMs?: number;
}

export interface TenantOption {
  /** The tenant that owns the job; default: the tenant of the call being served. */
  tenantId?: string;
}

export interface SolveOptions extends TenantOption {
  idempotencyKey: string;
  /** How long to wait for the job before cancelling it (default 10 min). */
  timeoutMs?: number;
  signal?: AbortSignal;
}

export type SolveOutcome = { job: CapabilityJob; result: CapabilityJobResult; replayed: boolean };

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(signal.reason);
      },
      { once: true }
    );
  });

export function createOptimizationApiClient(options: OptimizationApiClientOptions) {
  const base = options.baseUrl.replace(/\/+$/, '');
  const doFetch = options.fetch ?? fetch;
  const requestTimeoutMs = options.requestTimeoutMs ?? 30_000;
  const firstPoll = options.pollIntervalMs ?? 250;
  const maxPoll = options.maxPollIntervalMs ?? 2_000;
  if (!options.token) throw new Error('an Optimization API client needs a service token');

  function tenantOf(option: TenantOption | undefined): string {
    const tenant = option?.tenantId?.trim() || currentCallerTrace()?.tenantId;
    if (!tenant) {
      throw new OptimizationApiError(0, 'no tenant for the job: a job belongs to the OIP tenant of the call being served', {
        code: 'TENANT_REQUIRED',
        message: 'no tenant for the job',
        requestId: 'client',
        retryable: false,
        issues: [],
      });
    }
    return tenant;
  }

  async function call<T>(
    method: 'GET' | 'POST' | 'DELETE',
    path: string,
    schema: ZodType<T> | null,
    extra: { body?: unknown; tenantId?: string; idempotencyKey?: string } = {}
  ): Promise<{ body: T; headers: Headers }> {
    const headers: Record<string, string> = { accept: 'application/json', authorization: `Bearer ${options.token}`, ...outboundTraceHeaders() };
    if (extra.tenantId) headers[CAPABILITY_TENANT_HEADER] = extra.tenantId;
    if (extra.idempotencyKey) headers[CAPABILITY_IDEMPOTENCY_HEADER] = extra.idempotencyKey;
    if (extra.body !== undefined) headers['content-type'] = 'application/json';
    let response: Response;
    try {
      response = await doFetch(`${base}${path}`, {
        method,
        headers,
        ...(extra.body !== undefined ? { body: JSON.stringify(extra.body) } : {}),
        signal: AbortSignal.timeout(requestTimeoutMs),
      });
    } catch (cause) {
      throw new OptimizationApiError(0, `${method} ${path}: the Optimization API did not answer`, undefined, { cause });
    }
    const text = await response.text();
    let parsed: unknown;
    try {
      parsed = text ? JSON.parse(text) : undefined;
    } catch {
      parsed = undefined;
    }
    if (!response.ok) {
      const envelope = capabilityErrorEnvelopeSchema.safeParse(parsed);
      const detail = envelope.success ? `${envelope.data.code}: ${envelope.data.message}` : text.slice(0, 200);
      throw new OptimizationApiError(response.status, `${method} ${path} answered ${response.status} (${detail})`, envelope.success ? envelope.data : undefined);
    }
    if (schema === null) return { body: parsed as T, headers: response.headers };
    const checked = schema.safeParse(parsed);
    if (!checked.success) {
      throw new OptimizationApiError(response.status, `${method} ${path}: the answer does not keep Capability Contract v1 (${checked.error.issues[0]?.path.join('.') ?? ''}: ${checked.error.issues[0]?.message ?? ''})`, {
        code: 'BAD_ANSWER',
        message: 'the answer does not keep the contract',
        requestId: response.headers.get('x-request-id') ?? 'client',
        retryable: false,
        issues: [],
      });
    }
    return { body: checked.data, headers: response.headers };
  }

  const jobPath = (jobId: string) => `/jobs/${encodeURIComponent(jobId)}`;

  const client = {
    async capabilities(): Promise<CapabilityCatalog> {
      return (await call('GET', '/capabilities', capabilityCatalogSchema)).body;
    },
    async validate(problem: unknown): Promise<CapabilityValidation> {
      return (await call('POST', '/validate', capabilityValidationSchema, { body: problem })).body;
    },
    async resolveConfiguration(body: unknown): Promise<Record<string, unknown>> {
      return (await call<Record<string, unknown>>('POST', '/configurations/resolve', null, { body })).body;
    },
    async resolveDataRequirements(body: unknown): Promise<Record<string, unknown>> {
      return (await call<Record<string, unknown>>('POST', '/data-requirements/resolve', null, { body })).body;
    },
    async submit(problem: unknown, submit: TenantOption & { idempotencyKey: string }): Promise<{ job: CapabilityJob; replayed: boolean }> {
      const { body, headers } = await call('POST', '/jobs', capabilityJobSchema, { body: problem, tenantId: tenantOf(submit), idempotencyKey: submit.idempotencyKey });
      return { job: body, replayed: headers.get(CAPABILITY_REPLAYED_HEADER) === 'true' };
    },
    async repair(request: unknown, submit: TenantOption & { idempotencyKey: string }): Promise<{ job: CapabilityJob; replayed: boolean }> {
      const { body, headers } = await call('POST', '/repairs', capabilityJobSchema, { body: request, tenantId: tenantOf(submit), idempotencyKey: submit.idempotencyKey });
      return { job: body, replayed: headers.get(CAPABILITY_REPLAYED_HEADER) === 'true' };
    },
    async job(jobId: string, option?: TenantOption): Promise<CapabilityJob> {
      return (await call('GET', jobPath(jobId), capabilityJobSchema, { tenantId: tenantOf(option) })).body;
    },
    async result(jobId: string, option?: TenantOption): Promise<CapabilityJobResult> {
      return (await call('GET', `${jobPath(jobId)}/result`, capabilityJobResultSchema, { tenantId: tenantOf(option) })).body;
    },
    async cancel(jobId: string, option?: TenantOption): Promise<CapabilityJob> {
      return (await call('DELETE', jobPath(jobId), capabilityJobSchema, { tenantId: tenantOf(option) })).body;
    },
    async evaluate(body: unknown, option?: TenantOption): Promise<Record<string, unknown>> {
      return (await call<Record<string, unknown>>('POST', '/evaluations', null, { body, tenantId: tenantOf(option) })).body;
    },

    /** The job's end: polls with backoff until terminal; attempts cancellation on timeout or abort without claiming termination. */
    async wait(jobId: string, option: TenantOption & { timeoutMs?: number; signal?: AbortSignal } = {}): Promise<CapabilityJob> {
      const tenantId = tenantOf(option);
      const deadline = Date.now() + (option.timeoutMs ?? 10 * 60_000);
      let pause = firstPoll;
      for (;;) {
        const job = await client.job(jobId, { tenantId });
        if (isTerminalCapabilityJobStatus(job.status)) return job;
        if (Date.now() > deadline || option.signal?.aborted) {
          await client.cancel(jobId, { tenantId }).catch(() => undefined);
          throw new OptimizationApiError(0, `job ${jobId} did not finish in time; cancellation was attempted and termination is unconfirmed`, {
            code: option.signal?.aborted ? 'ABORTED' : 'TIMEOUT',
            message: 'the job did not finish in time',
            requestId: 'client',
            retryable: true,
            issues: [],
          });
        }
        await sleep(Math.min(pause, Math.max(0, deadline - Date.now())), option.signal).catch(() => undefined);
        pause = Math.min(maxPoll, pause * 2);
      }
    },

    /** Submit, wait, and read the result of a succeeded or infeasible job; a failed or cancelled job throws. */
    async solve(problem: unknown, solve: SolveOptions): Promise<SolveOutcome> {
      const tenantId = tenantOf(solve);
      const { job: submitted, replayed } = await client.submit(problem, { tenantId, idempotencyKey: solve.idempotencyKey });
      const job = await client.wait(submitted.jobId, { tenantId, timeoutMs: solve.timeoutMs, signal: solve.signal });
      if (job.status === 'succeeded' || job.status === 'infeasible') {
        return { job, result: await client.result(job.jobId, { tenantId }), replayed };
      }
      const error = job.error;
      throw new OptimizationApiError(409, `job ${job.jobId} ${job.status}${error ? `: ${error.code}: ${error.message}` : ''}`, {
        code: error?.code ?? (job.status === 'cancelled' ? 'JOB_CANCELLED' : 'JOB_FAILED'),
        message: error?.message ?? `the job was ${job.status}`,
        requestId: 'client',
        retryable: error?.retryable ?? false,
        issues: error?.issues ?? [],
      });
    },
  };
  return client;
}

export type OptimizationApiClient = ReturnType<typeof createOptimizationApiClient>;
