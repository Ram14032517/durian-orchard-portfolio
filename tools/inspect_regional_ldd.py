"""Read relevant GIS schemas/encodings/CRS and supplied year evidence."""
from pathlib import Path
import json
import shapefile
from pyproj import CRS

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'research_data/external/ldd_regions_2026-09-18'
if __name__=='__main__':
    for p in RAW.rglob('*.shp'):
        if not (p.name.startswith('Soil_') or p.name.startswith('LU_')):
            continue
        cpg=p.with_suffix('.cpg')
        hint=cpg.read_text().strip() if cpg.exists() else None
        encoding='utf-8' if hint and ('utf' in hint.lower() or hint=='65001') else 'cp874'
        reader=shapefile.Reader(str(p),encoding=encoding)
        row=reader.record(0).as_dict()
        print(json.dumps({'path':str(p.relative_to(RAW)), 'crs':CRS.from_wkt(p.with_suffix('.prj').read_text()).to_string(),
                          'cpg':hint,'encoding':encoding,'count':len(reader),'fields':[f[0] for f in reader.fields[1:]],'sample':row},ensure_ascii=False),flush=True)
    for p in RAW.rglob('*ReadMe*'):
        print(str(p.relative_to(RAW)),p.read_text(encoding='cp874'),flush=True)
