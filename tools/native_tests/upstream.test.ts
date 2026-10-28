import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { createServer, type IncomingMessage, type Server } from 'node:http';
import { after, before, describe, it } from 'node:test';

import { callerTraceOf, outboundCallerHeaders, runWithCallerTrace } from '../src/caller-trace.js';
import { OptimizationApiError, createOptimizationApiClient } from '../src/optimization-api/client.js';

// A stand-in Optimization API keeping Capability Contract v1 for one problem type.
type Seen = { method: string; path: string; headers: IncomingMessage['headers']; body: unknown };
const seen: Seen[] = [];
const jobs = new Map<string, { tenant: string; status: string; polls: number; problem: Record<string, unknown> }>();
const keys = new Map<string, string>();
const TOKEN = 'client-test-token';
let server: Server;
let base = '';

function envelope(code: string, message: string, requestId: string, retryable = false) {
  return { code, message, requestId, retryable, issues: [] };
}

function jobJson(id: string) {
  const job = jobs.get(id)!;
  const finished = ['succeeded', 'infeasible', 'failed', 'cancelled'].includes(job.status);
  return {
    jobId: id,
    problemType: 'toy',
    status: job.status,
    attempt: job.status === 'queued' ? 0 : 1,
    cancelRequested: job.status === 'cancelled',
    createdAt: '2026-10-03T00:00:00+00:00',
    updatedAt: '2026-10-03T00:00:00+00:00',
    startedAt: job.status === 'queued' ? null : '2026-10-03T00:00:00+00:00',
    finishedAt: finished ? '2026-10-03T00:00:01+00:00' : null,
    expiresAt: '2026-10-10T00:00:00+00:00',
    ...(job.status === 'failed' ? { error: { code: 'NO_FEASIBLE_ROSTER', message: 'nurse n-3 cannot cover the night', retryable: false, issues: [] } } : {}),
  };
}

before(async () => {
  server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const url = new URL(req.url ?? '/', 'http://x');
      const path = url.pathname.replace(/^\/v3/, '');
      const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : undefined;
      seen.push({ method: req.method ?? '', path, headers: req.headers, body });
      const requestId = String(req.headers['x-request-id'] ?? 'made-here');
      const send = (status: number, payload: unknown, headers: Record<string, string> = {}) => {
        res.writeHead(status, { 'content-type': 'application/json', 'x-request-id': requestId, ...headers });
        res.end(JSON.stringify(payload));
      };
      if (req.headers.authorization !== `Bearer ${TOKEN}`) return send(401, envelope('UNAUTHENTICATED', 'a service bearer token is required', requestId));
      if (path === '/capabilities') return send(200, { contractVersion: '1', problemType: 'toy', catalogDigest: 'b'.repeat(64), api: { version: '1.0' }, objectives: [] });
      if (path === '/broken/capabilities') return send(200, { contractVersion: '9' });
      const tenant = String(req.headers['x-oip-tenant-id'] ?? '');
      if (path.startsWith('/jobs') && !tenant) return send(400, envelope('TENANT_REQUIRED', 'X-OIP-Tenant-Id must name the tenant', requestId));
      if (req.method === 'POST' && path === '/jobs') {
        const key = `${tenant}|${req.headers['idempotency-key']}`;
        const existing = keys.get(key);
        if (existing) return send(202, jobJson(existing), { 'idempotent-replayed': 'true' });
        const id = randomUUID();
        jobs.set(id, { tenant, status: 'queued', polls: 0, problem: body });
        keys.set(key, id);
        return send(202, jobJson(id));
      }
      const match = /^\/jobs\/([^/]+)(\/result)?$/.exec(path);
      const job = match ? jobs.get(match[1]!) : undefined;
      if (match && (!job || job.tenant !== tenant)) return send(404, envelope('JOB_NOT_FOUND', 'no such job for this tenant', requestId));
      if (match && job && req.method === 'DELETE') {
        if (!['succeeded', 'infeasible', 'failed'].includes(job.status)) job.status = 'cancelled';
        return send(202, jobJson(match[1]!));
      }
      if (match && job && !match[2]) {
        job.polls += 1;
        if (job.problem.hang) job.status = 'running';
        else if (job.polls >= 2) job.status = job.problem.outcome ? String(job.problem.outcome) : 'succeeded';
        else job.status = 'running';
        return send(200, jobJson(match[1]!));
      }
      if (match && job && match[2]) return send(200, { jobId: match[1], status: job.status, result: { value: 42 } });
      return send(404, envelope('NOT_FOUND', 'no route', requestId));
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  base = `http://127.0.0.1:${typeof address === 'object' && address ? address.port : 0}/v3`;
});

after(() => new Promise<void>((resolve) => server.close(() => resolve())));

const client = () => createOptimizationApiClient({ baseUrl: base, token: TOKEN, pollIntervalMs: 5, maxPollIntervalMs: 20 });
const inCall = <T>(tenant: string | undefined, work: () => Promise<T>) => runWithCallerTrace(callerTraceOf(undefined, 'gw-call-1', tenant), work);

