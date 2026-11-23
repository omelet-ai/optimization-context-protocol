"""CSV preparation must preserve units/zeroes and reject missing or ambiguous data."""
import unittest
import json
import sys
from ocp_candidate.contract import OCPError
from ocp_runtime.coordinate_input import coordinates_from_csv

DEPOT = 'id,latitude,longitude\ndepot,37.5,127\n'
VISITS = 'id,latitude,longitude,demand_kg\na,37.51,127.01,0\nb,37.52,127.02,10\n'
VEHICLES = 'id,capacity_kg\na,20\nb,20\n'


class CoordinatesCSV(unittest.TestCase):
    def data(self, depot=DEPOT, visits=VISITS, vehicles=VEHICLES, model='haversine'):
        return coordinates_from_csv(depot, visits, vehicles, distance_model=model)

    def test_valid_values_zero_units_and_rounding(self):
        data = self.data()
        self.assertEqual(data['visits'][0]['demand'], 0)
        self.assertEqual(data['distance'], {'model': 'haversine', 'earth_radius_m': 6371000, 'rounding': 'ceil', 'unit': 'meter'})
        self.assertEqual(data['vehicles'][0], {'id': 'a', 'capacity': 20})

    def test_missing_and_unknown_column(self):
        for text in (VISITS.replace(',demand_kg', ''), VISITS.replace('demand_kg', 'demand'),
                     VISITS.replace('demand_kg', 'demand_kg,time_window'), VISITS.replace('demand_kg', 'id')):
            with self.subTest(text=text), self.assertRaises(ValueError): self.data(visits=text)

    def test_missing_value_and_extra_field(self):
        for text in (VISITS.replace('127.01,0', '127.01,'), VISITS.replace('127.01,0', '127.01'),
                     VISITS.replace('127.01,0', '127.01,0,extra')):
            with self.subTest(text=text), self.assertRaises(ValueError): self.data(visits=text)

    def test_fractional_negative_and_null_mass(self):
        for value in ('1.5', '-1', 'null', '1e2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.data(visits=VISITS.replace('127.01,0', '127.01,' + value))

    def test_nonfinite_and_out_of_range_coordinate(self):
        for value in ('nan', 'inf', '91', '-91', 'Seoul'):
            with self.subTest(value=value), self.assertRaises(ValueError): self.data(depot=DEPOT.replace('37.5', value))

    def test_duplicate_ids_and_whitespace(self):
        for text in (VISITS.replace('\nb,', '\na,'), VISITS.replace('\nb,', '\n b,')):
            with self.subTest(text=text), self.assertRaises(ValueError): self.data(visits=text)

    def test_existing_profile_bounds(self):
        with self.assertRaises(OCPError): self.data(vehicles='id,capacity_kg\na,20\n')
        with self.assertRaises(ValueError): self.data(depot=DEPOT + 'other,37.5,127\n')
        with self.assertRaises(ValueError): self.data(model='road')

    def test_size_bound(self):
        with self.assertRaises(ValueError): self.data(visits=VISITS + 'x' * 65536)

    def test_malformed_csv_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, 'CSV_MALFORMED'):
            self.data(visits='id,latitude,longitude,demand_kg\n"unfinished')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print(json.dumps({'tests_run': result.testsRun, 'errors': len(result.errors),
        'failures': len(result.failures), 'skipped': len(result.skipped), 'model_calls': 0}))
    raise SystemExit(not result.wasSuccessful())
