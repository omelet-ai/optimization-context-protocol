"""Optional, offline Knowledge projection. Execution catalogs remain authoritative."""
from copy import deepcopy
from .contract import validate
from .fingerprint import fingerprint

VERSION = '0.1.0-draft.1'
SECTIONS = ('input', 'objectives', 'constraints', 'interpretation')


def project(domain, catalog, localizations=None):
    """Build descriptive data, never a second solver/capability declaration."""
    reference = catalog['domainProfile']
    texts = localizations or {'en': {'title': reference['id'],
        'summary': 'Read the input schema, objectives and limits before preparing this problem.', 'aliases': []}}
    bundle = {'knowledge_version': VERSION, 'domain': domain,
        'profile': deepcopy(reference), 'catalog_fingerprint': fingerprint(catalog),
        'default_locale': 'en', 'localizations': deepcopy(texts),
        'sections': {
            'input': [{'id': name, 'value': deepcopy(catalog[key])} for name, key in (
                ('schema', 'input_schema'), ('template', 'requestTemplate'),
                ('configuration', 'configurationSchema'), ('defaults', 'defaults'))],
            'objectives': [{'id': value['id'], 'value': deepcopy(value)} for value in catalog['objectives']],
            'constraints': [{'id': value['id'], 'value': deepcopy(value)} for value in catalog['constraints']],
            'interpretation': [{'id': 'result', 'value': deepcopy(catalog['resultSemantics'])},
                {'id': 'scope', 'value': {'profile_semantics': deepcopy(catalog['profile_semantics']),
                    'provider_limitations': deepcopy(catalog['providerLimitations']),
                    'execution': deepcopy(catalog['execution'])}}]},
        'required_extensions': []}
    lint(bundle, catalog=catalog)
    return bundle


def lint(bundle, *, catalog=None):
    fingerprint(bundle)  # bounded, portable JSON before traversing an author file
    validate('knowledge', bundle, 'INVALID_KNOWLEDGE')
    if bundle['required_extensions']:
        raise ValueError('UNSUPPORTED_KNOWLEDGE_EXTENSION')
    if bundle['default_locale'] not in bundle['localizations']:
        raise ValueError('MISSING_DEFAULT_LOCALE')
    for text in bundle['localizations'].values():
        aliases = [value.strip().lower() for value in text['aliases']]
        if any(not value for value in aliases) or len(set(aliases)) != len(aliases):
            raise ValueError('DUPLICATE_OR_EMPTY_ALIAS')
    for name, items in bundle['sections'].items():
        ids = [item['id'] for item in items]
        if len(set(ids)) != len(ids):
            raise ValueError('DUPLICATE_KNOWLEDGE_ID')
        if name in ('objectives', 'constraints'):
            for item in items:
                value = item['value']
                required = ('id', 'definition', 'unit', 'direction', 'role') if name == 'objectives' else ('id', 'definition', 'unit', 'kind', 'role')
                if any(not isinstance(value.get(key), str) or not value[key] for key in required):
                    raise ValueError('INCOMPLETE_METRIC_SEMANTICS')
                if item['id'] != value['id']:
                    raise ValueError('KNOWLEDGE_ID_MISMATCH')
                if name == 'objectives' and value['direction'] not in ('minimize', 'maximize'):
                    raise ValueError('INVALID_OBJECTIVE_DIRECTION')
    if catalog is not None:
        if bundle['catalog_fingerprint'] != fingerprint(catalog) or bundle['profile'] != catalog['domainProfile']:
            raise ValueError('KNOWLEDGE_CATALOG_MISMATCH')
        expected = {
            'input': [{'id': name, 'value': catalog[key]} for name, key in (
                ('schema', 'input_schema'), ('template', 'requestTemplate'),
                ('configuration', 'configurationSchema'), ('defaults', 'defaults'))],
            'objectives': [{'id': v['id'], 'value': v} for v in catalog['objectives']],
            'constraints': [{'id': v['id'], 'value': v} for v in catalog['constraints']],
            'interpretation': [{'id': 'result', 'value': catalog['resultSemantics']},
                {'id': 'scope', 'value': {'profile_semantics': catalog['profile_semantics'],
                    'provider_limitations': catalog['providerLimitations'], 'execution': catalog['execution']}}]}
        if fingerprint(bundle['sections']) != fingerprint(expected):
            raise ValueError('KNOWLEDGE_PROJECTION_DRIFT')
    return {'status': 'PASS', 'scope': 'Knowledge structure and semantics' +
            (' with authoritative catalog projection' if catalog is not None else '; catalog agreement not checked')}
