"""Check spatial support and same-year area definitions before climate modeling.

This is reconciliation, not calibration: never scale either source to make it
match. Algebraic mixed fractions are diagnostics, NOT estimated durian shares.
"""
from collections import defaultdict
import json
from pathlib import Path
import pandas as pd
import shapefile
from prepare_regional_orchards import CONFIG

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/regional_orchards'


def soil_resolution(code, name):
    """Transparent review tags inferred from source labels, not an LDD field."""
    if code=='W': return 'water'
    if code in {'SC','ES','RL','RC','AC'}: return 'terrain_misc_unit'
    if '-' in code or '/' in code or 'เชิงซ้อน' in name or 'สัมพันธ์' in name:
        return 'complex_or_association'
    if code in {'','(ไม่ระบุ)'} or not name: return 'unidentified'
    return 'named_single_unit_candidate'


def main():
    summaries=json.loads((OUT/'overlay_summaries.json').read_text(encoding='utf-8'))
    production=pd.read_csv(ROOT/'research_data/thailand_comparison/production_province_year.csv',dtype={'province_code':str})
    soil=pd.read_csv(OUT/'soil_series_comparison.csv',dtype={'province_code':str}).fillna({'soil_name':''})
    panel=pd.read_csv(OUT/'regional_province_year_panel.csv',dtype={'province_code':str})
    soil['resolution_review_tag']=[soil_resolution(str(c),str(n)) for c,n in zip(soil.soil_code,soil.soil_name)]
    soil.to_csv(OUT/'soil_resolution_review.csv',index=False,encoding='utf-8-sig')
    inventories,checks=[],[]
    for short,cfg in CONFIG.items():
        s=next(s for s in summaries if s['province_code']==cfg['code'])
        target_year=s['landuse_year_be']-543
        prod=production.loc[production.province_code.eq(cfg['code'])&production.year_ce.eq(target_year)]
        assert len(prod)==1, 'Need exactly one same-year production record'
        oae=prod.iloc[0]
        pure,mixed=s['summary']['pure']['rai'],s['summary']['mixed']['rai']
        path=next((cfg['folder']/'landuse').rglob(f'LU_{short.upper()}_{cfg["lu_year"]}.shp'))
        reader=shapefile.Reader(str(path),encoding='utf-8')
        fields={f[0] for f in reader.fields[1:]}
        area_field=next(k for k in ['Area_Rai','RAI','Area_Sqm','Shape_Area'] if k in fields)
        area_divisor=1 if area_field in ['Area_Rai','RAI'] else 1600
        grouped=defaultdict(lambda:{'records':0,'area':0.})
        for r in reader.iterRecords():
            code,desc=str(r['LU_CODE']).strip(),str(r['LU_DES_TH']).strip()
            if 'A403' not in code.split('/'): continue
            item=grouped[(code,desc)]
            item['records']+=1
            item['area']+=float(r[area_field])/area_divisor
        for (code,desc),item in grouped.items():
            inventories.append({'province_code':cfg['code'],'province_name':cfg['name'],
                'landuse_year_be':s['landuse_year_be'],'landuse_code':code,'source_description_th':desc,
                'records':item['records'],'source_area_field':area_field,'source_area_rai':item['area']})
        source_pure=sum(item['area'] for (c,d),item in grouped.items() if c=='A403')
        pure_descriptions=' | '.join(sorted({d for (c,d) in grouped if c=='A403'}))
        assert pure_descriptions=='ทุเรียน', (short,pure_descriptions)
        areas=soil.loc[soil.province_code.eq(cfg['code'])].groupby('resolution_review_tag').pure_rai.sum()
        fraction=(oae.planted_rai-pure)/mixed if mixed>0 else float('nan')
        years=panel.loc[panel.province_code.eq(cfg['code']),'year_ce']
        row={'province_code':cfg['code'],'province_name':cfg['name'],'landuse_year_be':s['landuse_year_be'],
             'matched_oae_year_ce':target_year,'ldd_A403_rai':pure,'ldd_mixed_polygon_rai':mixed,
             'ldd_all_A403_codes_rai':pure+mixed,'oae_planted_rai':oae.planted_rai,'oae_bearing_rai':oae.bearing_rai,
             'pure_to_oae_planted_pct':pure/oae.planted_rai*100,
             'all_codes_to_oae_planted_pct':(pure+mixed)/oae.planted_rai*100,
             'algebraic_mixed_fraction_to_match':fraction,
             'match_possible_with_fraction_0_to_1':bool(0<=fraction<=1),
             'A403_description_in_source':pure_descriptions,'source_attribute_pure_rai':source_pure,
             'geometry_minus_source_area_rai':pure-source_pure,
             'historical_years_before_landuse_snapshot':int((years<target_year).sum()),
             'total_weather_years':len(years),
             'soil_unmapped_pct':max(0,s['summary']['pure']['uncovered_rai'])/pure*100}
        for tag in ['named_single_unit_candidate','complex_or_association','terrain_misc_unit','water','unidentified']:
            row[tag+'_pct']=areas.get(tag,0.)/pure*100
        checks.append(row)
    result=pd.DataFrame(checks)
    result.to_csv(OUT/'model_readiness.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(inventories).to_csv(OUT/'landuse_code_inventory.csv',index=False,encoding='utf-8-sig')
    print(result[['province_name','landuse_year_be','pure_to_oae_planted_pct','all_codes_to_oae_planted_pct',
                  'algebraic_mixed_fraction_to_match','match_possible_with_fraction_0_to_1','geometry_minus_source_area_rai',
                  'named_single_unit_candidate_pct','historical_years_before_landuse_snapshot']].to_string(index=False))
    return result


if __name__=='__main__': main()
