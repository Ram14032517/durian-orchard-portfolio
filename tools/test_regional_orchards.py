"""Offline regression checks for GIS, weather, native notebook, and baseline."""
import calendar
import hashlib
import json
from pathlib import Path
import unittest
import nbformat
import numpy as np
import pandas as pd
import shapefile
import shapely
from shapely.geometry import shape, Point
from pyproj import CRS, Transformer
from fetch_orchard_weather import spatial_aggregate
from prepare_national_comparison import aggregate_weather, PARAMS
from prepare_regional_orchards import CONFIG, polygonal
from audit_regional_readiness import soil_resolution

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/regional_orchards'


class RegionalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summaries=json.loads((OUT/'overlay_summaries.json').read_text(encoding='utf-8'))
        def read(name): return pd.read_csv(OUT/name,dtype={'province_code':str})
        cls.points=read('orchard_weather_samples.csv')
        cls.raw=read('sample_weather_monthly.csv')
        cls.monthly=read('orchard_weather_monthly.csv')
        cls.panel=read('regional_province_year_panel.csv')
        cls.soil=read('soil_series_comparison.csv')

    def test_source_hashes_and_crs(self):
        self.assertEqual(len(self.summaries),4)
        for s in self.summaries:
            for entry in s['input_manifest']:
                self.assertEqual(hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest(),entry['sha256'])
            self.assertEqual(s['soil_year_be'],2561)
            if s['province_code']=='33':
                self.assertEqual(s['soil_source_crs'],'EPSG:32647')
                self.assertEqual(s['landuse_source_crs'],'EPSG:32648')
        for rawdir in ['ldd_regions_2026-09-18','power_orchards_2026-09-18']:
            for meta in (ROOT/'research_data/external'/rawdir).rglob('*.source.json'):
                info=json.loads(meta.read_text(encoding='utf-8'))
                target=meta.with_name(meta.name.removesuffix('.source.json'))
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),info['sha256'])
                self.assertTrue(info['url'].startswith('https://'))

    def test_soil_area_accounting(self):
        for s in self.summaries:
            table=self.soil.loc[self.soil.province_code.eq(s['province_code'])]
            for kind in ['pure','mixed']:
                g=s['summary'][kind]
                self.assertAlmostEqual(g['rai'],g['covered_rai']+g['uncovered_rai'],places=6)
                self.assertLess(abs(table[kind+'_rai'].sum()-g['covered_rai']),.1)
                self.assertLess(g['landuse_overlap_rai'],.1)
                self.assertLess(g['soil_overlap_rai'],.1)
                self.assertGreaterEqual(g['uncovered_rai'],-1e-7)
            self.assertLess(s['cross_class_overlap_rai'],.1)
        old=json.loads((ROOT/'research_data/soil_evidence_chanthaburi/analysis.json').read_text(encoding='utf-8'))
        cti=next(s for s in self.summaries if s['province_code']=='22')
        self.assertAlmostEqual(cti['summary']['pure']['rai'],old['summary']['pure']['rai'],places=5)

    def test_actual_query_points_inside_A403(self):
        # Independently re-open input LU polygons; check rounded API coordinates,
        # not just the pipeline's saved True flag.
        for short,cfg in CONFIG.items():
            p=next((cfg['folder']/'landuse').rglob(f'LU_{short.upper()}_{cfg["lu_year"]}.shp'))
            crs=CRS.from_wkt(p.with_suffix('.prj').read_text())
            project=Transformer.from_crs(4326,crs,always_xy=True)
            reader=shapefile.Reader(str(p),encoding='utf-8')
            geoms=[]
            for i,r in enumerate(reader.iterRecords()):
                if r['LU_CODE'].strip()=='A403':
                    g=shape(reader.shape(i).__geo_interface__)
                    geoms.append(polygonal(shapely.make_valid(g)) if not g.is_valid else g)
            tree=shapely.STRtree(geoms)
            ps=self.points.loc[self.points.province_code.eq(cfg['code'])]
            self.assertAlmostEqual(ps.weight.sum(),1.,places=7)
            for r in ps.itertuples():
                pt=Point(*project.transform(round(r.longitude,7),round(r.latitude,7)))
                self.assertTrue(any(geoms[j].covers(pt) for j in tree.query(pt)),r.sample_id)

    def test_weather_grain_units_and_annual_values(self):
        self.assertEqual(len(self.raw),59*240)
        self.assertEqual(len(self.monthly),960)
        self.assertEqual(len(self.panel),80)
        self.assertFalse(self.raw.duplicated(['sample_id','year_ce','month']).any())
        self.assertFalse(self.monthly.duplicated(['province_code','year_ce','month']).any())
        self.assertFalse(self.panel.duplicated(['province_code','year_ce']).any())
        self.assertEqual(set(self.monthly.month),set(range(1,13)))
        self.assertTrue(self.panel.complete_weather_months.eq(12).all())
        for (c,y,m),g in self.raw.groupby(['province_code','year_ce','month']):
            row=self.monthly.loc[self.monthly.province_code.eq(c)&self.monthly.year_ce.eq(y)&self.monthly.month.eq(m)].iloc[0]
            self.assertEqual(row.days,calendar.monthrange(y,m)[1])
            self.assertAlmostEqual(np.average(g.T2M,weights=g.weight),row.T2M,places=7)
            self.assertAlmostEqual(np.average(g.PRECTOTCORR,weights=g.weight)*row.days,row.rain_mm_month,places=7)
        recalculated=aggregate_weather(self.monthly).set_index(['province_code','year_ce'])
        panel=self.panel.set_index(['province_code','year_ce'])
        for col in ['temperature_c','humidity_pct','rain_mm_year','solar_mj_m2_day']:
            np.testing.assert_allclose(recalculated[col],panel.loc[recalculated.index,col])
        self.assertTrue(self.panel.production_tonnes.notna().all())

    def test_missing_stratum_does_not_silently_renormalize(self):
        ps=self.points.loc[self.points.province_code.eq('22')]
        bad=self.raw.loc[self.raw.province_code.eq('22')&self.raw.sample_id.ne(ps.iloc[0].sample_id)]
        result=spatial_aggregate(ps,bad)
        self.assertTrue(result[PARAMS].isna().all().all())
        self.assertTrue(result.T2M_area_coverage.lt(1).all())

    def test_baseline_is_past_only(self):
        predictions=pd.read_csv(OUT/'baseline_predictions.csv',dtype={'province_code':str})
        self.assertEqual(len(predictions),60)
        for row in predictions.itertuples():
            history=self.panel.loc[self.panel.province_code.eq(row.province_code)&self.panel.year_ce.lt(row.year_ce)].sort_values('year_ce')
            self.assertEqual(row.previous_year,history.iloc[-1].yield_kg_per_rai_source)
            self.assertAlmostEqual(row.trailing_5yr_mean,history.tail(5).yield_kg_per_rai_source.mean())
        errors=predictions.previous_year-predictions.yield_kg_per_rai_source
        self.assertAlmostEqual(errors.abs().mean(),189.78333333333333)

    def test_native_notebook_and_figures(self):
        nb=nbformat.read(ROOT/'notebooks/03_regional_orchards_soil_weather.ipynb',as_version=4)
        nbformat.validate(nb)
        cells=[c for c in nb.cells if c.cell_type=='code']
        self.assertEqual([c.execution_count for c in cells],list(range(1,len(cells)+1)))
        self.assertTrue(all(o.output_type!='error' for c in cells for o in c.outputs))
        for name in ['soil_units_four_provinces','weather_spatial_support_comparison','retrospective_weather_profiles']:
            for ext in ['png','svg']:
                self.assertGreater((OUT/(name+'.'+ext)).stat().st_size,5000)
        self.assertTrue((OUT/'ANALYSIS_NOTEBOOK.html').exists())

    def test_same_year_area_reconciliation(self):
        readiness=pd.read_csv(OUT/'model_readiness.csv',dtype={'province_code':str})
        production=pd.read_csv(ROOT/'research_data/thailand_comparison/production_province_year.csv',dtype={'province_code':str})
        self.assertEqual(len(readiness),4)
        self.assertTrue(readiness.province_code.is_unique)
        self.assertEqual((~readiness.match_possible_with_fraction_0_to_1).sum(),3)
        for r in readiness.itertuples():
            self.assertEqual(r.matched_oae_year_ce,r.landuse_year_be-543)
            source=production.loc[production.province_code.eq(r.province_code)&production.year_ce.eq(r.matched_oae_year_ce)].iloc[0]
            self.assertEqual(r.oae_planted_rai,source.planted_rai)
            self.assertEqual(r.oae_bearing_rai,source.bearing_rai)
            f=(r.oae_planted_rai-r.ldd_A403_rai)/r.ldd_mixed_polygon_rai
            self.assertAlmostEqual(r.algebraic_mixed_fraction_to_match,f)
            self.assertAlmostEqual(r.ldd_A403_rai+f*r.ldd_mixed_polygon_rai,r.oae_planted_rai)
            self.assertLess(abs(r.geometry_minus_source_area_rai/r.source_attribute_pure_rai),.001)
            self.assertEqual(r.A403_description_in_source,'ทุเรียน')

    def test_soil_resolution_and_future_footprint_counts(self):
        self.assertEqual(soil_resolution('SC','พื้นที่ลาดชันเชิงซ้อน'),'terrain_misc_unit')
        self.assertEqual(soil_resolution('W','พื้นที่น้ำ'),'water')
        self.assertEqual(soil_resolution('Ho-Klt','หน่วยเชิงซ้อน'),'complex_or_association')
        self.assertEqual(soil_resolution('Chp/Ka','หน่วยดินสัมพันธ์'),'complex_or_association')
        self.assertEqual(soil_resolution('Te','ท่าแซะ'),'named_single_unit_candidate')
        self.assertEqual(soil_resolution('(ไม่ระบุ)',''),'unidentified')
        readiness=pd.read_csv(OUT/'model_readiness.csv',dtype={'province_code':str})
        columns=['named_single_unit_candidate_pct','complex_or_association_pct','terrain_misc_unit_pct',
                 'water_pct','unidentified_pct','soil_unmapped_pct']
        np.testing.assert_allclose(readiness[columns].sum(axis=1),100,atol=1e-6)
        for r in readiness.itertuples():
            expected=((self.panel.province_code.eq(r.province_code))&(self.panel.year_ce.lt(r.landuse_year_be-543))).sum()
            self.assertEqual(r.historical_years_before_landuse_snapshot,expected)
        self.assertEqual(readiness.historical_years_before_landuse_snapshot.sum(),64)


if __name__=='__main__': unittest.main(verbosity=2)
