/**
 * The `ocp_state` envelope (ADR-0051): how a stateless OCP domain server hands a session's state to
 * its caller and takes it back on the next call, instead of re-running the caller's earlier calls.
 *
 *   token  = "ocps1." kid "." b64u(header) "." b64u(iv12 ‖ ciphertext ‖ tag16)    (base64url, no padding)
 *   header = {"dom","sv","cd","sub","sid","seq","by","iat","exp"}                  (these keys, this order, compact JSON)
 *
 * The payload is AES-256-GCM over gzip(codec(state)) with the header segment as associated data; only
 * the domain servers hold the keys (@omelet/ocp-server-base/domain seals and opens). This module is the
 * part every party shares: the format, the header schema, the answers a server gives, and the catalog
 * entry (`catalog.stateEnvelope`) that tells a client the domain keeps state this way. It reads a
 * header without any key, in Node.js and in browsers alike (atob, TextDecoder).
 */
import { z } from 'zod';

export const OCP_STATE_FORMAT = 'ocps1';
/** Identifier of the state codec inside the encrypted payload. */
export const OCP_STATE_CODEC = 'ocpsc1';
/** The tool argument that carries the token in (null: the flow keeps state, none held yet). */
export const OCP_STATE_ARGUMENT = 'ocp_state';
/** The answer field that carries the new token out. */
export const OCP_STATE_RESULT_FIELD = 'ocp_state';

/** Lifetime of a token, from its seal (exp − iat). */
export const OCP_STATE_TTL_SECONDS = Object.freeze({ default: 7200, min: 60, max: 86_400 });
/** Largest token a server accepts or emits, in characters (bytes: the token is ASCII). */
export const OCP_STATE_MAX_BYTES = Object.freeze({ default: 512 * 1024, min: 16 * 1024, max: 768 * 1024 });
/** Longest header segment a server reads. */
export const OCP_STATE_MAX_HEADER_SEGMENT = 2048;
/** Smallest payload: a 12-byte iv, at least one byte of ciphertext, a 16-byte tag. */
export const OCP_STATE_MIN_PAYLOAD_BYTES = 29;

/**
 * Every refusal a domain server answers about a state (HTTP 200, `{success: false, error: {code}}`).
 * Opening checks them in this order: size, format, key id, authentication, claims, payload.
 */
export const OCP_STATE_ERROR_CODES = [
  'STATE_TOO_LARGE',
  'STATE_MALFORMED',
  'STATE_KEY_UNKNOWN',
  'STATE_INVALID_SIGNATURE',
  'STATE_WRONG_DOMAIN',
  'STATE_PRINCIPAL_MISMATCH',
  'STATE_SESSION_MISMATCH',
  'STATE_EXPIRED',
  'STATE_INCOMPATIBLE',
  'STATE_NOT_SERIALIZABLE',
] as const;
export type OcpStateErrorCode = (typeof OCP_STATE_ERROR_CODES)[number];

/**
 * Refusals after which the held state can never be opened again (expired, sealed for another
 * version or capability, or under a key the servers no longer hold): a client drops it, and the
 * next call starts the flow over, as a legacy server's lost session did.
 */
export const OCP_STATE_RESET_CODES: readonly OcpStateErrorCode[] = ['STATE_EXPIRED', 'STATE_INCOMPATIBLE', 'STATE_KEY_UNKNOWN'];

export function isOcpStateErrorCode(code: unknown): code is OcpStateErrorCode {
  return typeof code === 'string' && (OCP_STATE_ERROR_CODES as readonly string[]).includes(code);
}

export function isOcpStateResetCode(code: unknown): code is OcpStateErrorCode {
  return typeof code === 'string' && (OCP_STATE_RESET_CODES as readonly string[]).includes(code);
}

const B64U = /^[A-Za-z0-9_-]+$/;
const KID = /^[A-Za-z0-9_-]{1,32}$/;

/** `ocps1.<kid>.<header>.<payload>`: four segments, base64url without padding. */
export const OCP_STATE_TOKEN_PATTERN = /^ocps1\.([A-Za-z0-9_-]{1,32})\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/;

/** The header's keys, in the order a server writes them. */
export const OCP_STATE_HEADER_KEYS = ['dom', 'sv', 'cd', 'sub', 'sid', 'seq', 'by', 'iat', 'exp'] as const;

const epochSeconds = z.number().int().min(0).max(Number.MAX_SAFE_INTEGER);

export const OcpStateHeaderSchema = z
  .object({
    /** Domain id of the server that sealed it. */
    dom: z.string().regex(/^[a-z][a-z0-9-]*$/).max(128),
    /** Version of the domain's session shape (SessionStateAdapter.version). */
    sv: z.number().int().min(1),
    /** The domain's capabilityDigest when it sealed. */
    cd: z.string().regex(/^[0-9a-f]{64}$/),
    /** The caller: base64url SHA-256 of tenant, workspace and user. */
    sub: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
    /** The session_id the state belongs to. */
    sid: z.string().min(1).max(256),
    /** 1 for the first state of a flow, one more for every state after it. */
    seq: z.number().int().min(1).max(Number.MAX_SAFE_INTEGER),
    /** The legacy tool whose call produced it. */
    by: z.string().regex(/^[a-z][a-z0-9_]{0,63}$/),
    iat: epochSeconds,
    exp: epochSeconds,
  })
  .strict()
  .refine((header) => header.exp - header.iat >= OCP_STATE_TTL_SECONDS.min && header.exp - header.iat <= OCP_STATE_TTL_SECONDS.max, {
    message: `exp - iat must be from ${OCP_STATE_TTL_SECONDS.min} to ${OCP_STATE_TTL_SECONDS.max} seconds`,
  });
