"""Check that the displayed feature comparison stays tied to the baseline audit."""
import csv
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research_data/five_province_history/training'


class AnnualYieldFeatureComparisonTests(unittest.TestCase):
    def test_baseline_and_all_weather_match_prior_benchmark(self):
        result = json.loads((BASE / 'annual_yield_feature_comparison.json').read_text(encoding='utf-8'))
        with (BASE / 'annual_yield_windows_metrics.csv').open(encoding='utf-8-sig', newline='') as f:
            benchmark = list(csv.DictReader(f))
        self.assertEqual(result['split_counts'], {'train': 125, 'validation': 10, 'test': 10})
        self.assertEqual(len(result['yearly_context']), 145)
        for key, window in [('baseline', 0), ('all_weather', 6)]:
            score = next(row for row in result['scores'] if row['key'] == key)
            for split in ('validation', 'test'):
                expected = next(row for row in benchmark if row['window_months'] == str(window)
                                and row['split'] == split)
                self.assertAlmostEqual(score[f'{split}_mae_kg_rai'], float(expected['mae_kg_rai']))


if __name__ == '__main__':
    unittest.main()
