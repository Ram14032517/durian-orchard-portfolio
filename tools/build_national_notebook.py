"""Build and execute a source-backed Jupyter analysis and its offline map output."""
from __future__ import annotations

import html
import json
import math
import os
from pathlib import Path
import re
import sys
import textwrap

import folium
from branca.element import MacroElement
from jinja2 import Template
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_national_comparison import fetch, save_json

OUT = ROOT / 'research_data/thailand_comparison'
NOTEBOOK = ROOT / 'notebooks/02_thailand_durian_comparison.ipynb'


def build_map(panel, provinces, soil_result):
    """One map visualization exported from the notebook, not a hosted web app."""
    geometry = json.loads((OUT / 'province_display.geojson').read_text(encoding='utf-8'))
    metric_defs = {
        'yield_kg_per_rai_source': ('ผลผลิตต่อไร่ (กก./ไร่)', 'กก./ไร่', 0, 500),
        'production_tonnes': ('ผลผลิตรวม (ตัน)', 'ตัน', 0, 100000),
        'temperature_c': ('อุณหภูมิเฉลี่ยปี (°C)', '°C', 1, 5),
        'humidity_pct': ('ความชื้นอากาศเฉลี่ย (%)', '%', 1, 10),
        'rain_mm_year': ('ฝนสะสมประมาณ (มม./ปี)', 'มม./ปี', 0, 1000),
        'solar_mj_m2_day': ('รังสีอาทิตย์ (MJ/m²/วัน)', 'MJ/m²/วัน', 1, 5),
    }
    metrics = {}
    for key, (label, short, decimals, step) in metric_defs.items():
        lo = 0 if key in ['yield_kg_per_rai_source', 'production_tonnes', 'rain_mm_year'] else math.floor(panel[key].min()/step)*step
        hi = math.ceil(panel[key].max()/step)*step
        metrics[key] = {'label': label, 'short': short, 'decimals': decimals,
                        'legend_decimals': 1 if key in ['temperature_c', 'solar_mj_m2_day'] else 0, 'min': lo, 'max': hi}
    map_obj = folium.Map(location=[13, 101], tiles=None, zoom_start=6, control_scale=True,
                         prefer_canvas=False, height=850, zoom_snap=0.1)
    map_obj.default_js = [('leaflet', 'https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js')]
    map_obj.default_css = [('leaflet_css', 'https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css')]
    geo = folium.GeoJson(geometry, name='จังหวัด', smooth_factor=0,
                         style_function=lambda feature: {'color': '#7c8882', 'weight': 0.7, 'fillOpacity': 0.9}).add_to(map_obj)
    controls = MacroElement()
    controls._template = Template((ROOT / 'tools/national_map_controls.html').read_text(encoding='utf-8'))
    controls.rows = json.loads(panel.to_json(orient='records', force_ascii=False))
    controls.provinces = json.loads(provinces.to_json(orient='records', force_ascii=False))
    controls.metrics = metrics
    controls.map_name, controls.geo_name = map_obj.get_name(), geo.get_name()
    ranked = sorted(soil_result['soil_stats'], key=lambda x: -x['pure_rai'])[:5]
    controls.soil = {'22': {'top': [{'code': s['code'], 'name': ' / '.join(s['names']), 'rai': s['pure_rai']} for s in ranked],
                     'total': soil_result['summary']['pure']['rai'], 'mixed':soil_result['summary']['mixed']['rai'], 'soil_year':2561,'lu_year':2568}}
    regional = ROOT/'research_data/regional_orchards'
    if (regional/'soil_series_comparison.csv').exists() and (regional/'overlay_summaries.json').exists():
        soil_table = pd.read_csv(regional/'soil_series_comparison.csv',dtype={'province_code':str})
        for s in json.loads((regional/'overlay_summaries.json').read_text(encoding='utf-8')):
            g=soil_table.loc[soil_table.province_code.eq(s['province_code'])].nlargest(5,'pure_rai')
            controls.soil[s['province_code']]={'top':[{'code':r.soil_code,'name':r.soil_name,'rai':r.pure_rai} for r in g.itertuples()],
                'total':s['summary']['pure']['rai'],'mixed':s['summary']['mixed']['rai'],'soil_year':s['soil_year_be'],'lu_year':s['landuse_year_be']}
    controls.soil_count = len(controls.soil)
    map_obj.add_child(controls)
    rendered = map_obj.get_root().render()
    # Keep library notices. Inline these two versioned public assets; no map tiles,
    # external fonts, API keys, or network access are needed to view saved output.
    vendor = ROOT / '.build/national-map-vendor'
    for kind, url in [('js', map_obj.default_js[0][1]), ('css', map_obj.default_css[0][1])]:
        path = fetch(url, vendor / f'leaflet-1.9.3.{kind}')
        content = path.read_text(encoding='utf-8')
        if kind == 'js':
            content = content.replace('</script', '<\\/script')
            rendered = rendered.replace(f'<script src="{url}"></script>', '<script>' + content + '</script>')
        else:
            # No markers/layer-control sprites used in this visualization.
            content = re.sub(r'url\([^)]*\)', 'none', content)
            rendered = rendered.replace(f'<link rel="stylesheet" href="{url}"/>', '<style>' + content + '</style>')
    assert not re.search(r'<script[^>]+src=|<link[^>]+href=', rendered), 'Unexpected online dependency'
    rendered = rendered.replace('<head>', '<head><title>แผนที่เปรียบเทียบทุเรียนประเทศไทย</title>', 1)
    path = OUT / 'THAILAND_MAP.html'
    path.write_text(rendered, encoding='utf-8')
    save_json(OUT / 'map_metrics.json', metrics)
    return path


