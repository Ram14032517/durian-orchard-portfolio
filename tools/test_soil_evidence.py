"""Read-only consistency checks for the generated Chanthaburi pilot."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'.build/soil-map-packages'))
import shapefile

OUT = ROOT/'research_data/soil_evidence_chanthaburi'
RAW = ROOT/'research_data/external/ldd_chanthaburi_2026-09-17'


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((OUT/'analysis.json').read_text(encoding='utf-8'))
        cls.audit = json.loads((OUT/'polygon_audit.json').read_text(encoding='utf-8'))

    def test_source_hashes(self):
        for row in self.data['archives']:
            self.assertEqual(hashlib.sha256((RAW/row['file']).read_bytes()).hexdigest(), row['sha256'])

    def test_original_classification_counts(self):
        source = shapefile.Reader(str(next((RAW/'landuse').rglob('LU_CTI_2568.shp'))), encoding='utf-8')
        codes = [r['LU_CODE'].strip() for r in source.iterRecords()]
        self.assertEqual(len(codes), self.data['landuse_features'])
        self.assertEqual(sum(c == 'A403' for c in codes), self.data['summary']['pure']['records'])
        self.assertEqual(sum(c != 'A403' and 'A403' in c.split('/') for c in codes), self.data['summary']['mixed']['records'])

    def test_area_reconciliation(self):
        for kind in ('pure', 'mixed'):
            s = self.data['summary'][kind]
            self.assertAlmostEqual(s['rai'], s['covered_rai']+s['uncovered_rai'], places=5)
            self.assertAlmostEqual(sum(r[kind+'_rai'] for r in self.data['soil_stats']), s['covered_rai'], places=5)
            self.assertLess(s['soil_overlap_rai'], 0.1)
            self.assertLess(s['landuse_internal_overlap_rai'], 0.1)
        self.assertLess(self.data['cross_class_overlap_rai'], 0.1)

    def test_per_polygon_audit(self):
        self.assertEqual(len(self.audit), sum(s['records'] for s in self.data['summary'].values()))
        self.assertEqual(len({r['source_record_0_based'] for r in self.audit}), len(self.audit))
        for r in self.audit:
            self.assertGreater(r['geometry_rai'], 0)
            self.assertGreaterEqual(r['soil_covered_rai'], 0)
            self.assertLessEqual(r['soil_covered_rai'], r['geometry_rai']+1e-6)

    def test_report_is_offline_and_has_citations(self):
        report = (OUT/'START_HERE.html').read_text(encoding='utf-8')
        self.assertNotIn('__ANALYSIS_JSON__', report)
        self.assertNotIn('<script src=', report)
        for url in self.data['sources'].values():
            self.assertIn(url, report)
        self.assertIn('Non-Commercial No-Derivs', report)


if __name__ == '__main__':
    unittest.main()
