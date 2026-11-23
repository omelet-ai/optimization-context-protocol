import Ajv2020 from 'ajv/dist/2020';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {fingerprint, Fingerprint} from './fingerprint';

export const KNOWLEDGE_VERSION = '0.1.0-draft.1';
export type KnowledgeItem = {id: string; value: Record<string, unknown>};
export type Knowledge = {
  knowledge_version: string; domain: string; profile: {id: string; version: string};
  catalog_fingerprint: Fingerprint; default_locale: string;
  localizations: Record<string, {title: string; summary: string; aliases: string[]}>;
  sections: Record<'input' | 'objectives' | 'constraints' | 'interpretation', KnowledgeItem[]>;
  required_extensions: string[];
};

// Same packaged schema as Python; no URI retrieval or schema compilation from a host prompt.
const schema = JSON.parse(readFileSync(join(__dirname, 'schemas/knowledge-0.1.schema.json'), 'utf8'));
const valid = new Ajv2020({strict: false}).compile<Knowledge>(schema);
const equal = (a: unknown, b: unknown) => fingerprint(a).sha256 === fingerprint(b).sha256;

export function lintKnowledge(value: unknown, catalog?: Record<string, any>) {
  fingerprint(value);
  if (!valid(value)) throw new Error('INVALID_KNOWLEDGE');
  const bundle = value;
  if (bundle.required_extensions.length) throw new Error('UNSUPPORTED_KNOWLEDGE_EXTENSION');
  if (!Object.hasOwn(bundle.localizations, bundle.default_locale)) throw new Error('MISSING_DEFAULT_LOCALE');
  for (const text of Object.values(bundle.localizations)) {
    const aliases = text.aliases.map(value => value.trim().toLowerCase());
    if (aliases.some(value => !value) || new Set(aliases).size !== aliases.length) throw new Error('DUPLICATE_OR_EMPTY_ALIAS');
  }
  for (const [name, items] of Object.entries(bundle.sections)) {
    if (new Set(items.map(item => item.id)).size !== items.length) throw new Error('DUPLICATE_KNOWLEDGE_ID');
    if (name === 'objectives' || name === 'constraints') for (const item of items) {
      const fields = name === 'objectives' ? ['id', 'definition', 'unit', 'direction', 'role'] : ['id', 'definition', 'unit', 'kind', 'role'];
      if (fields.some(key => typeof item.value[key] !== 'string' || !item.value[key])) throw new Error('INCOMPLETE_METRIC_SEMANTICS');
      if (item.id !== item.value.id) throw new Error('KNOWLEDGE_ID_MISMATCH');
      if (name === 'objectives' && !['minimize', 'maximize'].includes(item.value.direction as string)) throw new Error('INVALID_OBJECTIVE_DIRECTION');
    }
  }
  if (catalog) {
    if (!equal(bundle.catalog_fingerprint, fingerprint(catalog)) || !equal(bundle.profile, catalog.domainProfile)) throw new Error('KNOWLEDGE_CATALOG_MISMATCH');
    const expected = {
      input: [['schema', 'input_schema'], ['template', 'requestTemplate'], ['configuration', 'configurationSchema'], ['defaults', 'defaults']].map(([id, key]) => ({id, value: catalog[key]})),
      objectives: catalog.objectives.map((value: any) => ({id: value.id, value})),
      constraints: catalog.constraints.map((value: any) => ({id: value.id, value})),
      interpretation: [{id: 'result', value: catalog.resultSemantics}, {id: 'scope', value: {
        profile_semantics: catalog.profile_semantics, provider_limitations: catalog.providerLimitations, execution: catalog.execution}}]
    };
    if (!equal(bundle.sections, expected)) throw new Error('KNOWLEDGE_PROJECTION_DRIFT');
  }
  return {status: 'PASS', scope: 'Knowledge structure and semantics' + (catalog ? ' with authoritative catalog projection' : '; catalog agreement not checked')};
}
