import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare_monthly_training.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)

class TrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = prepare.build_rows()

    def test_unique_keys(self):
        self.assertEqual(len(self.rows), len({(r['province_code'], r['target_month']) for r in self.rows}))

    def test_prior_month_not_prior_available_row(self):
        self.assertEqual(prepare.previous_month(2025, 1), (2024, 12))
        for row in self.rows:
            y, m = prepare.previous_month(row['year_ce'], row['month'])
            self.assertEqual(row['feature_month'], f'{y:04d}-{m:02d}')

    def test_eligibility_does_not_fill_missing_target(self):
        self.assertTrue(any(r['target_production_tonnes'] == '' for r in self.rows))
        for row in self.rows:
            if row['eligible_for_baseline']:
                self.assertNotEqual(row['target_production_tonnes'], '')
                self.assertFalse(row['exclusion_reason'])
                self.assertEqual(int(row['lag1_rain_days']), row['lag1_expected_days'])
                self.assertEqual(row['lag1_humidity_days'], row['lag1_expected_days'])
                self.assertEqual(row['lag1_solar_days'], row['lag1_expected_days'])

    def test_features_and_time_split(self):
        self.assertNotIn('target_production_tonnes', prepare.FEATURES)
        self.assertEqual([prepare.split_for(y) for y in [2021, 2022, 2023, 2024, 2025, 2026]],
                         ['train', 'validation', 'validation', 'test', 'test', 'future_holdout'])

    def test_target_join_matches_source(self):
        source = prepare.keyed(prepare.read_csv('harvest_monthly.csv'), 'month_number')
        for row in self.rows:
            key = (row['province_code'], row['year_ce'], row['month'])
            self.assertEqual(row['target_production_tonnes'], source.get(key, {}).get('tonnes', ''))

if __name__ == '__main__':
    unittest.main()
