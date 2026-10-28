/**
 * The trace of the call a domain server is serving (M15). A tool call runs with its correlation id
 * (the gateway's x-oip-correlation-id; a service route's x-correlation-id or x-request-id) and the
 * trace of its W3C traceparent, or a new trace when it carries none. The server's own calls to its
 * Optimization API or engine carry them (outboundTraceHeaders): x-request-id is the correlation id,
 * so the API's access log names the call the gateway logged, and traceparent is a new span of the
 * trace. Outside a call (startup, readiness) there are no such headers.
 *
 * Domain servers load this module from source (@omelet/ocp-server-base/domain) while OCP packages
 * load the built one (@omelet/ocp-server-base): one process-wide store serves both.
 */
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomBytes } from 'node:crypto';

export type CallerTrace = Readonly<{ correlationId: string; traceId: string; flags: string; tenantId?: string }>;

const STORE_KEY = Symbol.for('omelet.ocp-server-base.caller-trace');
const holder = globalThis as unknown as { [STORE_KEY]?: AsyncLocalStorage<CallerTrace> };
const store: AsyncLocalStorage<CallerTrace> = (holder[STORE_KEY] ??= new AsyncLocalStorage<CallerTrace>());
const TRACEPARENT = /^00-([\da-f]{32})-([\da-f]{16})-([\da-f]{2})$/i;

/**
 * The trace of an incoming call: its traceparent's trace id and flags (a new trace without one), and
 * the OIP tenant it serves when it has one (a tool call's verified x-oip-tenant-id, M16).
 */
export function callerTraceOf(traceparent: string | undefined, correlationId: string, tenantId?: string): CallerTrace {
  const match = TRACEPARENT.exec((traceparent ?? '').trim());
  const valid = match !== null && !/^0+$/.test(match[1]!) && !/^0+$/.test(match[2]!);
  const tenant = tenantId?.trim();
  return Object.freeze({
    correlationId,
    traceId: valid ? match[1]!.toLowerCase() : randomBytes(16).toString('hex'),
    flags: valid ? match[3]!.toLowerCase() : '01',
    ...(tenant ? { tenantId: tenant } : {}),
  });
}

export function runWithCallerTrace<T>(trace: CallerTrace, work: () => T): T {
  return store.run(trace, work);
}

export function currentCallerTrace(): CallerTrace | undefined {
  return store.getStore();
}

/** Headers for one outbound call of the call being served: none outside a call. */
export function outboundTraceHeaders(): Record<string, string> {
  const trace = store.getStore();
  if (!trace) {
    return {};
  }
  return {
    'x-request-id': trace.correlationId,
    traceparent: `00-${trace.traceId}-${randomBytes(8).toString('hex')}-${trace.flags}`,
  };
}

/**
 * Headers for one call to an Optimization API (Capability Contract v1, M16): the trace, and the tenant
 * of the call being served (X-OIP-Tenant-Id), which owns the jobs the call makes.
 */
export function outboundCallerHeaders(): Record<string, string> {
  const trace = store.getStore();
  return { ...outboundTraceHeaders(), ...(trace?.tenantId ? { 'X-OIP-Tenant-Id': trace.tenantId } : {}) };
}
