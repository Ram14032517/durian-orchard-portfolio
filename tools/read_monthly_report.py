"""Read the same local monthly evidence as the map, using only Python stdlib.

Run from VS Code Terminal: python tools/read_monthly_report.py --province 84 --year 2025 --month 7
"""
import argparse
import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'research_data/five_province_history'

def records(name):
    with (BASE / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def find(rows, code, year, month, month_key='month'):
    return next((r for r in rows if r['province_code'] == code
                 and int(r['year_ce']) == year and int(r[month_key]) == month), None)

def display_number(value, unit=''):
    return f'{float(value):,.2f} {unit}'.strip() if value not in (None, '') else 'ไม่มีข้อมูล'

def report(code='84', year=2025, month=7):
    """Print a report and return its source rows for further Python analysis."""
    points = {r['province_code']: r for r in records('reference_points.csv')}
    if code not in points or not 1 <= month <= 12 or not 1981 <= year <= 2026:
        raise ValueError('ใช้จังหวัด 22,33,53,84,86 เดือน 1–12 และปี ค.ศ. 1981–2026')
    weather = records('weather_monthly.csv')
    harvest = records('harvest_monthly.csv')
    evidence = json.loads((BASE / 'phenology_evidence.json').read_text(encoding='utf-8'))
    region = next(r for r in evidence['regions'].values() if code in r['provinces'])
    phases = [p for p in region['periods'] if month in p['months']]
    events = [e for e in evidence['events'] if e['province_code'] == code
              and e['year'] == year and month in e['months']]
    w = find(weather, code, year, month) or {}
    h = find(harvest, code, year, month, 'month_number') or {}
    print(f"\n{points[code]['province_name']} เดือน {month} ปี {year + 543} (ค.ศ. {year})")
    print('\nกรอบระยะทั่วไปของภูมิภาค ไม่ใช่ระยะจริงรายสวน/รายปี:')
    for p in phases:
        print(f"  {evidence['stages'][p['stage']]['label']} — {p['range']}")
    if region.get('note'): print(region['note'])
    print('ที่มา:', evidence['calendar_source']['url'])
    print('\nข้อมูลเดือนที่เลือก:')
    for label, field, unit in [('อุณหภูมิเฉลี่ย', 'temperature_c', '°C'),
                                ('ฝนรวม', 'rain_mm', 'มม.'),
                                ('ความชื้นอากาศ', 'humidity_pct', '%'),
                                ('รังสีดวงอาทิตย์', 'solar_mj_m2_day', 'MJ/m²/วัน')]:
        print(f'  {label}: {display_number(w.get(field), unit)}')
    print(f"  วันมีข้อมูลอุณหภูมิ/ฝน: {w.get('days_temperature', '—')}/{w.get('days_rain', '—')} จาก {w.get('expected_days', '—')} วัน")
    print('  ผลผลิตจังหวัดทุกพันธุ์:', display_number(h.get('tonnes'), 'ตัน'))
    print('อากาศ NASA POWER ณ จุดอ้างอิง ไม่ใช่ค่าเฉลี่ยทั้งจังหวัดหรือค่าที่วัดในสวน')
    print('\nรายงานที่ตรงเดือน–ปี (ไม่มีรายงาน ไม่ได้หมายถึงไม่มีเหตุ):')
    if not events: print('  ยังไม่มีรายงานที่ยืนยันในฐานนี้')
    for event in events:
        print(f"  {event['title']}\n  {event['summary']}\n  เหตุ/กำหนด: {event['event_date']} เผยแพร่: {event.get('published_date') or 'ไม่ระบุ'}\n  {event['url']}")
    print('\nเทียบ 5 จังหวัดในเดือนเดียวกัน:')
    for province, point in points.items():
        other = find(weather, province, year, month) or {}
        output = find(harvest, province, year, month, 'month_number') or {}
        print(f"  {point['province_name']}: {display_number(other.get('temperature_c'), '°C')} | ฝน {display_number(other.get('rain_mm'), 'มม.')} | ผลผลิต {display_number(output.get('tonnes'), 'ตัน')}")
    print('\nแหล่ง/ข้อจำกัด: ', BASE / 'PHENOLOGY_SOURCES_TH.md')
    print('ชุดเตรียมเทรน: ', BASE / 'training/monthly_model_panel.csv')
    return {'weather': w, 'harvest': h, 'phases': phases, 'events': events}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--province', default='84', choices=['22', '33', '53', '84', '86'])
    parser.add_argument('--year', type=int, default=2025, help='ปี ค.ศ.')
    parser.add_argument('--month', type=int, default=7, choices=range(1, 13))
    args = parser.parse_args()
    report(args.province, args.year, args.month)
