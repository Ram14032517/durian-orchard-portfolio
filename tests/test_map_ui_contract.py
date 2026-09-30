"""Guard template contracts; real pointer/responsive checks are documented separately."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MapUIContractTests(unittest.TestCase):
    def test_chart_css_does_not_override_leaflet_svg(self):
        for name in ['tools/unified_orchard_map.html', 'research_data/five_province_history/UNIFIED_MAP.html']:
            html = (ROOT / name).read_text(encoding='utf-8')
            self.assertNotRegex(html, r'(?:^|[}\s])svg\s*\{')
            self.assertIn('#chart{width:100%;height:170px}', html)

    def test_map_contains_layers_at_all_breakpoints(self):
        css = (ROOT / 'tools/orchard_monthly_report.css').read_text(encoding='utf-8')
        self.assertIn('#map{position:relative;overflow:hidden;min-width:0}', css)

    def test_province_does_not_auto_select_a_district(self):
        html = (ROOT / 'tools/unified_orchard_map.html').read_text(encoding='utf-8')
        body = html.split('async function provinceChange', 1)[1].split('function districtChange', 1)[0]
        self.assertIn('เลือกอำเภอเพื่อดูชุดดิน', body)
        self.assertNotIn('districtChange(false)', body)
        self.assertIn("$('soil').disabled=true", body)
        self.assertIn('scrollWheelZoom:false', html)
        self.assertIn('ResizeObserver', html)

    def test_weather_chart_switch_and_annual_model_present(self):
        for name in ['tools/unified_orchard_map.html', 'research_data/five_province_history/UNIFIED_MAP.html']:
            html = (ROOT / name).read_text(encoding='utf-8')
            for metric in ['T2M', 'T2M_MAX', 'T2M_MIN', 'PRECTOTCORR',
                           'RH2M', 'ALLSKY_SFC_SW_DWN', 'WS2M']:
                self.assertIn(f'<option value="{metric}">', html)
            self.assertIn("$('chart-metric').onchange", html)
            self.assertIn('annual_yield_feature_comparison.json', html)
            self.assertIn('id="annual-year-context"', html)
            self.assertIn('id="weather-warning"', html)
            self.assertIn('ไฟล์สำรองจุดจังหวัด (ไม่ใช่พิกัด A/B)', html)
            self.assertIn('data.stale_cache', html)


if __name__ == '__main__':
    unittest.main()
