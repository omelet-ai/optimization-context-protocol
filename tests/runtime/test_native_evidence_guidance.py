"""Installed-only regressions for the four observed 0.3 host explanation errors."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest

from mcp import Client as MCPClient, StdioServerParameters
from conformance.assessment import assess
from foundry_capability_contract import MemoryJobStore
from ocp_candidate import Client
from ocp_candidate.native import NativeError
from ocp_runtime.native_domain import ReferenceDomain
from ocp_runtime.native_evidence import EvidenceService
from ocp_runtime.native_evidence_guidance import input_policy, constraint_scope, comparison_inputs
from ocp_runtime.providers import make_provider


def domain(profile):
    return ReferenceDomain(make_provider(profile), problem_type=profile.replace('.', '-'))


def invalid_examples(inputs):
    worker = deepcopy(inputs['worker.scheduling'])
    worker['tasks'][0]['allowed_start_times'] = [0, 30]
    inventory = deepcopy(inputs['inventory.replenishment'])
    inventory['products'][0]['quantity_discount'] = {'minimum_quantity': 3, 'unit_cost': 0}
    return [('worker.scheduling', worker), ('inventory.replenishment', inventory)]


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.inputs = json.loads(Path('inputs.json').read_text())

    def test_no_selected_domain_makes_no_profile_claim(self):
        self.assertEqual(input_policy(None)['status'], 'SELECT_DOMAIN')
        self.assertIsNone(constraint_scope(None)['intrinsic_rules'])

    def test_closed_locations_do_not_treat_data_as_schema(self):
        schema = {'additionalProperties': False,
                  'properties': {'a/b~c': {'type': 'object', 'additionalProperties': False},
                                 'additionalProperties': {'const': False},
                                 'open': {'type': 'object', 'additionalProperties': {'type': 'integer'}}},
                  'default': {'additionalProperties': False},
                  'examples': [{'additionalProperties': False}],
                  'const': {'additionalProperties': False},
                  '$defs': {'closed': {'additionalProperties': False}},
                  'items': {'$ref': '#/$defs/closed'}}
        self.assertEqual(input_policy({'input_schema': schema})['schema_rules']['closed_object_schema_locations'],
                         ['#', '#/properties/a~1b~0c', '#/$defs/closed'])

    def test_closed_and_dynamic_objects_remain_distinct(self):
        catalog = domain('worker.scheduling').capabilities()
        before = deepcopy(catalog)
        paths = input_policy(catalog)['schema_rules']['closed_object_schema_locations']
        self.assertIn('#/properties/tasks/items', paths)
        self.assertNotIn('#/properties/tasks/items/properties/costs', paths)
        self.assertEqual(catalog, before)

    def test_routing_config_is_not_the_entire_constraint_set(self):
        facts = constraint_scope(domain('routing.basic').capabilities())
        self.assertEqual(facts['configuration_entries'], ['weight_capacity'])
        self.assertEqual(facts['fixed_selection'], ['weight_capacity'])
        self.assertEqual(facts['selection_mode'], 'FIXED_BY_SCHEMA')
        self.assertIn('all_visits_once', [r['id'] for r in facts['declared_constraints']])
        self.assertEqual([r['id'] for r in facts['intrinsic_rules']], ['all_visits_once', 'closed_depot_routes'])

    def test_other_reference_profiles_have_their_own_rules(self):
        for profile, rule in [('worker.scheduling', 'fixed_task_intervals'),
                              ('inventory.replenishment', 'arrivals_before_demand')]:
            facts = constraint_scope(domain(profile).capabilities())
            self.assertEqual(facts['selection_mode'], 'FIXED_BY_SCHEMA')
            self.assertIn(rule, [r['id'] for r in facts['intrinsic_rules']])
            self.assertNotIn('closed_depot_routes', [r['id'] for r in facts['intrinsic_rules']])

    def test_drifted_profile_context_does_not_inherit_rules(self):
        original = domain('routing.basic').capabilities()
        for key in ('input_schema', 'solution_schema', 'profile_semantics', 'domainProfile'):
            catalog = deepcopy(original)
            if key.endswith('schema'):
                catalog[key]['description'] = 'Changed context with the same schema ID'
            elif key == 'profile_semantics':
                catalog[key] = ['Different meaning']
            else:
                catalog[key]['version'] = '99.0.0'
            facts = constraint_scope(catalog)
            self.assertEqual(facts['intrinsic_rules_status'], 'NOT_SUMMARIZED')
            self.assertIsNone(facts['intrinsic_rules'])

    def test_configurable_extension_is_not_reported_as_fixed(self):
        facts = constraint_scope({'domainProfile': {'id': 'custom', 'version': '1'},
                                  'defaults': {'constraints': ['limit']},
                                  'configurationSchema': {'properties': {'constraints': {'type': 'array'}}}})
        self.assertEqual(facts['selection_mode'], 'CONSULT_CONFIGURATION_SCHEMA')
        self.assertIsNone(facts['fixed_selection'])
        self.assertIsNone(facts['intrinsic_rules'])

    def test_rejected_fields_are_not_silently_dropped_or_submitted(self):
        for profile, data in invalid_examples(self.inputs):
            client = domain(profile)
            calls = []
            client.submit = lambda *args, **kw: calls.append((args, kw))
            service = EvidenceService({'selected': client}, MemoryJobStore())
            request = Client(client.provider).request(data, request_id='invalid-field')
            before = deepcopy(request)
            validation = service.validate('selected', request, tenant='owner')
            self.assertFalse(validation['valid'])
            self.assertTrue(validation['issues'])
            with self.assertRaisesRegex(NativeError, 'INVALID_PROBLEM'):
                service.submit('selected', request, tenant='owner', idempotency_key='bad')
            self.assertEqual(calls, [])
            self.assertEqual(request, before)

    def test_route_checks_include_visits_and_depot_cost(self):
        client = domain('routing.basic')
        request = Client(client.provider).request(self.inputs['routing.basic'], request_id='intrinsic')
        result = client.provider.execute(request)
        self.assertEqual(assess(request, result)['status'], 'PASS')
        matrix = request['input']['matrix']
        lookup = {name: i for i, name in enumerate(matrix['node_ids'])}
        total = 0
        for route in result['solution']['routes']:
            nodes = [request['input']['depot'], *route['visits'], request['input']['depot']]
            total += sum(matrix['values'][lookup[a]][lookup[b]] for a, b in zip(nodes, nodes[1:]))
        self.assertEqual(result['metrics'][0]['value'], total)
        missing = deepcopy(result)
        missing['solution']['routes'][0]['visits'].pop()
        self.assertEqual(assess(request, missing)['status'], 'FAIL')

    def test_baseline_assignment_is_not_a_problem_request(self):
        client = domain('routing.basic')
        request = Client(client.provider).request(self.inputs['routing.basic'], request_id='baseline')
        result = client.provider.execute(request)
        self.assertFalse(client.validate(result['solution'])['valid'])
        with_solution = deepcopy(request); with_solution['solution'] = result['solution']
        self.assertFalse(client.validate(with_solution)['valid'])
        guidance = comparison_inputs()
        self.assertFalse(guidance['supplied_solution_accepted'])
        self.assertEqual(guidance['explain_accepts']['baseline'], 'baseline_job_id')
        self.assertIn('reoptimizes', guidance['supplied_assignment'])

    def test_returned_guidance_is_not_shared_mutable_state(self):
        catalog = domain('routing.basic').capabilities()
        facts = constraint_scope(catalog)
        facts['intrinsic_rules'][0]['id'] = 'changed'
        facts['configuration_entries'].clear()
        self.assertEqual(constraint_scope(catalog)['intrinsic_rules'][0]['id'], 'all_visits_once')
        self.assertEqual(catalog['defaults']['constraints'], ['weight_capacity'])

    def test_actual_mcp_rejects_then_accepts_same_key(self):
        asyncio.run(self.mcp_rejections())

    async def mcp_rejections(self):
        params = StdioServerParameters(command=sys.executable,
            args=['-I', '-B', '-m', 'ocp_runtime.native_mcp', '--verification', '--evidence'],
            env={'PATH': os.defpath, 'HOME': os.environ['HOME'], 'PYTHONDONTWRITEBYTECODE': '1'})
        records = []
        examples = invalid_examples(self.inputs) + [('routing.basic', {'routes': []})]
        async with MCPClient(params, read_timeout_seconds=90) as host:
            for profile, bad_input in examples:
                name = profile.replace('.', '-')
                context = (await host.call_tool('ocp_native_context', {'domain': name})).structured_content
                self.assertEqual(context['evidence']['version'], '0.5.0')
                problem = deepcopy(context['catalog']['requestTemplate'])
                problem.update(input=bad_input, request_id='reject-'+name)
                if profile == 'routing.basic':
                    problem = bad_input  # Supplied solution alone, not a problem.
                checked = await host.call_tool('ocp_native_validate', {'domain': name, 'problem': problem})
                self.assertFalse(checked.is_error)
                self.assertFalse(checked.structured_content['valid'])
                refused = await host.call_tool('ocp_native_submit', {
                    'domain': name, 'problem': problem, 'idempotency_key': 'rejection-'+name})
                self.assertTrue(refused.is_error)
                self.assertEqual(refused.structured_content['code'], 'INVALID_PROBLEM')
                self.assertNotIn('job', refused.structured_content)
                valid = deepcopy(context['catalog']['requestTemplate'])
                valid.update(input=self.inputs[profile], request_id='valid-'+name)
                accepted = await host.call_tool('ocp_native_submit', {
                    'domain': name, 'problem': valid, 'idempotency_key': 'rejection-'+name})
                self.assertFalse(accepted.is_error, accepted.structured_content)
                self.assertFalse(accepted.structured_content['replayed'])
                records.append({'profile': profile, 'validation': checked.structured_content,
                                'rejection': refused.structured_content, 'accepted': accepted.structured_content})
        Path('evidence-guidance-mcp.json').write_text(json.dumps(records, indent=2)+'\n')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    summary = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': len(result.skipped), 'model_calls': 0, 'scope': 'Installed evidence guidance and actual stdio regressions'}
    Path('evidence-guidance-test-result.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))
    raise SystemExit(not result.wasSuccessful())
