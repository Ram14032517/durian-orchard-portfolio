"""Prepare public soil/district reference points and unified map assets."""
import json
from pathlib import Path
import pandas as pd
from shapely.geometry import shape

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/five_province_history'
def main():
    points=pd.read_csv(OUT/'reference_points.csv',dtype={'province_code':str})
    districts=[]
    for code in points.province_code:
        path=ROOT/f'research_data/priority_provinces/soil_layers/{code}.geojson'
        data=json.loads(path.read_text(encoding='utf-8'));best={}
        for f in data['features']:
            g=shape(f['geometry']); p=g.representative_point()
            f['properties']['latitude']=round(p.y,5);f['properties']['longitude']=round(p.x,5)
            name=f['properties'].get('district','ไม่ระบุ')
            if name not in best or g.area>best[name][0]:best[name]=(g.area,p)
        for name,(_,p) in best.items():
            districts.append(dict(province_code=code,district=name,latitude=round(p.y,5),longitude=round(p.x,5),point_method='จุดภายในหน่วยดินชิ้นใหญ่สุดที่มีชื่ออำเภอนี้ ไม่ใช่พิกัดสวนหรือค่าเฉลี่ยอำเภอ'))
        path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    pd.DataFrame(districts).to_csv(OUT/'district_reference_points.csv',index=False,encoding='utf-8-sig')
    bounds=json.loads((ROOT/'research_data/thailand_comparison/province_display.geojson').read_text(encoding='utf-8'))
    bounds['features']=[f for f in bounds['features'] if str(f['properties']['province_code']) in set(points.province_code)]
    def records(path):return json.loads(pd.read_csv(path,dtype={'province_code':str}).to_json(orient='records',force_ascii=False))
    payload=dict(provinces=records(OUT/'reference_points.csv'),districts=districts,boundaries=bounds,
                 annual=records(OUT/'production_weather_annual.csv'),harvest=records(OUT/'harvest_monthly.csv'))
    payload['monthly_weather']=records(OUT/'weather_monthly.csv')
    payload['phenology']=json.loads((OUT/'phenology_evidence.json').read_text(encoding='utf-8'))
    template=(ROOT/'tools/unified_orchard_map.html').read_text(encoding='utf-8')
    monthly_js=(ROOT/'tools/orchard_monthly_report.js').read_text(encoding='utf-8')
    monthly_css=(ROOT/'tools/orchard_monthly_report.css').read_text(encoding='utf-8')
    rendered=template.replace('__DATA__',json.dumps(payload,ensure_ascii=False)).replace('__MONTHLY_CODE__',monthly_js).replace('__MONTHLY_STYLE__',monthly_css)
    (OUT/'UNIFIED_MAP.html').write_text(rendered,encoding='utf-8')
    season_template=(ROOT/'tools/five_province_seasons.html').read_text(encoding='utf-8')
    season_payload={k:v for k,v in payload.items() if k not in ('monthly_weather','phenology')}
    (OUT/'SEASONS_MAP.html').write_text(season_template.replace('__DATA__',json.dumps(season_payload,ensure_ascii=False)),encoding='utf-8')
    print('District reference points:',len(districts))
if __name__=='__main__':main()
