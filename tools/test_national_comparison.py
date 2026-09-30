"""Offline source/aggregation/output checks. Does not make network requests."""
import hashlib
import json
from pathlib import Path
import unittest

import nbformat
import numpy as np
import pandas as pd
from shapely.geometry import shape

from prepare_national_comparison import aggregate_weather

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_data/thailand_comparison'
RAW = ROOT / 'research_data/external/national_2026-09-17'


class NationalComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = pd.read_csv(OUT/'province_year_panel.csv', dtype={'province_code':str})
        cls.monthly = pd.read_csv(OUT/'weather_monthly.csv', dtype={'province_code':str})

    def test_provenance_hashes(self):
        sources = list(RAW.rglob('*.source.json'))
        self.assertGreaterEqual(len(sources), 82)
        for meta in sources:
            info = json.loads(meta.read_text(encoding='utf-8'))
            path = meta.with_name(meta.name.removesuffix('.source.json'))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), info['sha256'])
            self.assertTrue(info['url'].startswith('https://'))

    def test_keys_and_missingness(self):
        self.assertEqual(len(self.panel), 385)
        self.assertFalse(self.panel.duplicated(['province_code','year_ce']).any())
        self.assertEqual(self.panel.province_code.nunique(), 77)
        source = pd.read_csv(OUT/'production_province_year.csv')
        for year, group in self.panel.groupby('year_ce'):
            expected = source.loc[source.year_ce.eq(year),'province_code'].nunique()
            self.assertEqual(group.production_tonnes.notna().sum(), expected)
            self.assertEqual(group.production_tonnes.isna().sum(), 77-expected)
            self.assertEqual(group.soil_overlay_available.sum(), 4)
        self.assertEqual(set(self.panel.loc[self.panel.soil_overlay_available,'province_name'].unique()), {'จันทบุรี','ชุมพร','ศรีสะเกษ','อุตรดิตถ์'})

    def test_weather_units_and_annual_math(self):
        self.assertEqual(len(self.monthly), 77*5*12)
        self.assertEqual(set(self.monthly.month), set(range(1,13)))
        self.assertTrue(self.panel.complete_weather_months.eq(12).all())
        for _, g in self.monthly.groupby(['province_code','year_ce']):
            annual = self.panel.loc[self.panel.province_code.eq(g.iloc[0].province_code) & self.panel.year_ce.eq(g.iloc[0].year_ce)].iloc[0]
            self.assertAlmostEqual((g.PRECTOTCORR*g.days).sum(), annual.rain_mm_year, places=6)
            self.assertAlmostEqual(np.average(g.T2M,weights=g.days),annual.temperature_c,places=6)
        # Missing month must invalidate the corresponding annual metric, not become zero.
        sample = self.monthly.iloc[:12].copy()
        sample.loc[sample.index[0], 'T2M'] = np.nan
        sample.loc[sample.index[0], 'rain_mm_month'] = np.nan
        result = aggregate_weather(sample).iloc[0]
        self.assertTrue(pd.isna(result.temperature_c))
        self.assertTrue(pd.isna(result.rain_mm_year))

    def test_boundary_completeness_and_finite_display(self):
        geo = json.loads((OUT/'province_display.geojson').read_text(encoding='utf-8'))
        self.assertEqual(len(geo['features']),77)
        self.assertIn('91',[f['properties']['province_code'] for f in geo['features']])
        for feature in geo['features']:
            self.assertFalse(shape(feature['geometry']).is_empty)

    def test_country_reconciliation_is_not_fudged(self):
        source = pd.read_csv(OUT/'oae_country_source.csv')
        for year,g in self.panel.groupby('year_ce'):
            official = source.loc[source.year.eq(year+543)&source.item.eq('ผลผลิต'),'data'].item()
            self.assertLessEqual(abs(g.production_tonnes.sum()-official),1.0)
        # Historical source precision discrepancy is retained, not overwritten.
        self.assertAlmostEqual(self.panel.loc[self.panel.year_ce.eq(2025),'production_tonnes'].sum(),1573851.69)

    def test_native_executed_notebook_and_offline_map(self):
        nb = nbformat.read(ROOT/'notebooks/02_thailand_durian_comparison.ipynb',as_version=4)
        nbformat.validate(nb)
        code = [c for c in nb.cells if c.cell_type=='code']
        self.assertGreaterEqual(len(code),7)
        self.assertEqual([c.execution_count for c in code],list(range(1,len(code)+1)))
        self.assertTrue(all(all(o.output_type!='error' for o in c.outputs) for c in code))
        markup = (OUT/'THAILAND_MAP.html').read_text(encoding='utf-8')
        self.assertNotIn('<script src=',markup)
        self.assertNotIn('<link rel="stylesheet" href=',markup)
        self.assertIn("el('metric').value='yield_kg_per_rai_source'",markup)
        self.assertIn('ยังไม่ประมวลผลจังหวัดนี้',markup)


if __name__ == '__main__':
    unittest.main(verbosity=2)
