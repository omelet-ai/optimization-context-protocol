import { createHash } from 'node:crypto';

function stable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, stable((value as Record<string, unknown>)[key])])
    );
  }
  return value;
}

/** sha256 of canonical JSON (sorted keys). */
export const canonicalDigest = (value: unknown) => createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');

/**
 * Capability digest of an OCP profile: what the OCP can do, independent of where one server
 * instance runs. `api.baseUrl` is a deployment address (some OCPs derive it from their own port),
 * so it is left out; every other field counts.
 */
export function capabilityDigest(profile: unknown): string {
  if (!profile || typeof profile !== 'object') return canonicalDigest(profile);
  const copy = structuredClone(profile) as Record<string, unknown>;
  const api = copy.api;
  if (api && typeof api === 'object' && !Array.isArray(api)) delete (api as Record<string, unknown>).baseUrl;
  return canonicalDigest(copy);
}
