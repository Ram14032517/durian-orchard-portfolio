"""Build a local, reproducible LDD soil/land-use evidence report (no farm data).

Inputs are preserved government archives, extracted with 7-Zip. Install optional
GIS dependencies in .build/soil-map-packages, or in your own Python environment.
Geometry measurements use the source CRS, EPSG:32647, and 1 rai = 1,600 m².
"""
from __future__ import annotations

import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.build/soil-map-packages'))
import shapefile
import shapely
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import transform
from pyproj import CRS, Transformer

RAW = ROOT / 'research_data/external/ldd_chanthaburi_2026-09-17'
OUT = ROOT / 'research_data/soil_evidence_chanthaburi'
SOURCE_URLS = {
    'soil': 'https://lddcatalog.ldd.go.th/dataset/ldd_11_01',
    'landuse': 'https://lddcatalog.ldd.go.th/dataset/ldd_21_01',
    'soil_download': 'https://tswc.ldd.go.th/DownloadGIS/web_Soil/SoilSeries/E/sr_cti.rar',
    'landuse_download': 'https://tswc.ldd.go.th/DownloadGIS/web_LU/DataLu/E/Landuse_cti.zip',
}
EXPECTED_HASHES = {
    'sr_cti.rar': '216d09529e8615111f3f3ed48b0597696729df66277f749d9fc07908b1e6d530',
    'Landuse_cti.zip': 'b82c6212b98578a2b1f1e5f6f3bec247f4275114e1ff058f53446435ba610bec',
}


def polygonal(g):
    if isinstance(g, (Polygon, MultiPolygon)):
        return g
    if isinstance(g, GeometryCollection):
        return shapely.union_all([polygonal(x) for x in g.geoms])
    return Polygon()


def valid(g, counts, label):
    if not g.is_valid:
        counts[label] += 1
        g = polygonal(shapely.make_valid(g))
    return g


def read_layer(p, encoding):
    crs = CRS.from_wkt(p.with_suffix('.prj').read_text())
    if not crs.equals(CRS.from_epsg(32647)):
        raise ValueError(f'Unexpected CRS: {p}: {crs}')
    return shapefile.Reader(str(p), encoding=encoding)


