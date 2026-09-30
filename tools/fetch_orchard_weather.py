"""Retrospective POWER profiles at public mapped-durian locations (2006–2025).

Stratum area-weighting is approximate quadrature, not a native-grid polygon
integral. Land-use snapshot is fixed across historical weather years.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import calendar
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
import numpy as np
import pandas as pd

from prepare_national_comparison import fetch, save_json, aggregate_weather, PARAMS, NASA

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/regional_orchards'
RAW=ROOT/'research_data/external/power_orchards_2026-09-18'
YEARS=range(2006,2026)


def one(rec):
    query={'parameters':','.join(PARAMS),'community':'AG','longitude':round(rec['longitude'],7),
           'latitude':round(rec['latitude'],7),'start':min(YEARS),'end':max(YEARS),'format':'JSON'}
    path=fetch(NASA+'?'+urlencode(query),RAW/(rec['sample_id']+'.json'))
    obj=json.loads(path.read_text(encoding='utf-8'))
    units={k:obj['parameters'][k]['units'] for k in PARAMS}
    assert units=={'T2M':'C','RH2M':'%','PRECTOTCORR':'mm/day','ALLSKY_SFC_SW_DWN':'MJ/m^2/day'}
    assert obj['header']['time_standard']=='LST'
    values=obj['properties']['parameter']
    signature=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
    rows=[]
    for year in YEARS:
        for month in range(1,13):
            row={'sample_id':rec['sample_id'],'province_code':rec['province_code'],'province_name':rec['province_name'],
                 'year_ce':year,'month':month,'days':calendar.monthrange(year,month)[1],'weight':rec['weight']}
            for key in PARAMS:
                v=values[key].get(f'{year}{month:02}')
                row[key]=np.nan if v is None or v==obj['header']['fill_value'] else float(v)
            rows.append(row)
    return rows,{'sample_id':rec['sample_id'],'province_code':rec['province_code'],'response_profile_sha256':signature}


def spatial_aggregate(points,raw):
    rows=[]
    # Build every province/month even if some requests failed. Do not silently
    # renormalize away unavailable strata: retain coverage and mark metric missing.
    for code,ps in points.groupby('province_code'):
        data=raw.loc[raw.province_code.eq(code)]
        for year in YEARS:
            for month in range(1,13):
                g=data.loc[data.year_ce.eq(year)&data.month.eq(month)]
                row={'province_code':code,'province_name':ps.iloc[0].province_name,'year_ce':year,'month':month,
                     'days':calendar.monthrange(year,month)[1],'landuse_year_be':int(ps.iloc[0].landuse_year_be),
                     'sample_points_total':len(ps),'fixed_snapshot_retrospective':True}
                for key in PARAMS:
                    valid=g[key].notna()
                    coverage=g.loc[valid,'weight'].sum()
                    row[key+'_area_coverage']=coverage
                    row[key]=(g.loc[valid,key]*g.loc[valid,'weight']).sum()/coverage if abs(coverage-1)<1e-7 else np.nan
                row['rain_mm_month']=row['PRECTOTCORR']*row['days']
                rows.append(row)
    return pd.DataFrame(rows)


def main():
    points=pd.read_csv(OUT/'orchard_weather_samples.csv',dtype={'province_code':str})
    assert points.province_code.nunique()==4, 'Finish all four GIS overlays first'
    assert points.sample_id.is_unique
    assert points.groupby('province_code').weight.sum().sub(1).abs().lt(1e-7).all()
    rows,signatures,failures=[],[],[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(one,r):r for r in points.to_dict('records')}
        for n,job in enumerate(as_completed(jobs),1):
            rec=jobs[job]
            try:
                rr,signature=job.result()
                rows.extend(rr);signatures.append(signature)
            except Exception as exc:
                failures.append({'sample_id':rec['sample_id'],'error':str(exc)})
            if n%10==0 or n==len(jobs):
                print(f'NASA orchard points {n}/{len(jobs)}; failures={len(failures)}',flush=True)
    save_json(OUT/'weather_fetch_failures.json',failures)
    if not rows:
        raise RuntimeError('No weather data; inspect failures')
    raw=pd.DataFrame(rows).sort_values(['province_code','sample_id','year_ce','month'])
    raw.to_csv(OUT/'sample_weather_monthly.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(signatures).to_csv(OUT/'sample_response_signatures.csv',index=False)
    weighted=spatial_aggregate(points,raw)
    weighted.to_csv(OUT/'orchard_weather_monthly.csv',index=False,encoding='utf-8-sig')
    annual=aggregate_weather(weighted)
    lookup=points[['province_code','province_name','region','landuse_year_be']].drop_duplicates()
    annual=annual.merge(lookup,on='province_code',validate='many_to_one')
    annual['weather_support']='A403_stratified_point_area_weighted'
    annual['fixed_snapshot_retrospective']=True
    annual.to_csv(OUT/'orchard_weather_annual.csv',index=False,encoding='utf-8-sig')
    prod=pd.read_csv(ROOT/'research_data/thailand_comparison/production_province_year.csv',dtype={'province_code':str})
    cols=['province_code','year_ce','production_tonnes','bearing_rai','planted_rai','yield_kg_per_rai_source','yield_kg_per_rai_calculated']
    panel=annual.merge(prod[cols],on=['province_code','year_ce'],how='left',validate='one_to_one')
    panel.to_csv(OUT/'regional_province_year_panel.csv',index=False,encoding='utf-8-sig')
    old=pd.read_csv(ROOT/'research_data/thailand_comparison/province_year_panel.csv',dtype={'province_code':str})
    measures=['temperature_c','humidity_pct','rain_mm_year','solar_mj_m2_day']
    compare=annual.merge(old[['province_code','year_ce',*measures]],on=['province_code','year_ce'],suffixes=('_orchard_weighted','_province_point'),validate='one_to_one')
    for key in measures:
        compare[key+'_difference']=compare[key+'_orchard_weighted']-compare[key+'_province_point']
    compare.to_csv(OUT/'reference_point_comparison_2021_2025.csv',index=False,encoding='utf-8-sig')
    print(f'Saved {len(weighted)} province-months / {len(panel)} province-years; missing production labels {panel.production_tonnes.isna().sum()}',flush=True)


if __name__=='__main__':
    main()