export type OcpStateHeader = z.infer<typeof OcpStateHeaderSchema>;

/** A token that does not have the ocps1 format (STATE_MALFORMED). Its message never repeats the token. */
export class OcpStateFormatError extends Error {
  readonly code = 'STATE_MALFORMED' as const;

  constructor(reason: string) {
    super(`ocp_state is malformed: ${reason}`);
    this.name = 'OcpStateFormatError';
  }
}

/** The parts of a token, read without any key. Nothing in it is authenticated yet. */
export interface ParsedOcpStateToken {
  kid: string;
  header: OcpStateHeader;
  /** `ocps1.<kid>.<header segment>`, as received: the associated data the payload is sealed with. */
  aad: string;
  /** iv ‖ ciphertext ‖ tag. */
  payload: Uint8Array;
}

/** Strict base64url (no padding, canonical trailing bits) to bytes; null when it is not. */
export function decodeBase64Url(segment: string): Uint8Array | null {
  if (!B64U.test(segment) || segment.length % 4 === 1) return null;
  let binary: string;
  try {
    binary = atob(segment.replace(/-/g, '+').replace(/_/g, '/'));
  } catch {
    return null;
  }
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  // One encoding per byte string: the unused low bits of the last character must be zero.
  return encodeBase64Url(bytes) === segment ? bytes : null;
}

export function encodeBase64Url(bytes: Uint8Array): string {
  let binary = '';
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]!);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * Split a token and read its header: the pattern, the strict header (these keys, this order,
 * compact JSON) and the payload length. Throws OcpStateFormatError; checks no key and no claim.
 */
export function parseOcpStateToken(token: unknown): ParsedOcpStateToken {
  if (typeof token !== 'string') throw new OcpStateFormatError('not a string');
  const match = OCP_STATE_TOKEN_PATTERN.exec(token);
  if (!match) throw new OcpStateFormatError(`not ${OCP_STATE_FORMAT}.<kid>.<header>.<payload>`);
  const [, kid, headerSegment, payloadSegment] = match as unknown as [string, string, string, string];
  if (!KID.test(kid)) throw new OcpStateFormatError('the key id is not valid');
  if (headerSegment.length > OCP_STATE_MAX_HEADER_SEGMENT) throw new OcpStateFormatError('the header is too long');
  const headerBytes = decodeBase64Url(headerSegment);
  if (!headerBytes) throw new OcpStateFormatError('the header is not base64url');
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(headerBytes);
  } catch {
    throw new OcpStateFormatError('the header is not UTF-8');
  }
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new OcpStateFormatError('the header is not JSON');
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new OcpStateFormatError('the header is not an object');
  if (JSON.stringify(Object.keys(raw)) !== JSON.stringify(OCP_STATE_HEADER_KEYS) || JSON.stringify(raw) !== text) {
    throw new OcpStateFormatError('the header is not the compact header of this format');
  }
  const header = OcpStateHeaderSchema.safeParse(raw);
  if (!header.success) throw new OcpStateFormatError(`the header does not follow the schema (${header.error.issues.map((issue) => issue.path.join('.') || 'header').join(', ')})`);
  const payload = decodeBase64Url(payloadSegment);
  if (!payload) throw new OcpStateFormatError('the payload is not base64url');
  if (payload.length < OCP_STATE_MIN_PAYLOAD_BYTES) throw new OcpStateFormatError('the payload is too short');
  return { kid, header: header.data, aad: `${OCP_STATE_FORMAT}.${kid}.${headerSegment}`, payload };
}

/** The header of a token, read without any key (see parseOcpStateToken). */
export function parseOcpStateHeader(token: unknown): OcpStateHeader {
  return parseOcpStateToken(token).header;
}

/**
 * `catalog.stateEnvelope` of a domain manifest: the domain keeps session state as `ocp_state`.
 * `tools` are the legacy tools whose calls return a new state; every tool-backed operation but
 * create_session accepts one.
 */
export const OcpStateEnvelopeCatalogSchema = z
  .object({
    format: z.literal(OCP_STATE_FORMAT),
    argument: z.literal(OCP_STATE_ARGUMENT),
    resultField: z.literal(OCP_STATE_RESULT_FIELD),
    stateVersion: z.number().int().min(1),
    maxBytes: z.number().int().min(OCP_STATE_MAX_BYTES.min).max(OCP_STATE_MAX_BYTES.max),
    ttlSeconds: z.number().int().min(OCP_STATE_TTL_SECONDS.min).max(OCP_STATE_TTL_SECONDS.max),
    tools: z
      .array(z.string().min(1))
      .min(1)
      .refine((tools) => new Set(tools).size === tools.length, { message: 'state tools must be unique' }),
  })
  .strict();
export type OcpStateEnvelopeCatalog = z.infer<typeof OcpStateEnvelopeCatalogSchema>;
