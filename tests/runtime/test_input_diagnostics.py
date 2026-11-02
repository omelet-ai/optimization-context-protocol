"""Installed-consumer checks for actionable, value-safe validation issues."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from ocp_candidate import Client
from ocp_candidate.contract import OCPError, validate
from ocp_candidate.native import native_validate
from ocp_runtime.native_domain import ReferenceDomain
from ocp_runtime.providers import make_provider

INPUTS = json.loads(Path('inputs.json').read_text())


class InputDiagnostics(unittest.TestCase):
    def check_issue(self, profile, mutate, path, text, code='INVALID_REQUEST'):
        provider = make_provider(profile)
        request = Client(provider).request(deepcopy(INPUTS[profile]), request_id='diagnostic')
        mutate(request)
        original = deepcopy(request)
        core = provider.validate(request)
        self.assertFalse(core['valid'])
        self.assertEqual(core['issues'][0]['path'], path)
        self.assertEqual(core['issues'][0]['code'], code)
        self.assertIn(text, core['issues'][0]['message'])
        native = ReferenceDomain(provider, problem_type='diagnostic').validate(request)
        native_validate('Validation', native)
        self.assertFalse(native['valid'])
        self.assertEqual(native['issues'][0]['fieldPath'], path)
        self.assertEqual(native['issues'][0]['code'], code)
        self.assertEqual(native['issues'][0]['message'], core['issues'][0]['message'])
        self.assertEqual(request, original, 'Validation must never repair supplied input')

    def test_missing_nested_field(self):
        self.check_issue('worker.scheduling', lambda r: r['input']['tasks'][0].pop('end'),
                         '/tasks/0/end', 'Required field')

    def test_unsupported_rule(self):
        self.check_issue('worker.scheduling', lambda r: r['input'].update(breaks=[]),
                         '/breaks', 'preserve the requirement')

    def test_missing_matrix(self):
        self.check_issue('routing.basic', lambda r: r['input'].pop('matrix'),
                         '/matrix', 'Required field', 'INVALID_DATA')

    def test_missing_inventory_unit(self):
        self.check_issue('inventory.replenishment', lambda r: r['input'].pop('quantity_unit'),
                         '/quantity_unit', 'Required field')

    def test_missing_envelope_field(self):
        provider = make_provider('worker.scheduling')
        request = Client(provider).request(deepcopy(INPUTS['worker.scheduling']), request_id='envelope')
        del request['budget']
        report = ReferenceDomain(provider, problem_type='diagnostic').validate(request)
        self.assertFalse(report['valid'])
        self.assertEqual(report['issues'][0]['fieldPath'], '/budget')
        self.assertIn('Required field', report['issues'][0]['message'])

    def test_wrong_type_does_not_echo_value(self):
        secret = 'a-sensitive-value-that-must-not-appear'
        provider = make_provider('worker.scheduling')
        request = Client(provider).request(deepcopy(INPUTS['worker.scheduling']), request_id='type')
        request['input']['workers'][0]['max_minutes'] = secret
        report = provider.validate(request)
        self.assertFalse(report['valid'])
        self.assertEqual(report['issues'][0]['path'], '/workers/0/max_minutes')
        self.assertIn('wrong type', report['issues'][0]['message'])
        self.assertNotIn(secret, json.dumps(report))

    def test_json_pointer_escapes_extra_field(self):
        self.check_issue('worker.scheduling', lambda r: r['input']['tasks'][0].update({'x/y~z': 1}),
                         '/tasks/0/x~1y~0z', 'not supported')

    def test_missing_and_extra_costs(self):
        def missing(request):
            task = request['input']['tasks'][0]
            task['costs'].pop('alice')
        self.check_issue('worker.scheduling', missing, '/tasks/0/costs/alice',
                         'ask for this value', 'INVALID_ELIGIBILITY')
        self.check_issue('worker.scheduling', lambda r: r['input']['tasks'][0]['costs'].update({'x/y~z': 3}),
                         '/tasks/0/costs/x~1y~0z', 'ineligible worker', 'INVALID_ELIGIBILITY')

    def test_wrong_units_and_bounds(self):
        self.check_issue('worker.scheduling', lambda r: r['input'].update(time_unit='hour'),
                         '/time_unit', 'declared choices')
        self.check_issue('worker.scheduling', lambda r: r['input']['workers'][0].update(max_minutes=-1),
                         '/workers/0/max_minutes', 'numeric bounds')

    def test_caller_error_code_is_preserved(self):
        with self.assertRaises(OCPError) as caught:
            validate('worker-scheduling-solution', {}, code='INVALID_SOLUTION')
        self.assertEqual(caught.exception.code, 'INVALID_SOLUTION')
        self.assertEqual(caught.exception.path, '/assignments')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InputDiagnostics))
    print(json.dumps({'status': 'PASS' if result.wasSuccessful() else 'FAIL',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'scope': 'Installed Core and native Python consumers; no model calls'}))
    raise SystemExit(not result.wasSuccessful())