def main():
    cells = []
    def md(source):
        cells.append(nbformat.v4.new_markdown_cell(textwrap.dedent(source).strip()))
    def code(source):
        cells.append(nbformat.v4.new_code_cell(textwrap.dedent(source).strip()))

    md('''
    # ประเทศไทย: เปรียบเทียบผลผลิตทุเรียน อากาศ และหลักฐานดิน

    ## สรุปสั้น
    สมุดวิเคราะห์ Jupyter จากข้อมูลจริง ไม่ใช่ระบบทำนายผลผลิตสำเร็จรูป
    ดูประเทศไทยรวม → 6 ภาค → จังหวัด บนแผนที่กดได้ และเลือกเทียบสองจังหวัด
    - ขอบเขตแผนที่ **77 จังหวัด** จากบริการ GISTDA; ผลผลิต สศก. **67 จังหวัด** ในไฟล์ปี 2540–2568
    - อากาศ NASA POWER ปี **2564–2568** ที่จุดอ้างอิงหนึ่งจุดต่อจังหวัด ไม่ใช่สถานีสวน
    - **ดินใต้พื้นที่ทุเรียนดูสถานะ coverage ด้านล่าง**: เพิ่ม 4 จังหวัดใน notebook 03 แล้ว; แผนที่ใช้ที่ดินแต่ละจังหวัดต่างปี
    - notebook 03 เพิ่มอากาศ 20 ปี ณ จุดใน A403; **อากาศในแผนที่นี้ยังเป็นจุดอ้างอิงจังหวัดเดิม** เพื่อไม่ปนวิธีคำนวณ
    - จังหวัดที่ไม่มีระเบียนไม่ถูกแทนเป็นศูนย์ ผลผลิตไม่แยกพันธุ์หมอนทอง

    ใช้ศึกษา/แสดงอาจารย์ในเครื่องก่อน ยังไม่ได้เผยแพร่ชุดข้อมูลหรือส่งขึ้น GitHub
    ''')
    md('''
    ## เปิดอย่างไร และกำลังเรียนรู้อะไร
    ใน VS Code เปิดไฟล์นี้ → Select Kernel → Python Environments → เลือก
    `C:/project/.build/national-analysis-venv/Scripts/python.exe` → Run All
    หากยังไม่มีส่วนขยาย ใช้ Python และ Jupyter ของ Microsoft; ไม่ต้องล็อกอิน GitHub
    หรือเปิดด้วย Anaconda Jupyter ที่มีแพ็กเกจตาม `tools/requirements-national-analysis.txt`

    ลำดับบทเรียน: pandas อ่านข้อมูล → join จังหวัด/ปี → ตรวจ missing/unit →
    groupby แบบมีตัวหาร → กราฟเปรียบเทียบ → Folium แผนที่ → ข้อจำกัดก่อนโมเดล
    ผลลัพธ์แผนที่ที่ export อยู่ `research_data/thailand_comparison/THAILAND_MAP.html`
    ส่วนนี้เป็นผลภาพของ notebook ไม่ใช่การสร้างเว็บบริการใหม่
    ''')
    md('''
    ## บริบทและวิธีวิเคราะห์
    หน่วยวิเคราะห์หลักคือ **จังหวัด × ปี**; ใช้ปีปฏิทิน 2021–2025 เทียบกันในรอบทดลองนี้
    ยังไม่จับช่วงอากาศตามระยะออกดอก/ติดผลของแต่ละภูมิภาค จึงยังสรุปผลของอากาศต่อผลผลิตไม่ได้

    | ข้อมูล | แหล่งจริง | การตีความ |
    |---|---|---|
    | ผลผลิต/เนื้อที่ให้ผล | [สศก.](https://catalog.oae.go.th/dataset/durian_product) | ผลผลิตตัน, พื้นที่ไร่; ไม่ใช่ผลผลิตต้นหนึ่งหรือดินชนิดหนึ่ง |
    | ขอบเขตจังหวัด | [GISTDA / DOPA](https://gistdaportal.gistda.or.th/arcgis/rest/services/ข้อมูลเขตการปกครอง/MapServer/2) | source date ใน attribute 2013-12-30; ใช้ทำแผนที่ ไม่ใช่รังวัด |
    | การแบ่งภาค | [DPM REGION_6](https://gis-portal.disaster.go.th/arcgis/rest/services/MapDX/DPM_TH_Boundary/FeatureServer/1) | แหล่งนี้ขาดสตูล จึงใช้เพียงตารางภาคและเติมสตูลเป็นภาคใต้; ไม่ใช่กลุ่มภาคในตาราง สศก. |
    | อากาศ | [NASA POWER monthly](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/) | อุณหภูมิ/ความชื้น/ฝนเป็น reanalysis กริด; 1 จุดอ้างอิงที่อยู่ภายในขอบเขตจังหวัด |
    | ดิน × การใช้ที่ดิน | [LDD ดิน](https://lddcatalog.ldd.go.th/dataset/ldd_11_01), [LDD การใช้ที่ดิน](https://lddcatalog.ldd.go.th/dataset/ldd_21_01) | คำนวณ spatial intersection; เพิ่มจันทบุรี ชุมพร ศรีสะเกษ อุตรดิตถ์ใน notebook 03; ไม่สมมติว่าจังหวัดมีดินชนิดเดียว |

    อากาศ: MERRA-2 โดยทั่วไปกริด 0.5° × 0.625°, รังสีอาทิตย์มาจาก SYN1DEG;
    [รายละเอียดวิธี NASA](https://power.larc.nasa.gov/docs/methodology/meteorology/)
    เวลาใช้ LST ตาม API ไม่ใช่ timezone สวน แหล่งนี้ไม่ใช่ yr.no และไม่ใช้แทนการตรวจเทียบสถานีสวนโดยตรง
    ''')
    code('''
    from pathlib import Path
    import json, sys
    import numpy as np
    import pandas as pd
    from IPython.display import display, HTML

    root = next(p for p in [Path.cwd(), *Path.cwd().parents]
                if (p/'research_data/thailand_comparison/province_year_panel.csv').exists())
    folder = root/'research_data/thailand_comparison'
    panel = pd.read_csv(folder/'province_year_panel.csv', dtype={'province_code': str})
    provinces = pd.read_csv(folder/'province_lookup.csv', dtype={'province_code': str})
    monthly = pd.read_csv(folder/'weather_monthly.csv', dtype={'province_code': str})
    soil_result = json.loads((root/'research_data/soil_evidence_chanthaburi/analysis.json').read_text(encoding='utf-8'))
    YEAR = 2025  # ทดลองเปลี่ยน 2021–2025 แล้ว Run All; แผนที่มีปุ่มเลือกปีของตัวเอง
    SELECTED_PROVINCES = ['จันทบุรี', 'ชุมพร', 'ศรีสะเกษ', 'อุตรดิตถ์']
    current = panel.loc[panel.year_ce.eq(YEAR)].copy()
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.float_format', lambda x: f'{x:,.2f}')
    print('ข้อมูลร่วม:', panel.shape, '| ปี:', sorted(panel.year_ce.unique()))
    ''')
    md('''
    ## ข้อมูล: ตรวจให้แน่ใจก่อนเปรียบเทียบ
    missing ไม่ใช่ 0; ฝนใน API มีหน่วย **mm/day** เป็นอัตราเฉลี่ยรายเดือน
    จึงคูณจำนวนวันในเดือนก่อนรวมรายปี ไม่บวกอัตราเฉลี่ยเข้าด้วยกัน
    อุณหภูมิ/ความชื้น/รังสีอาทิตย์เฉลี่ยถ่วงจำนวนวันในเดือน ต้องครบ 12 เดือน
    ข้ามรหัสเดือน 13 ซึ่งเป็นสรุปรายปีของ API ไม่เติม missing และไม่แทรกค่าช่วงสถานีสวนค้าง
    ''')
    code('''
    assert not panel.duplicated(['province_code','year_ce']).any()
    assert len(panel) == 77 * 5
    assert provinces.province_code.nunique() == 77
    assert set(monthly.month.unique()) == set(range(1,13))
    assert panel.complete_weather_months.eq(12).all()
    assert panel.temperature_c.between(-10, 45).all()
    assert panel.humidity_pct.between(0,100).all()
    assert panel.rain_mm_year.ge(0).all()
    coverage = panel.groupby('year_ce').agg(
        provinces=('province_code','size'), production_records=('production_tonnes','count'),
        weather_records=('temperature_c','count'), soil_overlay_provinces=('soil_overlay_available','sum'))
    display(coverage)
    print('จังหวัดที่ไม่มีระเบียนผลผลิตในปีเลือก:', ', '.join(current.loc[current.production_tonnes.isna(),'province_name']))
    print('จำนวนจังหวัดที่รายงานต่างกันตามปี: อย่าตีความระเบียนที่เพิ่งปรากฏว่าเพิ่งเริ่มปลูก')
    print('จังหวัดที่ซ้อนดินแล้ว:', ', '.join(current.loc[current.soil_overlay_available,'province_name']))
    print('สถานะดินคือ snapshot ไม่ใช่ชุดข้อมูลดินที่เปลี่ยนตามปีผลผลิต; รายละเอียดข้ามภาคดู notebook 03')
    ''')
    md('''
    ## ผลเปรียบเทียบ
    ### 1. แผนที่ประเทศไทยแบบกดจังหวัด
    สีเริ่มต้นคือผลผลิตต่อไร่ เพื่อไม่ให้จังหวัดใหญ่ดูดีกว่าเพียงเพราะพื้นที่มาก
    สลับตัวชี้วัดดูปริมาณรวม อุณหภูมิ ความชื้น ฝน และรังสีอาทิตย์ได้
    มีเมนูจังหวัดเป็นทางเลือกแทนการคลิกพื้นที่เล็ก และตารางเทียบ A/B
    ''')
    code('''
    import html
    sys.path.insert(0, str(root/'tools'))
    from build_national_notebook import build_map
    map_path = build_map(panel, provinces, soil_result)
    map_html = map_path.read_text(encoding='utf-8')
    display(HTML('<iframe title="แผนที่เปรียบเทียบทุเรียนประเทศไทย" style="width:100%;height:880px;border:1px solid #ddd" srcdoc="'
                 + html.escape(map_html, quote=True) + '"></iframe>'))
    print('ผลลัพธ์แผนที่เปิดแยกได้:', map_path)
    ''')
    md('''
    ### 2. ประเทศไทยรวมและรายภาค
    คำนวณผลผลิตต่อไร่ = ผลรวมตัน × 1,000 ÷ ผลรวมเนื้อที่ให้ผล
    **ไม่เฉลี่ยผลผลิตต่อไร่ของแต่ละจังหวัดตรง ๆ**
    ผลรวมจังหวัดตรวจเทียบกับไฟล์ประเทศที่ดาวน์โหลดแยกอีกชุด
    แสดงความต่างไว้ ไม่ปรับตัวเลขให้ตรงกันเอง
    ''')
    code('''
    regions = current.groupby('region').agg(
        production_tonnes=('production_tonnes',lambda x: x.sum(min_count=1)),
        bearing_rai=('bearing_rai',lambda x: x.sum(min_count=1)),
        observed_provinces=('production_tonnes','count'), total_provinces=('province_code','size'))
    regions['yield_kg_rai_weighted'] = regions.production_tonnes * 1000 / regions.bearing_rai.replace(0,np.nan)
    regions = regions.sort_values('production_tonnes', ascending=False)
    display(regions)
    regions.to_csv(folder/'region_summary_selected_year.csv', encoding='utf-8-sig')
    country_raw = pd.read_csv(folder/'oae_country_source.csv')
    official = country_raw.pivot(index='year', columns='item', values='data')
    sums = panel.groupby('year_ce')[['production_tonnes','bearing_rai']].sum(min_count=1)
    sums['country_production_source_tonnes'] = [official.loc[y+543,'ผลผลิต'] for y in sums.index]
    sums['difference_tonnes'] = sums.production_tonnes - sums.country_production_source_tonnes
    sums['yield_kg_rai_weighted'] = sums.production_tonnes * 1000 / sums.bearing_rai
    sums['production_change_pct'] = sums.production_tonnes.pct_change() * 100
    sums['bearing_area_change_pct'] = sums.bearing_rai.pct_change() * 100
    sums['yield_change_pct'] = sums.yield_kg_rai_weighted.pct_change() * 100
    display(sums)
    sums.to_csv(folder/'country_reconciliation.csv', encoding='utf-8-sig')
    if YEAR > sums.index.min():
        r = sums.loc[YEAR]
        print(f'ปี {YEAR+543} เทียบปีก่อน: ผลผลิต {r.production_change_pct:+.1f}%, '
              f'เนื้อที่ให้ผล {r.bearing_area_change_pct:+.1f}%, ผลผลิตต่อไร่ {r.yield_change_pct:+.1f}%')
        print('ปริมาณผลผลิตรวมเปลี่ยนทั้งจากขนาดพื้นที่ให้ผลและผลผลิตต่อไร่ — ไม่ใช่อากาศอย่างเดียว')
    es = current.loc[current.region.isin(['ภาคตะวันออก','ภาคใต้']),'production_tonnes'].sum()
    print(f'ภาคตะวันออก + ภาคใต้คิดเป็น {es/current.production_tonnes.sum()*100:.1f}% ของผลรวมจังหวัดที่มีระเบียน')
    ''')
    md('### 3. จังหวัดที่ผลผลิตมาก และผลผลิตต่อไร่รายภาค\nแกนแท่งเริ่มศูนย์ ตัวเลขผลผลิตมากไม่ใช่หลักฐานว่าดิน/สภาพอากาศดีที่สุด')
    code('''
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, ticker
    thai_font = Path('C:/Windows/Fonts/tahoma.ttf')
    if thai_font.exists():
        font_manager.fontManager.addfont(str(thai_font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(thai_font)).get_name()
    plt.rcParams.update({'figure.facecolor':'white','axes.facecolor':'white','font.size':11,
                         'axes.spines.top':False,'axes.spines.right':False,
                         'text.color':'#171717','axes.labelcolor':'#171717','axes.edgecolor':'#999999',
                         'savefig.facecolor':'white','axes.unicode_minus':False})
    top = current.dropna(subset=['production_tonnes']).nlargest(12,'production_tonnes').sort_values('production_tonnes')
    fig,ax = plt.subplots(figsize=(10,6.8),layout='constrained')
    ax.barh(top.province_name,top.production_tonnes,color='#1f6f5f',height=.62)
    ax.set_title(f'12 จังหวัดที่มีผลผลิตทุเรียนมากที่สุด · พ.ศ. {YEAR+543}',loc='left',pad=14)
    ax.set_xlabel('ผลผลิตรวม (ตัน) · ไม่ใช่ผลผลิตต่อไร่')
    ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
    ax.set_xlim(0,top.production_tonnes.max()*1.20)
    for y,v in enumerate(top.production_tonnes): ax.text(v+top.production_tonnes.max()*.012,y,f'{v:,.0f}',va='center',fontsize=10)
    fig.supxlabel('แหล่ง: สศก. durian_province.xlsx · ดาวน์โหลด 17 ก.ย. 2569 · ไม่แยกพันธุ์หมอนทอง',fontsize=9,color='#5e6462')
    fig.savefig(folder/'production_top12.png',dpi=140)
    plt.show()
    r = regions.sort_values('yield_kg_rai_weighted')
    fig,ax = plt.subplots(figsize=(10,4.8),layout='constrained')
    ax.barh(r.index,r.yield_kg_rai_weighted,color='#1f6f5f',height=.55)
    ax.set_title(f'ผลผลิตต่อไร่รายภาค · ถ่วงด้วยเนื้อที่ให้ผล · พ.ศ. {YEAR+543}',loc='left',pad=14)
    ax.set_xlabel('กิโลกรัม / ไร่ที่ให้ผล · ผลคำนวณจากจังหวัดที่มีระเบียน')
    ax.set_xlim(0,r.yield_kg_rai_weighted.max()*1.16)
    for y,v in enumerate(r.yield_kg_rai_weighted): ax.text(v+10,y,f'{v:,.0f}',va='center')
    fig.supxlabel('แหล่ง: สศก. · ผลรวมตาม DPM REGION_6 + สตูลภาคใต้ · ไม่ใช่ตารางภาคที่ สศก. เผยแพร่โดยตรง',fontsize=9,color='#5e6462')
    fig.savefig(folder/'region_weighted_yield.png',dpi=140)
    plt.show()
    ''')
    md('''
    ### 4. เทียบจังหวัดข้ามภาค และอากาศกับผลผลิต
    ตารางใช้ตัวชี้วัดคนละหน่วยแยกคอลัมน์; รังสีอาทิตย์ MJ/m²/วันไม่ใช่ lux หรือ NDVI
    scatter เป็นเพียงการสำรวจความสัมพันธ์ ไม่สร้างเส้นพยากรณ์หรือสรุปว่าอากาศทำให้ผลผลิตเปลี่ยน
    จังหวัดต่างกันทั้งพันธุ์ อายุสวน การให้น้ำ พื้นที่ให้ผล และจุดอ้างอิงอากาศ
    ''')
    code('''
    columns = ['province_name','region','production_tonnes','bearing_rai','yield_kg_per_rai_source',
               'temperature_c','humidity_pct','rain_mm_year','solar_mj_m2_day','soil_overlay_available']
    display(current.loc[current.province_name.isin(SELECTED_PROVINCES),columns].set_index('province_name'))
    comparison = current.dropna(subset=['temperature_c','yield_kg_per_rai_source'])
    fig,ax = plt.subplots(figsize=(10,6),layout='constrained')
    ax.scatter(comparison.temperature_c,comparison.yield_kg_per_rai_source,s=30,c='#7f8984',alpha=.75)
    for name in SELECTED_PROVINCES:
        r = comparison.loc[comparison.province_name.eq(name)].iloc[0]
        ax.scatter([r.temperature_c],[r.yield_kg_per_rai_source],s=42,c='#1f6f5f')
        ax.annotate(name,(r.temperature_c,r.yield_kg_per_rai_source),xytext=(6,6),textcoords='offset points',fontsize=10)
    ax.set_title(f'อากาศกับผลผลิตต่อไร่ · ปี {YEAR+543} · {len(comparison)} จังหวัด',loc='left',pad=14)
    ax.set_xlabel('อุณหภูมิเฉลี่ยปี ณ จุดอ้างอิงจังหวัด (°C) · NASA POWER')
    ax.set_ylabel('ผลผลิตต่อไร่ตาม สศก. (กก./ไร่)')
    ax.set_ylim(bottom=0)
    fig.supxlabel('แหล่ง: NASA POWER + สศก. · จุดอ้างอิงจังหวัดไม่ใช่พิกัดสวน · ความสัมพันธ์ไม่ยืนยันเหตุและผล',fontsize=9,color='#5e6462')
    fig.savefig(folder/'temperature_yield_exploration.png',dpi=140)
    plt.show()
    ''')
    md('''
    ### 5. ตัวอย่างวิธีอ่านดิน: จันทบุรี
    พื้นที่ทุเรียนรหัส A403 ตรงตัวซ้อนกับแผนที่ดินจันทบุรี ไม่รวมรหัสปลูกผสม
    ตัวหารสัดส่วนคือ A403 ทั้งหมดรวมส่วนที่เชื่อมดินไม่ได้
    **นี่ไม่ใช่ผลผลิตรายชุดดิน** และไม่ใช่ค่าความชื้นดินปัจจุบัน
    ''')
    code('''
    soil = pd.DataFrame(soil_result['soil_stats'])
    soil['name'] = soil.names.map(lambda x:' / '.join(x))
    soil['share_of_all_A403_pct'] = soil.pure_rai / soil_result['summary']['pure']['rai'] * 100
    display(soil.sort_values('pure_rai',ascending=False)[['code','name','pure_rai','share_of_all_A403_pct','textures','ph']].head(10))
    print('ซ้อนดินไม่ได้:',round(soil_result['summary']['pure']['uncovered_rai'],2),'ไร่')
    print('หน่วย W พื้นที่น้ำซ้อน A403:',round(soil.loc[soil.code.eq('W'),'pure_rai'].sum(),2),'ไร่ — ต้องสอบทานต่างปี/รูปทรง/ประเภท')
    print('SC เป็นพื้นที่ลาดชันเชิงซ้อน ไม่ใช่ชื่อชุดดินเฉพาะ')
    ''')
    md('''
    ## ข้อสรุป / การทำต่อ
    1. ใช้เปรียบเทียบปริมาณ ผลผลิตต่อไร่ และบริบทอากาศข้ามจังหวัด/ภาค พร้อมเปิดแหล่งที่มาได้แล้ว
    2. ยังเปรียบเทียบดินทั้งประเทศไม่ได้; notebook 03 เพิ่ม 4 จังหวัดข้ามภาคแล้ว แต่ต้องตรวจต่างปี/สวนผสม/ใบอนุญาต
    3. notebook 03 เพิ่มอากาศย้อนหลัง 20 ปีบนพื้นที่ A403 อ้างอิงคงที่แล้ว; ยังต้องจับฤดูออกดอก/ติดผลและแก้ความเสี่ยงใช้พื้นที่อนาคต
    4. โมเดลแรกควรทำนายผลผลิตต่อไร่จังหวัดปีถัดไป เทียบ baseline “เท่าปีก่อน”; แบ่ง train/test ตามเวลาและกันจังหวัดไว้ทดสอบ ไม่สุ่มแถวปนปี
    5. อุณหภูมิ ±1°C ยังไม่ใช่เหตุผลให้คำนวณผลผลิตแบบ causal; ต้องออกแบบสมมติฐาน/ปัจจัยกวนและแสดง uncertainty
    6. ข้อมูลสวน 15 นาทีเป็นงานตรวจเทียบสถานีอีกระดับหนึ่ง: ใช้ outdoor fields และตัดช่วง gateway ค้างจาก weather features โดยเก็บ raw เดิม
    7. ยังไม่สรุปสุขภาพต้น/ลิตรให้น้ำ/ความเหมาะสมดินจากตารางนี้ ไม่มี label สุขภาพต้นหรือการสอบเทียบดิน

    ## ข้อจำกัดการเผยแพร่
    OAE metadata ระบุ CC Attribution Non-Commercial; LDD ระบุ CC Attribution Non-Commercial No-Derivs
    ไม่ระบุรุ่นใบอนุญาต ส่วนขอบเขตต้องยืนยันเงื่อนไขเพิ่มเติมก่อนเผยแพร่
    จึงเก็บ raw/ผลสืบเนื่องไว้ในเครื่อง ไม่ส่งข้อมูลชุดนี้ขึ้น public repo อัตโนมัติ
    URL, request parameters, เวลาดาวน์โหลด UTC และ SHA-256 อยู่ใน `research_data/external/national_2026-09-17`
    อ่าน `README_TH.md` และ `VALIDATION_TH.md` ในโฟลเดอร์ผลวิเคราะห์ประกอบ
    ''')
    nb = nbformat.v4.new_notebook(cells=cells, metadata={
        'kernelspec': {'display_name':'Durian national analysis','language':'python','name':'durian-national'},
        'language_info': {'name':'python','version':sys.version.split()[0]}})
    nbformat.validate(nb)
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, NOTEBOOK)
    os.environ['JUPYTER_PATH'] = str(ROOT / '.build/national-analysis-venv/share/jupyter') + os.pathsep + os.environ.get('JUPYTER_PATH','')
    NotebookClient(nb, timeout=180, kernel_name='durian-national', resources={'metadata':{'path':str(ROOT)}}).execute()
    nbformat.validate(nb)
    assert all(not any(o.output_type=='error' for o in c.get('outputs',[])) for c in nb.cells)
    nbformat.write(nb, NOTEBOOK)
    exporter = HTMLExporter(template_name='lab')
    exported, _ = exporter.from_notebook_node(nb)
    (OUT / 'ANALYSIS_NOTEBOOK.html').write_text(exported, encoding='utf-8')
    print('Executed native Jupyter notebook:', NOTEBOOK, flush=True)
    print('Map:', OUT / 'THAILAND_MAP.html', flush=True)
    print('Saved report:', OUT / 'ANALYSIS_NOTEBOOK.html', flush=True)


if __name__ == '__main__':
    main()