def run_analysis():
    started = time.monotonic()
    OUT.mkdir(exist_ok=True)
    inputs = []
    for name, expected in EXPECTED_HASHES.items():
        data = (RAW / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise ValueError(f'Input archive changed: {name}')
        inputs.append({'file': name, 'sha256': digest, 'bytes': len(data)})
    soilpath = next((RAW / 'soil').rglob('*.shp'))
    lupath = next((RAW / 'landuse').rglob('LU_CTI_2568.shp'))
    amppath = next((RAW / 'landuse').rglob('*_Amp.shp'))
    soil = read_layer(soilpath, 'cp874')
    land = read_layer(lupath, 'utf-8')
    amps = read_layer(amppath, 'utf-8')
    repairs = Counter()
    soils, soilrows = [], []
    for sr in soil.iterShapeRecords():
        soils.append(valid(shape(sr.shape.__geo_interface__), repairs, 'soil'))
        soilrows.append(sr.record.as_dict())
    tree = shapely.STRtree(soils)
    print(f'Loaded {len(soils)} soil polygons', flush=True)
    by_series = defaultdict(lambda: {'pure_m2': 0., 'mixed_m2': 0., 'parts': 0,
                                     'names': set(), 'textures': set(), 'ph': set(), 'fertility': set()})
    by_code = defaultdict(lambda: {'records': 0, 'geometry_m2': 0., 'source_rounded_rai': 0.})
    by_type = defaultdict(lambda: {'records': 0, 'area_m2': 0., 'covered_m2': 0., 'overlap_m2': 0.})
    land_geoms = {'pure': [], 'mixed': []}
    intersections = defaultdict(list)
    audit_rows = []
    for idx, rec in enumerate(land.iterRecords()):
        code = rec['LU_CODE'].strip()
        if 'A403' not in code.split('/'):
            continue
        kind = 'pure' if code == 'A403' else 'mixed'
        geom = valid(shape(land.shape(idx).__geo_interface__), repairs, 'landuse')
        land_geoms[kind].append(geom)
        by_code[code]['records'] += 1
        by_code[code]['geometry_m2'] += geom.area
        by_code[code]['source_rounded_rai'] += rec['Area_Rai']
        by_code[code]['description'] = rec['LU_DES_TH']
        by_type[kind]['records'] += 1
        by_type[kind]['area_m2'] += geom.area
        hits, sum_area = [], 0.
        # Intersect original-precision shapes. Simplification happens only later.
        for si in tree.query(geom, predicate='intersects'):
            cut = polygonal(shapely.intersection(geom, soils[si]))
            area = cut.area
            if area <= 0:
                continue
            row = soilrows[si]
            key = row['soilseries'] or '(ไม่ระบุ)'
            agg = by_series[key]
            agg[f'{kind}_m2'] += area
            agg['parts'] += 1
            for target, source in [('names', 'soilserien'), ('textures', 'texture_to'), ('ph', 'pH_top'), ('fertility', 'fertility')]:
                agg[target].add(row[source])
            intersections[(key, kind)].append(cut)
            hits.append(cut)
            sum_area += area
        coverage = shapely.union_all(hits).area if hits else 0.
        by_type[kind]['covered_m2'] += coverage
        by_type[kind]['overlap_m2'] += max(0., sum_area - coverage)
        audit_rows.append({'source_record_0_based': idx, 'landuse_code': code,
                           'geometry_rai': geom.area / 1600, 'soil_covered_rai': coverage / 1600,
                           'soil_overlap_rai': max(0., sum_area-coverage) / 1600})
        if len(audit_rows) % 1000 == 0:
            print(f'Intersected {len(audit_rows)} polygons ({time.monotonic()-started:.0f}s)', flush=True)
    stats = []
    for code, vals in by_series.items():
        stats.append({'code': code, 'names': sorted(vals['names']),
                      'pure_rai': vals['pure_m2']/1600, 'mixed_rai': vals['mixed_m2']/1600,
                      'textures': sorted(vals['textures']), 'ph': sorted(vals['ph']),
                      'fertility': sorted(vals['fertility'])})
    stats.sort(key=lambda r: r['pure_rai'], reverse=True)
    summaries = {}
    for kind, vals in by_type.items():
        union = shapely.union_all(land_geoms[kind])
        summaries[kind] = {
            'records': vals['records'], 'rai': vals['area_m2']/1600,
            'covered_rai': vals['covered_m2']/1600,
            'uncovered_rai': (vals['area_m2']-vals['covered_m2'])/1600,
            'soil_overlap_rai': vals['overlap_m2']/1600,
            'landuse_internal_overlap_rai': max(0., vals['area_m2']-union.area)/1600,
        }
        if summaries[kind]['soil_overlap_rai'] > 0.1:
            raise ValueError('Material soil overlaps: cannot safely aggregate')
        if summaries[kind]['landuse_internal_overlap_rai'] > 0.1:
            raise ValueError('Material land-use overlaps: cannot safely aggregate')
    # Also validate that pure and mixed land-use classes do not overlap materially.
    cross_overlap = shapely.intersection(shapely.union_all(land_geoms['pure']), shapely.union_all(land_geoms['mixed'])).area / 1600
    if cross_overlap > 0.1:
        raise ValueError('Material overlap between pure and mixed classes')
    print('Building simplified display geometry', flush=True)
    trans = Transformer.from_crs(32647, 4326, always_xy=True).transform
    def geo(g, tolerance=100):
        display = transform(trans, g.simplify(tolerance, preserve_topology=True))
        return mapping(shapely.orient_polygons(display, exterior_cw=True))
    districts = []
    for sr in amps.iterShapeRecords():
        districts.append({'type': 'Feature', 'properties': {'name': sr.record['AMPHOE_T']},
                          'geometry': geo(shape(sr.shape.__geo_interface__), 100)})
    soil_features = []
    for code in sorted({r['soilseries'] for r in soilrows}):
        gs = [g for g, r in zip(soils, soilrows) if r['soilseries'] == code]
        soil_features.append({'type': 'Feature', 'properties': {'code': code},
                              'geometry': geo(shapely.union_all(gs), 100)})
    crop_features = []
    for (code, kind), gs in intersections.items():
        crop_features.append({'type': 'Feature', 'properties': {'code': code, 'kind': kind},
                              'geometry': geo(shapely.union_all(gs), 30)})
    result = {
        'province': 'จันทบุรี', 'downloaded_date': '2026-09-17',
        'soil_production_year_be': 2561, 'landuse_file_year_be': 2568,
        'soil_year_evidence': str(next((RAW/'soil').rglob('00_ReadMe.txt')).relative_to(ROOT)),
        'landuse_year_evidence': str(lupath.relative_to(ROOT)),
        'soil_features': len(soils), 'landuse_features': len(land), 'sources': SOURCE_URLS,
        'archives': inputs, 'crs': 'EPSG:32647', 'rai_conversion_m2': 1600,
        'repair_counts': dict(repairs), 'summary': summaries, 'soil_stats': stats,
        'cross_class_overlap_rai': cross_overlap,
        'landuse_codes': dict(by_code), 'display_only_simplification_m': {'soil':100,'durian_intersection':30},
        'versions': {'shapely': shapely.__version__, 'pyshp': shapefile.__version__},
    }
    (OUT/'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'polygon_audit.json').write_text(json.dumps(audit_rows, ensure_ascii=False), encoding='utf-8')
    maps = {'districts': districts, 'soil': soil_features, 'crop': crop_features}
    (OUT/'display_geometry.json').write_text(json.dumps(maps, ensure_ascii=False, separators=(',', ':')),encoding='utf-8')
    render_report()
    print(json.dumps({'summary': summaries, 'top5':stats[:5], 'repairs':dict(repairs), 'seconds':time.monotonic()-started},ensure_ascii=False,indent=2))


def render_report():
    """Package the already-computed results into one offline HTML document."""
    data = json.loads((OUT/'analysis.json').read_text(encoding='utf-8'))
    maps = json.loads((OUT/'display_geometry.json').read_text(encoding='utf-8'))
    # D3's spherical projection expects clockwise exterior rings.
    for features in maps.values():
        for feature in features:
            feature['geometry'] = mapping(shapely.orient_polygons(shape(feature['geometry']), exterior_cw=True))
    def safe_json(obj):
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    template = (ROOT/'tools/soil_evidence_report.html').read_text(encoding='utf-8')
    rendered = template.replace('/*__D3__*/', (ROOT/'.build/soil-evidence/d3.min.js').read_text(encoding='utf-8'))
    rendered = rendered.replace('__ANALYSIS_JSON__', safe_json(data)).replace('__GEOMETRY_JSON__', safe_json(maps))
    (OUT/'START_HERE.html').write_text(rendered, encoding='utf-8')
    print(f'Report: {OUT / "START_HERE.html"}', flush=True)


if __name__ == '__main__':
    if '--render-only' in sys.argv:
        render_report()
    else:
        run_analysis()
