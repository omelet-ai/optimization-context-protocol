/** Domain-neutral descriptor validation; independent port of the Python rules. */
import Ajv2020 from 'ajv/dist/2020.js';
import {fingerprint} from './fingerprint.js';

export const FORMAT_VERSION = '0.1.0-draft.2';
type Document = Record<string, any>;
function reject(code: string): never { throw new Error(code); }
function tokens(pointer: string): string[] {
  if (typeof pointer !== 'string' || (pointer && !pointer.startsWith('/')) || /~(?![01])/.test(pointer)) reject('POINTER_INVALID');
  return pointer === '' ? [] : pointer.slice(1).split('/').map(x => x.replace(/~1/g, '/').replace(/~0/g, '~'));
}
export function at(value: any, pointer: string): any {
  for (const key of tokens(pointer)) {
    if (Array.isArray(value) && !/^(0|[1-9][0-9]*)$/.test(key)) reject('POINTER_MISSING');
    if (value === null || typeof value !== 'object' || !Object.hasOwn(value, key)) reject('POINTER_MISSING');
    value = value[key];
  }
  return value;
}
function schemaAt(schema: any, pointer: string): any {
  function resolve(value: any) {
    const seen = new Set<string>();
    while (value && typeof value === 'object' && '$ref' in value) {
      if (seen.has(value.$ref)) reject('SCHEMA_REFERENCE_CYCLE');
      seen.add(value.$ref); value = at(schema, value.$ref.slice(1));
    }
    return value;
  }
  let value = schema;
  for (const key of tokens(pointer)) {
    value = resolve(value);
    if (value?.properties && Object.hasOwn(value.properties, key)) value = value.properties[key];
    else if (value?.type === 'array' && /^(0|[1-9][0-9]*)$/.test(key)) value = value.items ?? {};
    else reject('POINTER_MISSING');
  }
  return resolve(value);
}
function* objects(value: any): Generator<Document> {
  if (value && typeof value === 'object') {
    if (!Array.isArray(value)) yield value;
    for (const child of Object.values(value)) yield* objects(child);
  }
}
function equal(a: any, b: any): boolean {
  if (a === b) return true;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object' || Array.isArray(a) !== Array.isArray(b)) return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(k => Object.hasOwn(b, k) && equal(a[k], b[k]));
}
function portable(value: any): void {
  fingerprint(value);
}
function validator() { return new Ajv2020({strict: false, allErrors: false, validateFormats: false}); }
function check(schema: any, value: any) {
  if (!validator().compile(schema)(value)) reject('SCHEMA_INVALID');
}
export function requireReference(expected: any, actual: any): void {
  if (!equal(expected, actual)) reject('REFERENCE_MISMATCH');
}
function localSchema(schema: any) {
  if (!validator().validateSchema(schema)) reject('SCHEMA_DEFINITION_INVALID');
  for (const node of objects(schema)) {
    if ('$id' in node && node !== schema) reject('NESTED_SCHEMA_ID_UNSUPPORTED');
    for (const key of ['$ref', '$dynamicRef']) if (key in node) {
      if (typeof node[key] !== 'string' || !node[key].startsWith('#/')) reject('EXTERNAL_SCHEMA_REFERENCE_UNSUPPORTED');
      at(schema, node[key].slice(1));
    }
  }
}
export function lintPackage(document: Document, descriptorSchema: object, apiContract?: Document, supportedExtensions: string[] = []) {
  portable(document);
  check(descriptorSchema, document);
  if (document.required_extensions.some((x: string) => !supportedExtensions.includes(x))) reject('REQUIRED_EXTENSION_UNSUPPORTED');
  if (document.required_extensions.some((x: string) => !Object.hasOwn(document.extensions, x))) reject('REQUIRED_EXTENSION_MISSING');
  if (!Object.hasOwn(document.localizations, document.default_locale)) reject('DEFAULT_LOCALE_MISSING');
  const {api, schemas} = document;
  for (const key of ['input', 'configuration', 'result']) if (!Object.hasOwn(schemas, api[key + '_schema'])) reject('SCHEMA_REFERENCE_MISSING');
  for (const schema of Object.values(schemas) as any[]) {
    localSchema(schema);
  }
  for (const items of [document.bindings, document.metrics, document.input_formats, document.playbooks,
                       document.capabilities.objectives, document.capabilities.constraints]) {
    if (new Set(items.map((x: any) => x.id)).size !== items.length) reject('DUPLICATE_ID');
  }
  const configSchema = schemas[api.configuration_schema];
  const partial = structuredClone(configSchema); if (typeof partial === 'object') delete partial.required;
  check(partial, document.configuration_defaults);
  for (const item of [...document.metrics, ...document.capabilities.objectives, ...document.capabilities.constraints]) {
    if (item.unit !== null && !Object.hasOwn(document.units, item.unit)) reject('UNIT_UNDECLARED');
  }
  const bindings = new Map<string, any>(document.bindings.map((b: any) => [b.id, b]));
  for (const b of bindings.values()) {
    const field = schemaAt(schemas[api[b.target + '_schema']], b.pointer);
    if (b.operation === 'select_by_id' && field?.type !== 'array') reject('SELECTION_REQUIRES_ARRAY');
    localSchema(b.value_schema);
  }
  for (const m of document.metrics) schemaAt(schemas[api.result_schema], m.pointer);
  for (const rule of document.configuration_rules) schemaAt(configSchema, rule.pointer);
  for (const o of document.capabilities.objectives) if (o.weight_binding != null && !bindings.has(o.weight_binding)) reject('BINDING_MISSING');
  const metrics = new Set(document.metrics.map((m: any) => m.id));
  for (const p of document.playbooks) {
    if (p.binding_ids.some((x: string) => !bindings.has(x)) || p.metric_ids.some((x: string) => !metrics.has(x))) reject('PLAYBOOK_REFERENCE_MISSING');
    for (const keep of p.preserve) schemaAt(schemas[api[keep.target + '_schema']], keep.pointer);
  }
  if (apiContract) for (const key of ['api', 'schemas', 'capabilities']) requireReference(document[key], apiContract[key]);
  return {status: 'PASS', scope: 'descriptor_structure_and_semantics', api_agreement_checked: !!apiContract};
}
export function validateRequest(document: Document, input: any, configuration: Document) {
  portable(input); portable(configuration);
  if (configuration === null || typeof configuration !== 'object' || Array.isArray(configuration)) reject('SCHEMA_INVALID');
  const effective = {...structuredClone(document.configuration_defaults), ...structuredClone(configuration)};
  check(document.schemas[document.api.input_schema], input);
  check(document.schemas[document.api.configuration_schema], effective);
  for (const rule of document.configuration_rules) {
    const value = at(effective, rule.pointer);
    if (rule.kind === 'allowed_set' && (!Array.isArray(value) || new Set(value).size !== value.length ||
        !rule.values.some((v: any[]) => v.length === value.length && v.every(x => value.includes(x))))) reject('CONFIGURATION_COMBINATION_UNSUPPORTED');
  }
  return effective;
}
