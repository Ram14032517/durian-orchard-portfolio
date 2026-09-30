"""Fetch public LDD archives linked from the official GIS download indexes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess

from prepare_national_comparison import fetch

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'research_data/external/ldd_regions_2026-09-18'
BASE = 'https://tswc.ldd.go.th/DownloadGIS/'
PROVINCES = {'cpn': ('ชุมพร', 'S'), 'ssk': ('ศรีสะเกษ', 'NE'), 'utt': ('อุตรดิตถ์', 'N')}


def run_one(code, folder, kind):
    if kind == 'soil':
        name, part = f'sr_{code}.rar', f'web_Soil/SoilSeries/{folder}/sr_{code}.rar'
    else:
        name, part = f'Landuse_{code}.zip', f'web_LU/DataLu/{folder}/Landuse_{code}.zip'
    archive = fetch(BASE+part, RAW/code/name)
    target = (RAW/code/kind).resolve()
    assert target.is_relative_to(RAW.resolve())
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([r'C:\Program Files\7-Zip\7z.exe', 'x', str(archive), '-o'+str(target), '-aos'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-1000:]+result.stderr[-1000:])
    return {'province':code, 'kind':kind, 'bytes':archive.stat().st_size,
            'shapefiles':[str(p.relative_to(RAW)) for p in target.rglob('*.shp')]}


if __name__ == '__main__':
    for name in ['Index_Soil.html','Index_Lu.html']:
        fetch(BASE+name, RAW/name)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(run_one,code,region,kind) for code,(_,region) in PROVINCES.items() for kind in ['soil','landuse']]
        for job in as_completed(jobs):
            print(job.result(), flush=True)
