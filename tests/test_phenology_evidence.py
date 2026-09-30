"""Validate reviewed calendar mappings and dated records, without inventing observations."""
from pathlib import Path
from datetime import date
import json,unittest

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'research_data/five_province_history/phenology_evidence.json').read_text(encoding='utf-8'))

class EvidenceTests(unittest.TestCase):
    def test_five_provinces_once(self):
        codes=[c for r in DATA['regions'].values() for c in r['provinces']]
        self.assertEqual(sorted(codes),['22','33','53','84','86'])
    def test_each_month_covered_and_stages_known(self):
        for region in DATA['regions'].values():
            months=set()
            for p in region['periods']:
                self.assertIn(p['stage'],DATA['stages'])
                self.assertTrue(all(1<=m<=12 for m in p['months']))
                months.update(p['months'])
            self.assertEqual(months,set(range(1,13)))
    def test_overlaps_preserved(self):
        south=DATA['regions']['upper_south']['periods']
        self.assertEqual({p['stage'] for p in south if 7 in p['months']},{'leaf','fruit','harvest'})
        east=DATA['regions']['east']['periods']
        self.assertEqual({p['stage'] for p in east if 4 in p['months']},{'fruit','harvest'})
    def test_events_have_consistent_month_and_year(self):
        ids=set()
        for e in DATA['events']:
            self.assertNotIn(e['id'],ids);ids.add(e['id'])
            d=date.fromisoformat(e['event_date'])
            self.assertEqual(e['year'],d.year);self.assertIn(d.month,e['months'])
            self.assertTrue(e['url'].startswith('https://'))
    def test_publication_not_used_as_event_month(self):
        event=next(e for e in DATA['events'] if e['id']=='surat-cut-20260620')
        self.assertEqual(event['months'],[6])
        self.assertEqual(date.fromisoformat(event['published_date']).month,5)

if __name__=='__main__':unittest.main()
