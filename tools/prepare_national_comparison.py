"""Download/cache public sources and join province-year observations.

Never edits orchard readings or uploads anything. Run with the project analysis
environment; --skip-weather prepares boundaries/OAE without NASA requests.
"""
from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests
from shapely.geometry import shape, mapping
from shapely import make_valid

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'research_data/external/national_2026-09-17'
OUT = ROOT / 'research_data/thailand_comparison'
BOUNDARY = 'https://gis-portal.disaster.go.th/arcgis/rest/services/MapDX/DPM_TH_Boundary/FeatureServer/1'
GISTDA = 'https://gistdaportal.gistda.or.th/arcgis/rest/services/ข้อมูลเขตการปกครอง/MapServer/2'
OAE = 'https://catalog.oae.go.th/dataset/4810d4a3-669b-4e54-ba46-050e730d34c8/resource/'
NASA = 'https://power.larc.nasa.gov/api/temporal/monthly/point'
PARAMS = ['T2M', 'RH2M', 'PRECTOTCORR', 'ALLSKY_SFC_SW_DWN']
YEARS = range(2021, 2026)
ITEMS = {'เนื้อที่ยืนต้น': 'planted_rai', 'เนื้อที่ให้ผล': 'bearing_rai',
         'ผลผลิต': 'production_tonnes', 'ผลผลิตต่อเนื้อที่ให้ผล': 'yield_kg_per_rai_source'}


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def fetch(url, path):
    """Immutable-by-default cache with source URL/time/hash metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = path.with_suffix(path.suffix + '.source.json')
    if path.exists():
        info = json.loads(meta.read_text(encoding='utf-8'))
        assert info['url'] == url and info['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        return path
    for attempt in range(4):
        try:
            response = requests.get(url, timeout=(20, 100), headers={'User-Agent': 'DurianResearchNotebook/0.1'})
            response.raise_for_status()
            if path.suffix in ['.json', '.geojson']:
                obj = response.json()
                if 'error' in obj:
                    raise ValueError(str(obj['error']))
            path.write_bytes(response.content)
            save_json(meta, {'url': url, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                            'sha256': hashlib.sha256(response.content).hexdigest(),
                            'bytes': len(response.content),
                            'last_modified_http': response.headers.get('Last-Modified')})
            return path
        except (requests.RequestException, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def boundaries():
    fetch(BOUNDARY + '?f=pjson', RAW / 'province_layer_metadata.json')
    query = urlencode({'where': '1=1', 'outFields': 'PROV_CODE,PROV_NAM_T,PROV_NAM_E,REGION_6',
                       'returnGeometry': 'true', 'outSR': '4326', 'f': 'geojson'})
    dpm = json.loads(fetch(BOUNDARY + '/query?' + query, RAW / 'provinces.geojson').read_text(encoding='utf-8'))
    # DPM snapshot contains 76 features: Satun (91) is absent. Use one coherent
    # alternative boundary layer for ALL provinces, not a patched display shape.
    regions = {str(f['properties']['PROV_CODE']): f['properties']['REGION_6'] for f in dpm['features']}
    regions['91'] = 'ภาคใต้'  # explicit supplement to DPM REGION_6, documented in provenance
    fetch(GISTDA + '?f=pjson', RAW / 'gistda_province_metadata.json')
    gquery = urlencode({'where': '1=1', 'outFields': 'P_code,P_Name_T,P_Name_E,P_group,Source_Nam,Source_dat',
                        'returnGeometry': 'true', 'outSR': '4326', 'maxAllowableOffset': '0.002',
                        'geometryPrecision': 5, 'f': 'geojson'})
    source = json.loads(fetch(GISTDA + '/query?' + gquery, RAW / 'gistda_provinces.geojson').read_text(encoding='utf-8'))
    assert not source.get('exceededTransferLimit'), 'Paginate boundary response before use'
    assert len(source['features']) == 77, 'Unexpected province count: inspect source before continuing'
    records, display, repairs = [], [], []
    for feature in source['features']:
        props = feature['properties']
        polygon = shape(feature['geometry'])
        if not polygon.is_valid:
            repairs.append(str(props['P_code']))
            polygon = make_valid(polygon)
        assert polygon.is_valid and not polygon.is_empty
        point = polygon.representative_point()  # a reproducible point INSIDE, not an orchard location
        rec = {'province_code': str(props['P_code']), 'province_name': props['P_Name_T'].removeprefix('จังหวัด').strip(),
               'province_name_en': props['P_Name_E'], 'region': regions[str(props['P_code'])],
               'weather_latitude': round(point.y, 5), 'weather_longitude': round(point.x, 5)}
        assert 5 < point.y < 21 and 97 < point.x < 107
        records.append(rec)
        display.append({'type': 'Feature', 'properties': rec,
                        'geometry': mapping(polygon.simplify(0.005, preserve_topology=True))})
    frame = pd.DataFrame(records).sort_values('province_code')
    assert frame.province_code.nunique() == frame.province_name.nunique() == 77
    assert frame.region.notna().all()
    frame.to_csv(OUT / 'province_lookup.csv', index=False, encoding='utf-8-sig')
    save_json(OUT / 'province_display.geojson', {'type': 'FeatureCollection', 'features': display})
    save_json(OUT / 'boundary_checks.json', {'dpm_feature_count': len(dpm['features']),
                                          'selected_source': GISTDA, 'selected_feature_count': len(source['features']),
                                          'geometry_repairs_for_display_and_points': repairs,
                                          'region_supplement': {'91': 'ภาคใต้'}})
    return frame


def production(provinces):
    src = ROOT / 'research_data/external/oae_2026-09-17/durian_province.xlsx'
    assert hashlib.sha256(src.read_bytes()).hexdigest().lower() == '6a3ae44026b5ef8037a8bb091852281d890168a8d795c9c44d5cde9a48613d4c'
    data = pd.read_excel(src, sheet_name='durian')
    assert not data.duplicated(['year', 'province_name', 'item']).any()
    assert set(data['item']) == set(ITEMS)
    for label, unit in [('เนื้อที่ยืนต้น', 'ไร่'), ('เนื้อที่ให้ผล', 'ไร่'), ('ผลผลิต', 'ตัน'), ('ผลผลิตต่อเนื้อที่ให้ผล', 'กิโลกรัมต่อไร่')]:
        assert data.loc[data.item.eq(label), 'unit'].str.strip().eq(unit).all()
    data['year_ce'] = pd.to_numeric(data.year) - 543
    wide = data.pivot(index=['province_name', 'year_ce'], columns='item', values='data').rename(columns=ITEMS).reset_index()
    wide['province_name'] = wide.province_name.str.strip()
    joined = wide.merge(provinces, how='left', on='province_name', validate='many_to_one', indicator=True)
    assert joined['_merge'].eq('both').all(), joined.loc[joined['_merge'].ne('both'), 'province_name'].tolist()
    joined = joined.drop(columns='_merge')
    joined['yield_kg_per_rai_calculated'] = joined.production_tonnes * 1000 / joined.bearing_rai.replace(0, np.nan)
    joined.to_csv(OUT / 'production_province_year.csv', index=False, encoding='utf-8-sig')
    # Country totals are separately downloaded, not silently inferred as complete from 67 provinces.
    path = fetch(OAE + 'b87d403d-16b4-4b1e-9454-18ef4981724c/download/durian_wholecountry.xlsx', RAW / 'durian_wholecountry.xlsx')
    national = pd.read_excel(path)
    national.to_csv(OUT / 'oae_country_source.csv', index=False, encoding='utf-8-sig')
    return joined


def weather_one(rec):
    args = {'parameters': ','.join(PARAMS), 'community': 'AG',
            'longitude': rec['weather_longitude'], 'latitude': rec['weather_latitude'],
            'start': min(YEARS), 'end': max(YEARS), 'format': 'JSON'}
    path = fetch(NASA + '?' + urlencode(args), RAW / 'power' / f"{rec['province_code']}.json")
    obj = json.loads(path.read_text(encoding='utf-8'))
    expected_units = {'T2M': 'C', 'RH2M': '%', 'PRECTOTCORR': 'mm/day', 'ALLSKY_SFC_SW_DWN': 'MJ/m^2/day'}
    assert {key: obj['parameters'][key]['units'] for key in PARAMS} == expected_units
    fill = obj['header']['fill_value']
    rows = []
    for year in YEARS:
        for month in range(1, 13):  # month 13 is source annual summary; NEVER add it as another month
            row = {**rec, 'year_ce': year, 'month': month, 'days': calendar.monthrange(year, month)[1]}
            for key in PARAMS:
                value = obj['properties']['parameter'][key].get(f'{year}{month:02}')
                row[key] = np.nan if value is None or value == fill else float(value)
            row['rain_mm_month'] = row['PRECTOTCORR'] * row['days']
            rows.append(row)
    return rows


def aggregate_weather(monthly):
    records = []
    for (code, year), group in monthly.groupby(['province_code', 'year_ce']):
        row = {'province_code': code, 'year_ce': int(year)}
        for key, target in [('T2M', 'temperature_c'), ('RH2M', 'humidity_pct'), ('ALLSKY_SFC_SW_DWN', 'solar_mj_m2_day')]:
            row[target] = np.average(group[key], weights=group.days) if group[key].notna().sum() == 12 else np.nan
        row['rain_mm_year'] = group.rain_mm_month.sum() if group.rain_mm_month.notna().sum() == 12 else np.nan
        row['complete_weather_months'] = int(group[PARAMS].notna().all(axis=1).sum())
        records.append(row)
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-weather', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    provinces = boundaries()
    prod = production(provinces)
    print(f'Boundaries: {len(provinces)}; regions: {sorted(provinces.region.unique())}', flush=True)
    print(f'OAE: {len(prod)} province-years, {prod.province_code.nunique()} provinces', flush=True)
    if args.skip_weather:
        return
    rows, failures = [], []
    # Conservative concurrency; raw responses are cached and never fetched again on rerun.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(weather_one, rec): rec for rec in provinces.to_dict('records')}
        for number, future in enumerate(as_completed(futures), 1):
            rec = futures[future]
            try:
                rows.extend(future.result())
                print(f"NASA {number}/77: {rec['province_name']} OK", flush=True)
            except Exception as exc:
                failures.append({'province_code': rec['province_code'], 'error': str(exc)})
                print(f"NASA {number}/77: {rec['province_name']} FAILED: {exc}", flush=True)
    save_json(OUT / 'weather_failures.json', failures)
    if not rows:
        raise RuntimeError('No weather data; inspect failures, do not fabricate values')
    monthly = pd.DataFrame(rows).sort_values(['province_code', 'year_ce', 'month'])
    monthly.to_csv(OUT / 'weather_monthly.csv', index=False, encoding='utf-8-sig')
    annual = aggregate_weather(monthly)
    annual.to_csv(OUT / 'weather_annual.csv', index=False, encoding='utf-8-sig')
    grid = provinces.merge(pd.DataFrame({'year_ce': list(YEARS)}), how='cross')
    cols = ['province_code', 'year_ce', *ITEMS.values(), 'yield_kg_per_rai_calculated']
    panel = grid.merge(prod[cols], on=['province_code', 'year_ce'], how='left', validate='one_to_one')
    panel = panel.merge(annual, on=['province_code', 'year_ce'], how='left', validate='one_to_one')
    panel['production_record_available'] = panel.production_tonnes.notna()
    regional_soil = ROOT / 'research_data/regional_orchards/overlay_summaries.json'
    soil_names = [s['province_name'] for s in json.loads(regional_soil.read_text(encoding='utf-8'))] if regional_soil.exists() else ['จันทบุรี']
    # Availability of a fixed map snapshot, NOT time-varying soil observations.
    panel['soil_overlay_available'] = panel.province_name.isin(soil_names)
    panel.to_csv(OUT / 'province_year_panel.csv', index=False, encoding='utf-8-sig')
    save_json(OUT / 'coverage.json', {'boundary_provinces': len(provinces), 'weather_provinces': monthly.province_code.nunique(),
                                    'weather_failures': failures, 'production_provinces_all_years': prod.province_code.nunique(),
                                    'analysis_years': list(YEARS), 'soil_overlay_provinces': soil_names})
    print('Saved joined panel:', len(panel), 'rows; weather failures:', len(failures), flush=True)


if __name__ == '__main__':
    main()
