"""Cache NASA daily histories and join public OAE production for five provinces."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib, json, time
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/five_province_history'
RAW=OUT/'raw'
CODES=['22','86','33','53','84']
PARAMS=['T2M','T2M_MAX','T2M_MIN','RH2M','PRECTOTCORR','ALLSKY_SFC_SW_DWN','WS2M']
END='20260925'

def fetch(job):
    code,lat,lon,start,end=job
    path=RAW/f'{code}_{start}_{end}.json'
    args=dict(parameters=','.join(PARAMS),community='AG',latitude=lat,longitude=lon,start=start,end=end,format='JSON',**{'time-standard':'LST'})
    if path.exists():
        return code,json.loads(path.read_text(encoding='utf-8'))
    for attempt in range(3):
        try:
            r=requests.get('https://power.larc.nasa.gov/api/temporal/daily/point',params=args,timeout=150)
            r.raise_for_status(); data=r.json()
            assert 'parameter' in data['properties']
            path.write_bytes(r.content)
            path.with_suffix('.source.json').write_text(json.dumps(dict(url=r.url,retrieved_utc=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(r.content).hexdigest()),indent=2),encoding='utf-8')
            return code,data
        except Exception:
            if attempt==2: raise
            time.sleep(2*(attempt+1))

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'research_data/thailand_comparison/production_province_year.csv',dtype={'province_code':str})
    p=p[p.province_code.isin(CODES)].sort_values(['province_code','year_ce'])
    p['production_yoy_pct']=p.groupby('province_code').production_tonnes.pct_change(fill_method=None)*100
    p['yield_yoy_pct']=p.groupby('province_code').yield_kg_per_rai_calculated.pct_change(fill_method=None)*100
    p.to_csv(OUT/'production_annual.csv',index=False,encoding='utf-8-sig')
    points=p.drop_duplicates('province_code')[['province_code','province_name','weather_latitude','weather_longitude']]
    points.to_csv(OUT/'reference_points.csv',index=False,encoding='utf-8-sig')
    x=pd.read_excel(ROOT/'research_data/external/oae_2026-09-17/durian_monthly_province.xlsx',sheet_name='durian_monthly')
    x=x[x.province_name.isin(points.province_name)].copy()
    x['year_ce']=pd.to_numeric(x.year)-543
    x.to_csv(OUT/'production_monthly_source.csv',index=False,encoding='utf-8-sig')
    jobs=[]
    for r in points.itertuples():
        for start in [1981,1991,2001,2011,2021]:
            jobs.append((r.province_code,r.weather_latitude,r.weather_longitude,f'{start}0101',min(f'{start+9}1231',END)))
    rows=[]; errors=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(fetch,j):j for j in jobs}
        for f in as_completed(futures):
            job=futures[f]
            try:
                code,data=f.result(); params=data['properties']['parameter']
                dates=sorted(set().union(*(v.keys() for v in params.values())))
                fill=data.get('header',{}).get('fill_value',-999)
                for d in dates:
                    row={'province_code':code,'date':pd.to_datetime(d,format='%Y%m%d').strftime('%Y-%m-%d')}
                    row.update({k:None if params.get(k,{}).get(d,fill)==fill else params[k][d] for k in PARAMS})
                    rows.append(row)
                print('OK',job[0],job[3],len(dates),flush=True)
            except Exception as e:
                errors.append({'job':job,'error':str(e)}); print('FAILED',job,str(e),flush=True)
    d=pd.DataFrame(rows)
    if len(d):
        d=d.sort_values(['province_code','date']); assert not d.duplicated(['province_code','date']).any()
        d.to_csv(OUT/'weather_daily.csv',index=False,encoding='utf-8-sig')
    (OUT/'download_errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
    print('daily rows',len(d),'failures',len(errors),flush=True)

if __name__=='__main__': main()
