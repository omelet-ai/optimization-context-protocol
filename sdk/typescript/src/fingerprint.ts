import {createHash} from 'node:crypto';

export const ENCODING = 'ocp-json-binary64/1';
export type Fingerprint = {encoding: string; sha256: string};

export function fingerprint(value: unknown): Fingerprint {
  const chunks: Buffer[] = [Buffer.from(ENCODING + '\0')];
  let size = chunks[0].length;
  function emit(data: Buffer) {
    size += data.length;
    if (size > 1048576) throw new Error('FINGERPRINT_TOO_LARGE');
    chunks.push(data);
  }
  function length(tag: string, count: number) {
    const data = Buffer.alloc(5); data.write(tag); data.writeUInt32BE(count, 1); return data;
  }
  function text(value: string) {
    for (const char of value) {
      const code = char.codePointAt(0)!;
      if (code >= 0xd800 && code <= 0xdfff) throw new Error('INVALID_UNICODE');
    }
    const bytes = Buffer.from(value, 'utf8');
    emit(length('s', bytes.length)); emit(bytes);
  }
  function walk(item: unknown, depth = 0) {
    if (depth > 64) throw new Error('FINGERPRINT_TOO_DEEP');
    if (item === null) emit(Buffer.from('n'));
    else if (typeof item === 'boolean') emit(Buffer.from(item ? 't' : 'f'));
    else if (typeof item === 'number') {
      if (!Number.isFinite(item) || Math.abs(item) > Number.MAX_SAFE_INTEGER) throw new Error('UNSAFE_NUMBER');
      const data = Buffer.alloc(9); data.write('d'); data.writeDoubleBE(item === 0 ? 0 : item, 1); emit(data);
    } else if (typeof item === 'string') text(item);
    else if (Array.isArray(item)) {
      if (Object.keys(item).length !== item.length) throw new Error('INVALID_JSON_VALUE');
      emit(length('a', item.length));
      for (const child of item) walk(child, depth + 1);
    } else if (typeof item === 'object' && (Object.getPrototypeOf(item) === Object.prototype || Object.getPrototypeOf(item) === null)) {
      if (Object.getOwnPropertySymbols(item).length) throw new Error('INVALID_JSON_KEY');
      const obj = item as Record<string, unknown>;
      const keys = Object.keys(obj).sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b)));
      emit(length('o', keys.length));
      for (const key of keys) { text(key); walk(obj[key], depth + 1); }
    } else throw new Error('INVALID_JSON_VALUE');
  }
  walk(value);
  return {encoding: ENCODING, sha256: createHash('sha256').update(Buffer.concat(chunks)).digest('hex')};
}
