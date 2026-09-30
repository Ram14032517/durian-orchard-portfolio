import calendar
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_annual_yield_windows import months_before, aggregate_window, annual_yield, WEATHER

class AnnualWindowTests(unittest.TestCase):
    def group(self, days, value):
        return {field:[value]*days for field in WEATHER}

    def test_cross_year_excludes_anchor(self):
        self.assertEqual(months_before(2024,2,3),[(2024,1),(2023,12),(2023,11)])

    def test_leap_year_and_daily_weighting(self):
        daily = {('84',2024,1):self.group(31,10),('84',2024,2):self.group(29,20)}
        result = aggregate_window(daily,'84',2024,3,2)
        self.assertAlmostEqual(result['temperature_c'],(31*10+29*20)/60)
        self.assertEqual(result['rain_mm'],890)

    def test_missing_day_rejects_whole_window(self):
        daily = {('84',2024,2):self.group(29,20)}
        daily[('84',2024,2)]['humidity_pct'].pop()
        self.assertTrue(all(np.isnan(v) for v in aggregate_window(daily,'84',2024,3,1).values()))

    def test_anchor_and_future_do_not_change_features(self):
        daily = {('84',2024,2):self.group(29,20)}
        before = aggregate_window(daily,'84',2024,3,1)
        daily[('84',2024,3)] = self.group(31,999)
        daily[('84',2024,4)] = self.group(30,999)
        self.assertEqual(before,aggregate_window(daily,'84',2024,3,1))

    def test_bearing_area_denominator_and_units(self):
        self.assertEqual(annual_yield(20,10),2000)
        self.assertEqual(annual_yield(0,10),0)
        for production,area in [(20,0),(20,np.inf),(-1,10),(np.nan,10)]:
            self.assertTrue(np.isnan(annual_yield(production,area)))

    def test_invalid_window(self):
        for month,count in [(0,1),(13,1),(1,0),(1,7)]:
            with self.assertRaises(ValueError): months_before(2024,month,count)

if __name__ == '__main__': unittest.main()
