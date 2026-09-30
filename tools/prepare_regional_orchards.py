"""LDD soil overlays and area-weighted weather sampling within mapped A403.

All coordinates come from public LDD land-use polygons, NOT private farm data.
Four different land-use snapshots are intentionally retained and labelled.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import time

import pandas as pd
import shapefile
import shapely
from shapely.geometry import shape, Polygon, MultiPolygon, GeometryCollection, box, mapping
from shapely.ops import transform
from pyproj import CRS, Transformer

from prepare_national_comparison import save_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_data/regional_orchards'
NEW = ROOT/'research_data/external/ldd_regions_2026-09-18'
CONFIG = {
    'cti': {'name':'จันทบุรี','code':'22','region':'ภาคตะวันออก','lu_year':2568,
            'folder':ROOT/'research_data/external/ldd_chanthaburi_2026-09-17'},
    'cpn': {'name':'ชุมพร','code':'86','region':'ภาคใต้','lu_year':2564,'folder':NEW/'cpn'},
    'ssk': {'name':'ศรีสะเกษ','code':'33','region':'ภาคตะวันออกเฉียงเหนือ','lu_year':2565,'folder':NEW/'ssk'},
    'utt': {'name':'อุตรดิตถ์','code':'53','region':'ภาคเหนือ','lu_year':2563,'folder':NEW/'utt'},
}
STEP = 0.25  # stratification only; NOT a claim about NASA spatial resolution


def polygonal(geom):
    if isinstance(geom,(Polygon,MultiPolygon)):
        return geom
    if isinstance(geom,GeometryCollection):
        return shapely.union_all([polygonal(g) for g in geom.geoms])
    return Polygon()


def valid(geom, audit, kind):
    if geom.is_valid:
        return geom
    before = geom.area
    fixed = polygonal(shapely.make_valid(geom))
    audit[kind+'_repaired'] += 1
    audit[kind+'_repair_absolute_area_change_m2'] += abs(fixed.area-before)
    return fixed


def pick_field(fields, choices):
    for name in choices:
        if name in fields:
            return name
    raise ValueError(f'Missing field: {choices}; available={fields}')


def run_province(short, cfg):
    start = time.monotonic()
    folder=cfg['folder']
    soilpath=next((folder/'soil').rglob('Soil_*.shp'))
    landpath=next((folder/'landuse').rglob(f'LU_{short.upper()}_{cfg["lu_year"]}.shp'))
    soil_crs=CRS.from_wkt(soilpath.with_suffix('.prj').read_text())
    land_crs=CRS.from_wkt(landpath.with_suffix('.prj').read_text())
    assert land_crs.is_projected and land_crs.axis_info[0].unit_name=='metre'
    convert_soil=Transformer.from_crs(soil_crs,land_crs,always_xy=True).transform
    to_geo=Transformer.from_crs(land_crs,4326,always_xy=True).transform
    from_geo=Transformer.from_crs(4326,land_crs,always_xy=True).transform
    reader=shapefile.Reader(str(soilpath),encoding='cp874')
    land=shapefile.Reader(str(landpath),encoding='utf-8')
    fields=[f[0] for f in reader.fields[1:]]
    series_key=pick_field(fields,['soilseries','soil_serie'])
    name_key=pick_field(fields,['soilserien','seriesname'])
    qa=Counter()
    soils,soilrows=[],[]
    for sr in reader.iterShapeRecords():
        g=valid(shape(sr.shape.__geo_interface__),qa,'soil')
        if not soil_crs.equals(land_crs):
            g=transform(convert_soil,g)
        soils.append(g)
        soilrows.append(sr.record.as_dict())
    tree=shapely.STRtree(soils)
    stats=defaultdict(lambda:{'pure_m2':0.,'mixed_m2':0.,'names':set(),'textures':set(),'ph':set(),'fertility':set()})
    groups={'pure':[],'mixed':[]}
    audit=[]
    crop_records=[]
    print(f'{short}: soil {len(soils)}, land-use {len(land)}, CRS {soil_crs.to_epsg()} -> {land_crs.to_epsg()}',flush=True)
    for i,r in enumerate(land.iterRecords()):
        code=str(r['LU_CODE']).strip()
        if 'A403' not in code.split('/'):
            continue
        kind='pure' if code=='A403' else 'mixed'
        g=valid(shape(land.shape(i).__geo_interface__),qa,'landuse')
        if g.is_empty:
            qa['empty_crop']+=1
            continue
        groups[kind].append(g)
        crop_records.append({'province_code':cfg['code'],'source_record':i,'landuse_code':code,
                             'kind':kind,'landuse_year_be':cfg['lu_year'],'geometry_rai':g.area/1600})
        hits=[]
        summed=0.
        for j in tree.query(g,predicate='intersects'):
            cut=polygonal(shapely.intersection(g,soils[j]))
            if cut.area<=0:
                continue
            soilrow=soilrows[j]
            key=str(soilrow[series_key]).strip() or '(ไม่ระบุ)'
            stat=stats[key]
            stat[kind+'_m2']+=cut.area
            for dest,keyfield in [('names',name_key),('textures','texture_to'),('ph','pH_top'),('fertility','fertility')]:
                stat[dest].add(str(soilrow[keyfield] or '').strip())
            hits.append(cut)
            summed+=cut.area
        covered=shapely.union_all(hits).area if hits else 0.
        audit.append({'province_code':cfg['code'],'source_record':i,'kind':kind,'landuse_code':code,
                      'geometry_rai':g.area/1600,'covered_rai':covered/1600,
                      'soil_overlap_rai':max(0.,summed-covered)/1600})
        if len(audit)%2500==0:
            print(f'{short}: intersected {len(audit)} crop polygons in {time.monotonic()-start:.0f}s',flush=True)
    sums={}
    unions={}
    for kind,geometries in groups.items():
        union=shapely.union_all(geometries)
        unions[kind]=union
        rows=[r for r in audit if r['kind']==kind]
        area=sum(g.area for g in geometries)/1600
        sums[kind]={'records':len(geometries),'rai':area,'union_rai':union.area/1600,
                    'covered_rai':sum(r['covered_rai'] for r in rows),
                    'uncovered_rai':sum(r['geometry_rai']-r['covered_rai'] for r in rows),
                    'soil_overlap_rai':sum(r['soil_overlap_rai'] for r in rows),
                    'landuse_overlap_rai':max(0.,area-union.area/1600)}
        # Do not publish additive soil shares if overlapping classes duplicate appreciable area.
        assert sums[kind]['soil_overlap_rai']<0.1, (short,kind,sums[kind])
        assert sums[kind]['landuse_overlap_rai']<0.1, (short,kind,sums[kind])
    cross=unions['pure'].intersection(unions['mixed']).area/1600
    assert cross<0.1,(short,'cross-class overlap',cross)
    soil_summary=[]
    for code,rec in stats.items():
        soil_summary.append({'province_code':cfg['code'],'province_name':cfg['name'],'region':cfg['region'],
                             'soil_code':code,'soil_name':' / '.join(sorted(rec['names'])),
                             'soil_year_be':2561,'landuse_year_be':cfg['lu_year'],
                             'pure_rai':rec['pure_m2']/1600,'mixed_rai':rec['mixed_m2']/1600,
                             'share_of_A403_pct':rec['pure_m2']/1600/sums['pure']['rai']*100,
                             **{k:' / '.join(sorted(rec[k])) for k in ['textures','ph','fertility']}})
    # Stratified point quadrature: each sample is inside mapped A403, weighted by
    # ALL A403 area intersecting the 0.25-degree stratum. Not a farm or sensor count.
    crop=unions['pure']
    geo_crop=transform(to_geo,crop)
    x0,y0,x1,y1=geo_crop.bounds
    points=[]
    for gx in range(math.floor(x0/STEP)-1,math.ceil(x1/STEP)+1):
        for gy in range(math.floor(y0/STEP)-1,math.ceil(y1/STEP)+1):
            cell=transform(from_geo,box(gx*STEP,gy*STEP,(gx+1)*STEP,(gy+1)*STEP))
            cut=polygonal(crop.intersection(cell))
            if cut.is_empty or cut.area<=0:
                continue
            part=max(cut.geoms,key=lambda x:x.area) if isinstance(cut,MultiPolygon) else cut
            point=part.representative_point()
            assert crop.covers(point)
            lonlat=transform(to_geo,point)
            points.append({'sample_id':f'{short}_{gx}_{gy}','province_code':cfg['code'],
                           'province_name':cfg['name'],'region':cfg['region'],'landuse_year_be':cfg['lu_year'],
                           'grid_size_degrees':STEP,'grid_x':gx,'grid_y':gy,'longitude':lonlat.x,'latitude':lonlat.y,
                           'A403_area_rai':cut.area/1600,'weight':cut.area/crop.area,'inside_A403':True})
    assert abs(sum(p['weight'] for p in points)-1)<1e-7, (short,'strata areas not exhaustive')
    readme=next((folder/'soil').rglob('00_ReadMe.txt'))
    assert '2561' in readme.read_text(encoding='cp874')
    manifest=[]
    for p in [soilpath,soilpath.with_suffix('.dbf'),soilpath.with_suffix('.prj'),landpath,landpath.with_suffix('.dbf'),landpath.with_suffix('.prj'),readme]:
        manifest.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    result={'province_code':cfg['code'],'province_name':cfg['name'],'region':cfg['region'],
            'soil_year_be':2561,'landuse_year_be':cfg['lu_year'],'soil_source_crs':soil_crs.to_string(),
            'landuse_source_crs':land_crs.to_string(),'soil_features':len(soils),'landuse_features':len(land),
            'soil_code_field':series_key,'soil_name_field':name_key,'qa':dict(qa),'summary':sums,
            'cross_class_overlap_rai':cross,'sample_points':len(points),'sample_area_weight_sum':sum(p['weight'] for p in points),
            'input_manifest':manifest,'elapsed_seconds':round(time.monotonic()-start,1)}
    save_json(OUT/f'{short}_analysis.json',result)
    pd.DataFrame(audit).to_csv(OUT/f'{short}_polygon_audit.csv',index=False,encoding='utf-8-sig')
    print(f'{short}: DONE: {sums["pure"]["rai"]:.1f} A403 rai, {len(points)} sample strata, {time.monotonic()-start:.0f}s',flush=True)
    return result,soil_summary,points


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    summaries,soils,points=[],[],[]
    for short,cfg in CONFIG.items():
        result,ss,pp=run_province(short,cfg)
        summaries.append(result);soils.extend(ss);points.extend(pp)
        # Partial outputs survive interruption; coverage is always explicit.
        save_json(OUT/'overlay_summaries.json',summaries)
        pd.DataFrame(soils).to_csv(OUT/'soil_series_comparison.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(points).to_csv(OUT/'orchard_weather_samples.csv',index=False,encoding='utf-8-sig')
    save_json(OUT/'orchard_sample_points.geojson',{'type':'FeatureCollection','features':[
        {'type':'Feature','properties':p,'geometry':{'type':'Point','coordinates':[p['longitude'],p['latitude']]}} for p in points]})
