"""Export LDD soil polygons for display only (50 m simplification)."""
import json
from pathlib import Path
import shapefile
from shapely.geometry import shape, mapping
from shapely.ops import transform
from pyproj import CRS, Transformer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_data/priority_provinces/soil_layers'
SOURCES = {
    '84': ('สุราษฎร์ธานี', ROOT / 'research_data/external/ldd_surat_2026-09-23/soil'),
    '22': ('จันทบุรี', ROOT / 'research_data/external/ldd_chanthaburi_2026-09-17/soil'),
    '86': ('ชุมพร', ROOT / 'research_data/external/ldd_regions_2026-09-18/cpn/soil'),
    '33': ('ศรีสะเกษ', ROOT / 'research_data/external/ldd_regions_2026-09-18/ssk/soil'),
    '53': ('อุตรดิตถ์', ROOT / 'research_data/external/ldd_regions_2026-09-18/utt/soil'),
}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, (name, folder) in SOURCES.items():
        path = next(folder.rglob('Soil_*.shp'))
        crs = CRS.from_wkt(path.with_suffix('.prj').read_text())
        assert crs.is_projected and crs.axis_info[0].unit_name == 'metre'
        project = Transformer.from_crs(crs, 4326, always_xy=True).transform
        reader = shapefile.Reader(str(path), encoding='cp874')
        features = []
        for item in reader.iterShapeRecords():
            record = item.record.as_dict()
            geom = shape(item.shape.__geo_interface__)
            if geom.is_empty:
                continue
            geom = transform(project, geom.simplify(50, preserve_topology=True))
            props = {'province': name, 'soil_code': str(record.get('soilseries', record.get('soil_serie', 'ไม่ระบุ'))),
                     'soil_name': str(record.get('soilserien', record.get('seriesname', 'ไม่ระบุ'))),
                     'district': str(record.get('AMPHOE_T', 'ไม่ระบุ')),
                     'fertility': str(record.get('fertility', 'ไม่ระบุ')),
                     'topsoil_ph': str(record.get('pH_top', 'ไม่ระบุ')),
                     'topsoil_texture': str(record.get('texture_to', 'ไม่ระบุ')),
                     'source': 'กรมพัฒนาที่ดิน · ปีผลิต 2561 · มาตราส่วนต้นฉบับ 1:25,000',
                     'display_note': 'ลดรายละเอียดเส้น 50 เมตรเพื่อแสดงผล; ไม่ใช้ระบุแนวเขตแปลง'}
            features.append({'type': 'Feature', 'properties': props, 'geometry': mapping(geom)})
        (OUT / f'{code}.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False), encoding='utf-8')
        print(name, len(features), flush=True)

if __name__ == '__main__':
    main()
