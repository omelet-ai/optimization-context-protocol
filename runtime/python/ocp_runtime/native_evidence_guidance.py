"""Read-only host guidance derived from the selected catalog and MCP binding.

Schema declarations describe required validation, not proof of provider behavior.
Built-in rule summaries apply only to matching packaged profile context.
"""
from copy import deepcopy


def _closed_objects(schema):
    """Locate declarations, not data paths; do not interpret examples or defaults."""
    paths = []

    def token(value):
        return str(value).replace('~', '~0').replace('/', '~1')

    def walk(node, path):
        if not isinstance(node, dict):
            return
        if node.get('additionalProperties') is False:
            paths.append(path)
        for key in ('properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'):
            for name, child in node.get(key, {}).items():
                walk(child, path + '/' + key + '/' + token(name))
        for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
            for index, child in enumerate(node.get(key, [])):
                walk(child, path + '/' + key + '/' + str(index))
        for key in ('items', 'contains', 'additionalProperties', 'unevaluatedProperties',
                    'unevaluatedItems', 'propertyNames', 'not', 'if', 'then', 'else'):
            walk(node.get(key), path + '/' + key)

    walk(schema, '#')
    return paths


def input_policy(catalog):
    return {
        'scope': 'Selected provider schema and validation, before native MCP submission.',
        'status': 'SELECT_DOMAIN' if catalog is None else 'SELECTED_CATALOG',
        'missing_required_data': 'ASK_USER',
        'invalid_request': 'REJECT_BEFORE_JOB_CREATION',
        'unsupported_required_goal': 'ASK_FOR_SUPPORTED_PROFILE_OR_EXPLICIT_SCOPE_CHANGE',
        'silent_field_dropping': False,
        'schema_rules': {
            'source': 'catalog.input_schema',
            'disallowed_extra_fields': 'REJECT; do not describe them as ignored or possibly ignored.',
            'closed_object_schema_locations': _closed_objects((catalog or {}).get('input_schema')),
            'location_format': 'JSON Pointer fragments into the schema, not request field paths.',
            'coverage': 'additionalProperties:false declarations only; apply the entire schema, including refs and conditions. '
                        'Other objects may allow extra keys; use the selected schema and returned validation issues.'},
        'enforcement': 'The evidence submit path revalidates the exact problem through the provider; '
                       'valid:false prevents submission. These declarations do not certify an arbitrary provider.'}


_RULES = {
    ('routing.basic', '0.1.0'): [
        {'id': 'all_visits_once', 'meaning': 'Every supplied visit occurs exactly once.'},
        {'id': 'closed_depot_routes', 'meaning': 'Vehicle routes start and end at the declared depot.'}],
    ('worker.scheduling', '0.1.0'): [
        {'id': 'fixed_task_intervals', 'meaning': 'Task start and end are supplied fixed times, not decision variables.'},
        {'id': 'half_open_intervals', 'meaning': 'Intervals are [start,end); adjacent tasks do not overlap.'}],
    ('inventory.replenishment', '0.1.0'): [
        {'id': 'deterministic_demand', 'meaning': 'Supplied demand is used directly, not forecast from history.'},
        {'id': 'arrivals_before_demand', 'meaning': 'Receipts and due orders arrive before demand in each period.'},
        {'id': 'no_late_orders', 'meaning': 'Orders arriving after the horizon must be zero.'}]
}


def _packaged_rules(catalog):
    from ocp_candidate.contract import OCPError
    from ocp_candidate.profiles import packaged_registry
    profile = catalog.get('domainProfile', {})
    key = (profile.get('id'), profile.get('version'))
    if key not in _RULES:
        return None
    try:
        expected = packaged_registry().resolve({
            'domain_profile': profile, 'input_schema_id': catalog['input_schema']['$id'],
            'solution_schema_id': catalog['solution_schema']['$id']})
    except (OCPError, KeyError):
        return None
    if any(catalog.get(name) != value for name, value in expected.items()):
        return None
    return deepcopy(_RULES[key])


def constraint_scope(catalog):
    if catalog is None:
        return {'status': 'SELECT_DOMAIN', 'configuration_entries': None, 'intrinsic_rules': None}
    schema = catalog.get('configurationSchema', {})
    config = schema.get('properties', {}).get('constraints', {})
    if isinstance(schema.get('const'), dict) and 'constraints' in schema['const']:
        config = {'const': schema['const']['constraints']}
    rules = _packaged_rules(catalog)
    return {
        'status': 'SELECTED_CATALOG',
        'configuration_entries': deepcopy(catalog.get('defaults', {}).get('constraints')),
        'configuration_source': 'catalog.defaults.constraints and catalog.configurationSchema',
        'declared_constraints': deepcopy(catalog.get('constraints')),
        'declared_constraints_source': 'catalog.constraints (includes intrinsic constraints when advertised)',
        'selection_mode': 'FIXED_BY_SCHEMA' if 'const' in config else 'CONSULT_CONFIGURATION_SCHEMA',
        'fixed_selection': deepcopy(config.get('const')),
        'intrinsic_rules_status': 'PACKAGED_PROFILE_SUMMARY' if rules is not None else 'NOT_SUMMARIZED',
        'intrinsic_rules': rules,
        'profile_semantics_source': 'catalog.profile_semantics',
        'scope': 'Configuration entries are not an exhaustive list of profile rules. '
                 'Intrinsic rules are part of the versioned profile, not optional configuration switches. '
                 'The summary is partial; consult schemas and profile semantics. '
                 'NOT_SUMMARIZED does not mean there are no intrinsic rules. '
                 'Actual result checks are reported separately by independent verification.'}


def comparison_inputs():
    return {
        'scope': 'This native MCP submit/explain binding; other OCP bindings may support other inputs.',
        'submit_accepts': 'FULL_PROBLEM_REQUEST_FROM_CATALOG_TEMPLATE',
        'explain_accepts': {'current': 'job_id', 'baseline': 'baseline_job_id'},
        'supplied_solution_accepted': False,
        'existing_baseline': 'Use a completed baseline_job_id in the same tenant/domain with its stored problem and result.',
        'new_baseline': ['Obtain a complete baseline problem representable by the selected profile.',
                         'Validate and submit that problem, preserving its requirements.',
                         'Wait for completion, then explain using both stored job IDs.'],
        'supplied_assignment': 'An assignment or plan alone is not a baseline problem. '
                               'Submitting a new problem reoptimizes it; it does not evaluate that supplied plan. '
                               'Ask for a supported evaluation path when that exact plan must be checked.',
        'comparison_guards': ['matching domain_profile, execution_profile and configuration',
                              'matching objective definition and unit', 'two independently checked non-null objectives'],
        'difference_meaning': 'current minus baseline; an arithmetic comparison, not a causal savings claim.'}