describe('the caller trace carries the tenant (M16)', () => {
  it('a call with a tenant passes it on; a call without one does not', () => {
    assert.equal(runWithCallerTrace(callerTraceOf(undefined, 'c', ' tenant-a '), () => outboundCallerHeaders()['X-OIP-Tenant-Id']), 'tenant-a');
    assert.equal(runWithCallerTrace(callerTraceOf(undefined, 'c'), () => 'X-OIP-Tenant-Id' in outboundCallerHeaders()), false);
    assert.deepEqual(outboundCallerHeaders(), {}, 'outside a call, nothing');
  });
});

describe('Optimization API client (Capability Contract v1)', () => {
  it('reads the catalog with the service token and the call trace', async () => {
    const catalog = await inCall('tenant-a', () => client().capabilities());
    assert.equal(catalog.catalogDigest, 'b'.repeat(64));
    const request = seen.at(-1)!;
    assert.equal(request.headers.authorization, `Bearer ${TOKEN}`);
    assert.equal(request.headers['x-request-id'], 'gw-call-1');
    assert.match(String(request.headers.traceparent), /^00-[\da-f]{32}-[\da-f]{16}-01$/);
  });

  it('solves under the tenant of the call, polling until the job ends', async () => {
    const outcome = await inCall('tenant-a', () => client().solve({ n: 1 }, { idempotencyKey: 'k-solve' }));
    assert.equal(outcome.job.status, 'succeeded');
    assert.deepEqual(outcome.result.result, { value: 42 });
    assert.equal(outcome.replayed, false);
    const submit = seen.find((request) => request.method === 'POST' && request.path === '/jobs')!;
    assert.equal(submit.headers['x-oip-tenant-id'], 'tenant-a');
    assert.equal(submit.headers['idempotency-key'], 'k-solve');
    const again = await inCall('tenant-a', () => client().submit({ n: 1 }, { idempotencyKey: 'k-solve' }));
    assert.equal(again.replayed, true);
  });

  it('cancels the job when the caller gives up (a cancelled tool call)', async () => {
    const controller = new AbortController();
    const solving = inCall('tenant-a', () =>
      client().solve({ hang: true }, { idempotencyKey: 'k-abort', signal: controller.signal })
    );
    setTimeout(() => controller.abort('Studio step timeout'), 30);
    await assert.rejects(solving, (error: unknown) => error instanceof OptimizationApiError && error.code === 'ABORTED');
    const cancel = seen.find((request) => request.method === 'DELETE' && request.path.startsWith('/jobs/'));
    assert.ok(cancel, 'the job was cancelled');
    assert.equal(cancel.headers['x-oip-tenant-id'], 'tenant-a');
  });

  it('refuses a job without a tenant before sending anything', async () => {
    const before = seen.length;
    await assert.rejects(client().submit({ n: 1 }, { idempotencyKey: 'k-none' }), (error: unknown) => error instanceof OptimizationApiError && error.code === 'TENANT_REQUIRED');
    assert.equal(seen.length, before);
  });

  it('an explicit tenant wins over the call\'s', async () => {
    await inCall('tenant-a', () => client().submit({ n: 2 }, { idempotencyKey: 'k-explicit', tenantId: 'tenant-b' }));
    assert.equal(seen.at(-1)!.headers['x-oip-tenant-id'], 'tenant-b');
  });

  it('a failed job throws its error; another tenant\'s job is not found', async () => {
    await assert.rejects(
      inCall('tenant-a', () => client().solve({ outcome: 'failed' }, { idempotencyKey: 'k-fail' })),
      (error: unknown) => error instanceof OptimizationApiError && error.code === 'NO_FEASIBLE_ROSTER' && error.retryable === false
    );
    const { job } = await inCall('tenant-a', () => client().submit({ n: 3 }, { idempotencyKey: 'k-iso' }));
    await assert.rejects(inCall('tenant-b', () => client().job(job.jobId)), (error: unknown) => error instanceof OptimizationApiError && error.status === 404 && error.code === 'JOB_NOT_FOUND');
  });

  it('an infeasible job answers its result', async () => {
    const outcome = await inCall('tenant-a', () => client().solve({ outcome: 'infeasible' }, { idempotencyKey: 'k-infeasible' }));
    assert.equal(outcome.job.status, 'infeasible');
  });

  it('a job that outlives the timeout is cancelled', async () => {
    await assert.rejects(
      inCall('tenant-a', () => client().solve({ hang: true }, { idempotencyKey: 'k-hang', timeoutMs: 60 })),
      (error: unknown) => error instanceof OptimizationApiError && error.code === 'TIMEOUT'
    );
    assert.ok(seen.some((request) => request.method === 'DELETE'), 'the client cancelled the job');
  });

  it('a wrong token, an unreachable API and an answer off the contract are errors with codes', async () => {
    await assert.rejects(createOptimizationApiClient({ baseUrl: base, token: 'wrong' }).capabilities(), (error: unknown) => error instanceof OptimizationApiError && error.status === 401 && error.code === 'UNAUTHENTICATED');
    await assert.rejects(createOptimizationApiClient({ baseUrl: 'http://127.0.0.1:1/v3', token: TOKEN, requestTimeoutMs: 2_000 }).capabilities(), (error: unknown) => error instanceof OptimizationApiError && error.code === 'UNREACHABLE' && error.retryable);
    const broken = createOptimizationApiClient({ baseUrl: `${base}/broken`, token: TOKEN });
    await assert.rejects(broken.capabilities(), (error: unknown) => error instanceof OptimizationApiError && error.code === 'BAD_ANSWER' && error.status === 200);
  });
});
