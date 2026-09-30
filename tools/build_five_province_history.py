"""Build source-backed daily lookup and comparable year-on-year seasonal explorer."""
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/five_province_history'
MONTHS=['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม']

def clean(df):
    return json.loads(df.to_json(orient='records',force_ascii=False))

def main():
    d=pd.read_csv(OUT/'weather_daily.csv',dtype={'province_code':str})
    d['year_ce']=d.date.str[:4].astype(int);d['month']=d.date.str[5:7].astype(int)
    assert not d.duplicated(['province_code','date']).any()
    assert d.RH2M.dropna().between(0,100).all()
    assert (d.PRECTOTCORR.dropna()>=0).all()
    paired=d.dropna(subset=['T2M_MAX','T2M_MIN']);assert paired.T2M_MAX.ge(paired.T2M_MIN).all()
    m=d.groupby(['province_code','year_ce','month'],as_index=False).agg(
        temperature_c=('T2M','mean'),max_temperature_c=('T2M_MAX','max'),min_temperature_c=('T2M_MIN','min'),
        humidity_pct=('RH2M','mean'),rain_mm=('PRECTOTCORR',lambda x:x.sum(min_count=1)),
        solar_mj_m2_day=('ALLSKY_SFC_SW_DWN','mean'),days_temperature=('T2M','count'),days_rain=('PRECTOTCORR','count'))
    m['expected_days']=pd.to_datetime(dict(year=m.year_ce,month=m.month,day=1)).dt.days_in_month
    baseline=m[m.year_ce.between(1991,2020)&m.days_temperature.eq(m.expected_days)].groupby(['province_code','month']).temperature_c.mean().rename('baseline_1991_2020_c')
    m=m.join(baseline,on=['province_code','month']);m['temperature_anomaly_c']=m.temperature_c-m.baseline_1991_2020_c
    m.to_csv(OUT/'weather_monthly.csv',index=False,encoding='utf-8-sig')
    a=pd.read_csv(OUT/'production_annual.csv',dtype={'province_code':str})
    yearly=d.groupby(['province_code','year_ce'],as_index=False).agg(
        annual_temperature_c=('T2M','mean'),annual_max_c=('T2M_MAX','max'),
        annual_rain_mm=('PRECTOTCORR',lambda x:x.sum(min_count=1)),valid_temperature_days=('T2M','count'),valid_rain_days=('PRECTOTCORR','count'))
    a=a.merge(yearly,on=['province_code','year_ce'],how='left',validate='one_to_one')
    a.to_csv(OUT/'production_weather_annual.csv',index=False,encoding='utf-8-sig')
    points=pd.read_csv(OUT/'reference_points.csv',dtype={'province_code':str})
    raw=pd.read_csv(OUT/'production_monthly_source.csv')
    raw['month_number']=raw.month.map({v:i+1 for i,v in enumerate(MONTHS)})
    harvest=raw[raw.item.eq('ปริมาณผลผลิตรายเดือน')].merge(points[['province_code','province_name']],on='province_name',validate='many_to_one')
    harvest=harvest.rename(columns={'data':'tonnes'})[['province_code','year_ce','month_number','tonnes']]
    assert not harvest.duplicated(['province_code','year_ce','month_number']).any()
    harvest.to_csv(OUT/'harvest_monthly.csv',index=False,encoding='utf-8-sig')
    coverage=[]
    for code,g in d.groupby('province_code'):
        for col in ['T2M','T2M_MAX','T2M_MIN','RH2M','PRECTOTCORR','ALLSKY_SFC_SW_DWN','WS2M']:
            valid=g[g[col].notna()]
            coverage.append(dict(province_code=code,parameter=col,first=valid.date.min(),last=valid.date.max(),valid_days=len(valid),missing_days=int(g[col].isna().sum())))
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False,encoding='utf-8-sig')
    for code,g in d.groupby('province_code'):
        (OUT/f'daily_{code}.json').write_text(json.dumps(clean(g),ensure_ascii=False),encoding='utf-8')
    soils=[]
    for code in points.province_code:
        path=ROOT/f'research_data/priority_provinces/soil_layers/{code}.geojson'
        if path.exists():
            features=json.loads(path.read_text(encoding='utf-8'))['features']
            for f in features:
                soils.append(dict(province_code=code,**f['properties']))
    soil_df=pd.DataFrame(soils).drop_duplicates()
    soil_df.to_csv(OUT/'soil_properties_by_district.csv',index=False,encoding='utf-8-sig')
    data=dict(points=clean(points),annual=clean(a),monthly=clean(m),harvest=clean(harvest),coverage=coverage,soils=clean(soil_df))
    template=(ROOT/'tools/five_province_history.html').read_text(encoding='utf-8')
    (OUT/'HISTORY.html').write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False,allow_nan=False)),encoding='utf-8')
    print('Validated:',len(d),'daily rows;',len(a),'province-years;',len(harvest),'harvest months')
    print(pd.DataFrame(coverage).to_string(index=False))

if __name__=='__main__':main()
