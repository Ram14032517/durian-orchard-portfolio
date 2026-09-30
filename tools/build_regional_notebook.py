"""Build and execute the four-region research notebook; no online publication."""
from pathlib import Path
import os
import sys
import textwrap
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_data/regional_orchards'
NOTEBOOK = ROOT/'notebooks/03_regional_orchards_soil_weather.ipynb'


def main():
    from audit_regional_readiness import main as audit_readiness
    audit_readiness()
    cells = []
    def md(s): cells.append(nbformat.v4.new_markdown_cell(textwrap.dedent(s).strip()))
    def code(s): cells.append(nbformat.v4.new_code_cell(textwrap.dedent(s).strip()))

    md('''
    # ทุเรียน 4 ภูมิภาค: ดิน พื้นที่ปลูก อากาศย้อนหลัง และผลผลิต

    ## สรุปสำหรับอาจารย์
    ขยายจากจันทบุรีไปชุมพร ศรีสะเกษ และอุตรดิตถ์ เป็น **4 จังหวัดตัวอย่าง ไม่ใช่ตัวแทนเชิงสถิติของทั้งประเทศ**
    ใช้แผนที่กรมพัฒนาที่ดินจริงซ้อนกัน แล้วดึงอากาศ NASA POWER ณ จุดที่อยู่ภายในพื้นที่รหัสทุเรียน A403
    อากาศย้อนหลัง 2549–2568 เชื่อมผลผลิต สศก. ระดับจังหวัด–ปี

    **ข้อควรระวังหลัก:** ปีแผนที่แต่ละจังหวัดไม่ตรงกัน และสวนผสมที่มีทุเรียนไม่ใช่ทุเรียนล้วน
    จึงไม่ใช้แผนที่นี้อ้างจำนวนไร่ทุเรียนในอดีตทุกปี หรือสรุปผลผลิตรายชุดดิน
    สรุปตัวเลขจากผลที่คำนวณจริงอยู่ในกรอบถัดไป
    ''')
    code('''
    from pathlib import Path
    import json, sys
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, ticker
    from IPython.display import display, Markdown

    root = next(p for p in [Path.cwd(), *Path.cwd().parents]
                if (p/'research_data/regional_orchards/overlay_summaries.json').exists())
    folder = root/'research_data/regional_orchards'
    summaries = json.loads((folder/'overlay_summaries.json').read_text(encoding='utf-8'))
    def read(name): return pd.read_csv(folder/name, dtype={'province_code':str})
    soil = read('soil_series_comparison.csv')
    points = read('orchard_weather_samples.csv')
    monthly = read('orchard_weather_monthly.csv')
    panel = read('regional_province_year_panel.csv')
    comparison = read('reference_point_comparison_2021_2025.csv')
    signatures = read('sample_response_signatures.csv')
    readiness = read('model_readiness.csv')
    order = ['22','86','33','53']
    names = {s['province_code']:s['province_name'] for s in summaries}
    years = {s['province_code']:s['landuse_year_be'] for s in summaries}
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.float_format', lambda x:f'{x:,.2f}')
    thai_font = Path('C:/Windows/Fonts/tahoma.ttf')
    if thai_font.exists():
        font_manager.fontManager.addfont(str(thai_font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(thai_font)).get_name()
    plt.rcParams.update({'figure.facecolor':'white','axes.facecolor':'white','font.size':11,
                         'axes.spines.top':False,'axes.spines.right':False,
                         'text.color':'#171717','axes.labelcolor':'#171717','axes.edgecolor':'#999999',
                         'savefig.facecolor':'white','axes.unicode_minus':False})
    def save(fig, name):
        fig.savefig(folder/(name+'.png'), dpi=200)
        fig.savefig(folder/(name+'.svg'))
    ''')
    code('''
    # Write the takeaway from verified outputs, not from an assumed result.
    utt = next(s for s in summaries if s['province_code']=='53')['summary']
    mixed_share = utt['mixed']['rai']/(utt['pure']['rai']+utt['mixed']['rai'])*100
    display(Markdown(f"""
    - เชื่อมข้อมูลอากาศ **{panel.year_ce.min()+543}–{panel.year_ce.max()+543}** ได้ **{len(panel)} จังหวัด–ปี**;
      ผลผลิตมีระเบียน {panel.production_tonnes.notna().sum()}/{len(panel)} แถว
    - จุดดึงอากาศ **{len(points)} จุดแบ่งชั้นพื้นที่** ไม่ใช่ {len(points)} สถานีตรวจอากาศอิสระ
    - อุตรดิตถ์: **{mixed_share:.1f}%** ของพื้นที่รหัสที่มี A403 เป็นรหัสปลูกผสม
      (คิดจากขนาด polygon ไม่ใช่สัดส่วนต้นทุเรียน); โปรไฟล์อากาศชุดนี้ใช้เฉพาะ A403 ตรงตัว จึงมีข้อจำกัดการเป็นตัวแทน
    - **{(~readiness.match_possible_with_fraction_0_to_1).sum()}/4 จังหวัด**: พื้นที่ LDD กับ สศก. ปีเดียวกัน
      ยังอธิบายให้ตรงกันไม่ได้ด้วยการแบ่งสัดส่วนสวนผสมเพียงอย่างเดียว — ดูหัวข้อ 2.1
    - มี baseline ผลผลิตต่อไร่แบบใช้ปีก่อน/ค่าเฉลี่ย 5 ปีก่อนสำหรับเปรียบเทียบต่อไป
      แต่ **ยังไม่มีผลประเมินโมเดลที่ใช้อากาศ หรือค่าผลกระทบจากอุณหภูมิ ±1°C**
    """))
    ''')
    md('''
    ## 1. หน่วยข้อมูลและหลักฐานที่มา

    | ชุดข้อมูล | แหล่งจริง | หน่วย / ช่วงเวลา |
    |---|---|---|
    | ชุดดิน | [LDD ดาวน์โหลดดิน](https://tswc.ldd.go.th/DownloadGIS/Index_Soil.html) | polygon ดิน; readme ทั้ง 4 จังหวัดระบุปีผลิต 2561 มาตราส่วน 1:25,000 |
    | พื้นที่ทุเรียน | [LDD การใช้ที่ดิน](https://tswc.ldd.go.th/DownloadGIS/Index_Lu.html) | A403 ตรงตัวแยกจาก A403/รหัสอื่น; จันทบุรี 2568 ชุมพร 2564 ศรีสะเกษ 2565 อุตรดิตถ์ 2563 |
    | อากาศ | [NASA POWER monthly API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/) | 4 ตัวแปร รายเดือน 2006–2025; ข้อมูลกริด ไม่ใช่การวัดในสวน |
    | ผลผลิต | [สำนักงานเศรษฐกิจการเกษตร](https://catalog.oae.go.th/dataset/durian_product) | จังหวัด–ปี; ตัน, ไร่, กก./ไร่; ไม่แยกพันธุ์หมอนทอง |

    SHA-256, URL และเวลาดาวน์โหลด UTC ของแต่ละไฟล์อยู่ใน `.source.json` คู่ไฟล์ raw;
    `overlay_summaries.json` มี manifest SHP/DBF/PRJ/readme ที่ใช้คำนวณจริง
    อ่านรายละเอียดใน `SOURCE_TH.md` และ `DATA_DICTIONARY_TH.md` โฟลเดอร์เดียวกับผลวิเคราะห์

    ### วิธีคำนวณที่เรียนรู้จาก notebook นี้
    1. ตรวจรหัสจังหวัด/ปี ไม่ join ด้วยชื่อหรือเลขแถวอย่างเดียว
    2. ซ้อนทับ polygon ในระบบพิกัดหน่วยเมตร; **ศรีสะเกษดิน UTM47 แต่การใช้ที่ดิน UTM48 จึงต้องแปลงก่อน**
    3. แบ่งพื้นที่ A403 ด้วยกรอบ 0.25° แล้วเลือกจุดภายในแต่ละส่วน ถ่วงด้วยพื้นที่ A403 ของส่วนนั้น
    4. กรอบ 0.25° เป็นวิธีสุ่มเชิงพื้นที่ของเรา **ไม่ใช่ความละเอียดกริด NASA** และไม่ใช่การอินทิเกรตพื้นที่กริด NASA แบบตรงตัว
    5. ฝน API เป็น mm/day เฉลี่ยรายเดือน: คูณวันของเดือนก่อนรวมปี; ตัวแปรอื่นถ่วงจำนวนวัน
    6. ขาดจุด/เดือนจะเป็น missing พร้อม coverage ไม่ปรับน้ำหนักกลบข้อมูลที่ขาด

    [NASA methodology](https://power.larc.nasa.gov/docs/methodology/meteorology/): อุตุนิยมวิทยา MERRA-2
    โดยทั่วไป 0.5° × 0.625°; รังสีอาทิตย์ SYN1DEG มีความละเอียดต่างกัน
    เวลา LST ตาม API ไม่ใช่เวลาสถานีสวน; ไม่ใช่ yr.no และไม่ใช่ NDVI
    ''')
    code('''
    assert panel.shape[0] == 4*20
    assert not panel.duplicated(['province_code','year_ce']).any()
    assert len(monthly) == 4*20*12
    assert set(monthly.month) == set(range(1,13))
    assert panel.complete_weather_months.eq(12).all()
    assert points.groupby('province_code').weight.sum().sub(1).abs().lt(1e-7).all()
    assert points.inside_A403.all()
    assert panel.production_tonnes.notna().all()
    assert monthly.filter(like='_area_coverage').sub(1).abs().lt(1e-7).all().all()
    coverage = panel.groupby('province_code').agg(
        first_year=('year_ce','min'), last_year=('year_ce','max'),
        weather_years=('temperature_c','count'), production_years=('production_tonnes','count'))
    coverage['province'] = coverage.index.map(names)
    coverage['points'] = points.groupby('province_code').size()
    coverage['unique_weather_profiles'] = signatures.groupby('province_code').response_profile_sha256.nunique()
    display(coverage.loc[order])
    print('จุดบางจุดได้ค่ากริดเดียวกัน: unique profile ไม่เท่ากับจำนวนสถานีอิสระ และแต่ละตัวแปรอาจซ้ำมากกว่านี้')
    ''')
    md('''
    ## 2. พื้นที่ปลูกกับชุดดิน: เปรียบเทียบอะไรได้จริง
    ตารางนี้เป็น **พื้นที่ polygon ตามแผนที่คนละปี** ไม่ใช่เนื้อที่ให้ผล สศก. และไม่ใช่การจัดอันดับความเหมาะสม
    “mixed” คือพื้นที่ทั้ง polygon ของรหัสปลูกผสม ไม่ทราบว่าทุเรียนกินพื้นที่ในนั้นเท่าไร
    หน่วย SC = พื้นที่ลาดชันเชิงซ้อน; W = พื้นที่น้ำ ไม่ใช่ชื่อชุดดินเฉพาะ
    ''')
    code('''
    area_rows = []
    for s in summaries:
        pure, mixed = s['summary']['pure'], s['summary']['mixed']
        area_rows.append({'province_code':s['province_code'],'จังหวัด':s['province_name'],
            'ปีแผนที่ใช้ที่ดิน':s['landuse_year_be'],'A403 ตรงตัว (ไร่)':pure['rai'],
            'รหัสผสมทั้ง polygon (ไร่)':mixed['rai'],'ซ้อนดินได้ (%)':pure['covered_rai']/pure['rai']*100,
            'ซ้อนดินไม่ได้ (ไร่)':max(0,pure['uncovered_rai']),
            'สัดส่วนรหัสผสม (%)':mixed['rai']/(pure['rai']+mixed['rai'])*100})
    areas = pd.DataFrame(area_rows).set_index('province_code').loc[order]
    display(areas)
    areas.to_csv(folder/'landuse_class_summary.csv',encoding='utf-8-sig')
    top = soil.sort_values('pure_rai',ascending=False).groupby('province_code',sort=False).head(5)
    display(top[['province_name','landuse_year_be','soil_code','soil_name','pure_rai','share_of_A403_pct']])
    top.to_csv(folder/'top_soil_units.csv',index=False,encoding='utf-8-sig')
    fig,axes = plt.subplots(2,2,figsize=(12,8.0),layout='constrained')
    for ax,code_ in zip(axes.flat,order):
        g = soil.loc[soil.province_code.eq(code_)].nlargest(5,'pure_rai').sort_values('pure_rai')
        labels = g.soil_name.str.replace('ชุดดิน','',regex=False)+' ('+g.soil_code+')'
        ax.barh(labels,g.share_of_A403_pct,color='#1f6f5f',height=.6)
        ax.set_xlim(0,100)
        ax.set_title(f'{names[code_]} · การใช้ที่ดิน {years[code_]}',loc='left',pad=10)
        ax.set_xlabel('สัดส่วนพื้นที่ A403 ตรงตัว (%)')
        for y,v in enumerate(g.share_of_A403_pct):
            ax.text(v+1,y,f'{v:.1f}%',va='center',fontsize=10)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y',length=0)
    fig.suptitle('หน่วยดิน 5 อันดับแรกใต้พื้นที่ A403 ของแต่ละจังหวัด',fontsize=15,x=.02,ha='left')
    fig.supxlabel('แหล่ง: LDD · ดินปีผลิต 2561 × การใช้ที่ดินต่างปี · ไม่ใช่อันดับดินที่ให้ผลผลิตดีที่สุด',fontsize=10,color='#5e6462')
    save(fig,'soil_units_four_provinces')
    plt.show()
    ''')
    md('''
    ### 2.1 ตรวจพื้นที่คนละแหล่งในปีเดียวกัน ก่อนนำไปเป็นโมเดล
    เทียบ **เนื้อที่ยืนต้น** สศก. ไม่ใช่เนื้อที่ให้ผล เพื่อไม่เอาพื้นที่ที่ยังไม่ให้ผลออกจากด้านเดียว
    LDD คือขนาด polygon ตามการจำแนกการใช้ที่ดิน; สศก. คือสถิติเกษตร จึงยังไม่ถือว่านิยาม/การสำรวจเหมือนกัน
    ปีในชื่อไฟล์ LDD ไม่ได้ยืนยันวันสำรวจตรงกับรอบสถิติ สศก. ทุกแปลง

    ตารางนี้เป็นการหาความต่าง ไม่ใช่ตัดสินว่าแหล่งใดผิด และ **อัตราส่วนเกิน 100% ไม่ใช่ความแม่นยำหรือ coverage จริง**

    ทดลองสมการ `เนื้อที่ยืนต้น สศก. = พื้นที่ A403 ตรงตัว + f × พื้นที่ polygon ผสม`
    โดยสมมติชั่วคราวว่า f อยู่ระหว่าง 0–1 แล้วดูว่าสมการเป็นไปได้หรือไม่
    ถ้า f ติดลบหรือเกิน 1 แปลว่าแบ่งสัดส่วนสวนผสมอย่างเดียวไม่พออธิบายความต่าง
    **f เป็นเครื่องมือตรวจทางคณิตศาสตร์ ไม่ใช่สัดส่วนทุเรียนที่ประมาณจากข้อมูลจริง**
    ''')
    code('''
    a = readiness.set_index('province_code').loc[order]
    columns={'province_name':'จังหวัด','landuse_year_be':'ปี พ.ศ.',
             'ldd_A403_rai':'LDD ทุเรียนตรงตัว (ไร่)',
             'ldd_all_A403_codes_rai':'LDD รวม polygon ผสม (ไร่)',
             'oae_planted_rai':'สศก. เนื้อที่ยืนต้น (ไร่)',
             'oae_bearing_rai':'สศก. เนื้อที่ให้ผล (ไร่)'}
    display(a[list(columns)].rename(columns=columns).reset_index(drop=True))
    # Diagnostic identity only: OAE = pure + f * mixed.
    # f is NOT a fitted/calibrated durian share; actual within-polygon fraction is unknown.
    diagnostics = a[['province_name','algebraic_mixed_fraction_to_match','match_possible_with_fraction_0_to_1',
                     'geometry_minus_source_area_rai']].copy()
    diagnostics['geometry_difference_pct'] = a.geometry_minus_source_area_rai/a.source_attribute_pure_rai*100
    shown = diagnostics[['province_name','algebraic_mixed_fraction_to_match',
                         'match_possible_with_fraction_0_to_1','geometry_difference_pct']].copy()
    shown['match_possible_with_fraction_0_to_1']=shown.match_possible_with_fraction_0_to_1.map({True:'ใช่',False:'ไม่ใช่'})
    shown['geometry_difference_pct']=shown.geometry_difference_pct.where(shown.geometry_difference_pct.abs().gt(1e-6),0)
    display(shown.rename(columns={'province_name':'จังหวัด',
        'algebraic_mixed_fraction_to_match':'f เชิงคณิตศาสตร์',
        'match_possible_with_fraction_0_to_1':'f อยู่ในช่วง 0–1',
        'geometry_difference_pct':'พื้นที่คำนวณต่างจาก attribute (%)'}).reset_index(drop=True))
    cpn=a.loc['86'];cti=a.loc['22'];ssk=a.loc['33']
    display(Markdown(f"""
    **สิ่งที่พบจริง**
    - จันทบุรี: A403 ตรงตัวมากกว่าเนื้อที่ยืนต้น สศก. **{cti.pure_to_oae_planted_pct-100:.1f}%**;
      ศรีสะเกษมากกว่า **{ssk.pure_to_oae_planted_pct-100:.1f}%** แม้ยังไม่รวมสวนผสม
    - ชุมพร: แม้นับ polygon ผสมทั้งหมดเป็นทุเรียน จะได้ **{cpn.all_codes_to_oae_planted_pct:.1f}%**
      ของเนื้อที่ยืนต้น สศก. เท่านั้น จึงแก้ความต่างด้วยสัดส่วนสวนผสมอย่างเดียวไม่ได้
    - อุตรดิตถ์: f อยู่ในช่วง 0–1 ได้ในทางคณิตศาสตร์ แต่ **ไม่ใช่หลักฐานว่า f นี้คือสัดส่วนทุเรียนจริง**
    - คำอธิบาย A403 ในต้นฉบับทั้งสี่จังหวัดตรงกับ “ทุเรียน”; พื้นที่ geometry ต่างจาก attribute ต้นทาง
      ไม่เกิน **{diagnostics.geometry_difference_pct.abs().max():.3f}%** จึงยังไม่พบหลักฐานว่าแปลงหน่วยพื้นที่ผิดจนทำให้เกิดช่องว่างขนาดนี้

    **ผลต่อการใช้งาน:** ใช้สองแหล่งทำคำบรรยายเปรียบเทียบได้ แต่ห้าม scale แผนที่ให้ตรง สศก.
    หรือแจกผลผลิตจังหวัดลง polygon เพื่อสร้าง label ปลอม สาเหตุของความต่างยังต้องตรวจนิยาม รอบสำรวจ และวิธีจำแนกกับแหล่งข้อมูล
    """))
    ''')
    md('''
    ### 2.2 “มีหน่วยดิน” ไม่เท่ากับ “รู้ชุดดินละเอียด”
    จัดกลุ่มเพื่อสอบทานจากรหัส/คำอธิบายต้นฉบับ ไม่ใช่คอลัมน์ที่ LDD ประกาศ และยังไม่ใช่การรับรองชื่อชุดดินทุกระเบียน
    กลุ่มชื่อชุดดินเดี่ยวใช้คำว่า candidate; หน่วยเชิงซ้อน/สัมพันธ์เก็บเป็นกลุ่ม ไม่แบ่งสัดส่วนชุดดินเอง
    หน่วยภูมิประเทศ/อื่น ๆ ได้แก่ SC, ES, RL, RC, AC; แยก W พื้นที่น้ำออก
    ''')
    code('''
    soil_columns={'province_name':'จังหวัด','named_single_unit_candidate_pct':'ชื่อชุดดินเดี่ยว candidate (%)',
                  'complex_or_association_pct':'หน่วยเชิงซ้อน/สัมพันธ์ (%)','terrain_misc_unit_pct':'ภูมิประเทศ/หน่วยอื่น (%)',
                  'water_pct':'พื้นที่น้ำ (%)','soil_unmapped_pct':'ซ้อนดินไม่ได้ (%)'}
    display(a[list(soil_columns)].rename(columns=soil_columns).reset_index(drop=True))
    total_before=int(a.historical_years_before_landuse_snapshot.sum())
    display(Markdown(f"""
    **ข้อจำกัดก่อนพยากรณ์:** **{total_before}/{int(a.total_weather_years.sum())} จังหวัด–ปี**
    มีปีอากาศก่อนปีแผนที่ใช้ที่ดินที่นำมากำหนดพื้นที่อ้างอิง
    ส่วนที่เหลือก็ยังไม่ถือว่าผ่านการตรวจข้อมูลพร้อมใช้ ณ วันพยากรณ์ เพราะยังไม่รู้วันเผยแพร่/ข้อมูลย้อนหลังแต่ละฉบับ
    ในอุตรดิตถ์ A403 ตรงตัวมีหน่วยที่ดูเป็นชื่อชุดดินเดี่ยวเพียง **{a.loc['53','named_single_unit_candidate_pct']:.1f}%**
    จึงไม่ควรใช้ชื่อชุดดินหนึ่งชื่อแทนพื้นที่ปลูกทั้งจังหวัด
    """))
    ''')
    md('''
    ## 3. ตำแหน่งดึงข้อมูลเปลี่ยน ผลอากาศเปลี่ยนเท่าไร
    เปรียบเทียบปี 2568: วิธีเดิมใช้จุดอ้างอิงหนึ่งจุดภายในจังหวัด;
    วิธีใหม่ประมาณค่าเฉลี่ยด้วยหลายจุดภายใน A403 และถ่วงพื้นที่
    **ความต่างไม่ใช่ค่าความคลาดเคลื่อนเทียบสถานีจริง และไม่ได้พิสูจน์ว่าวิธีใหม่แม่นกว่า**
    แต่เป็นหลักฐานว่าขอบเขตเชิงพื้นที่ที่เลือกมีผลต่อข้อมูลเข้าของโมเดล
    อุตรดิตถ์ใช้เพียง A403 ตรงตัวส่วนเล็ก ไม่รวมสวนผสมส่วนใหญ่
    ''')
    code('''
    selected = comparison.loc[comparison.year_ce.eq(2025)].set_index('province_code').loc[order]
    cols = ['province_name','temperature_c_province_point','temperature_c_orchard_weighted',
            'temperature_c_difference','rain_mm_year_province_point','rain_mm_year_orchard_weighted','rain_mm_year_difference']
    display(selected[cols])
    fig,axes = plt.subplots(1,2,figsize=(12,5.2),layout='constrained')
    for ax,key,label,decimals in [(axes[0],'temperature_c','อุณหภูมิเฉลี่ยปี (°C)',2),
                                  (axes[1],'rain_mm_year','ฝนสะสมประมาณ (มม./ปี)',0)]:
        a = selected[key+'_province_point'].to_numpy()
        b = selected[key+'_orchard_weighted'].to_numpy()
        ypos = np.arange(4)
        ax.hlines(ypos,np.minimum(a,b),np.maximum(a,b),color='#a5aaa7',linewidth=1.5)
        ax.scatter(a,ypos,marker='o',s=45,color='#6f7672',label='จุดอ้างอิงจังหวัด',zorder=3)
        ax.scatter(b,ypos,marker='D',s=40,color='#1f6f5f',label='จุด A403 ถ่วงพื้นที่',zorder=3)
        for i,(v,w) in enumerate(zip(a,b)):
            ax.annotate(f'{v:,.{decimals}f}',(v,i),xytext=(0,9),textcoords='offset points',ha='center',fontsize=10,color='#505653')
            ax.annotate(f'{w:,.{decimals}f}',(w,i),xytext=(0,-17),textcoords='offset points',ha='center',fontsize=10,color='#1f6f5f')
        ax.set_yticks(ypos,[names[c] for c in order]);ax.invert_yaxis()
        ax.set_ylim(3.6,-.6);ax.margins(x=.20)
        ax.set_xlabel(label);ax.grid(axis='x',color='#e5e7e5',linewidth=.6)
        ax.legend(loc='lower left',bbox_to_anchor=(0,1.01),frameon=False,fontsize=10)
    fig.suptitle('เปลี่ยนจุดอ้างอิงอากาศ: ค่าเดิมและค่าใหม่ · พ.ศ. 2568',fontsize=15,x=.02,ha='left')
    fig.supxlabel('แหล่ง: NASA POWER · จุดกลม = วิธีเดิม / ข้าวหลามตัด = A403 ถ่วงพื้นที่ · ไม่ใช่การตรวจสอบกับสถานีจริง',fontsize=10,color='#5e6462')
    save(fig,'weather_spatial_support_comparison')
    plt.show()
    ''')
    md('''
    ## 4. อากาศย้อนหลัง 20 ปีบนพื้นที่อ้างอิงคงที่
    เป็นการถามว่า **บริเวณที่แผนที่ฉบับนี้ระบุว่าปลูกทุเรียน เคยมีอากาศอย่างไร**
    ไม่ได้ยืนยันว่าในปี 2549 มีสวนอยู่ตรงนั้นแล้ว จึงมีความเสี่ยงจากการใช้ข้อมูลพื้นที่อนาคต
    (look-ahead / survivorship bias) หากนำไปอ้างประสิทธิภาพการพยากรณ์ย้อนหลัง
    ตารางรายเดือนเก็บความชื้นและรังสีอาทิตย์ไว้ครบ แม้กราฟเลือกแสดงอุณหภูมิและฝนเพื่อให้อ่านง่าย
    ''')
    code('''
    styles = [('#1f6f5f','-'),('#5a6060','--'),('#929793',':'),('#303534','-.')]
    fig,axes = plt.subplots(2,1,figsize=(11.5,8.0),layout='constrained',sharex=True)
    for ax,key,label in [(axes[0],'temperature_c','อุณหภูมิเฉลี่ย (°C)'),(axes[1],'rain_mm_year','ฝนสะสมประมาณ (มม./ปี)')]:
        for code_,(color,style) in zip(order,styles):
            g=panel.loc[panel.province_code.eq(code_)].sort_values('year_ce')
            ax.plot(g.year_ce+543,g[key],label=names[code_],color=color,linestyle=style,linewidth=1.8)
        ax.set_ylabel(label)
        ax.grid(axis='y',color='#e5e7e5',linewidth=.6)
    axes[0].legend(ncol=4,frameon=False,loc='lower left',bbox_to_anchor=(0,1.0))
    axes[1].set_ylim(bottom=0)
    axes[1].set_xticks(range(2549,2569,2));axes[1].set_xlabel('ปี พ.ศ.')
    fig.suptitle('โปรไฟล์อากาศย้อนหลัง · ประมาณด้วยจุดใน A403 ถ่วงพื้นที่',fontsize=15,x=.02,ha='left')
    fig.supxlabel('แหล่ง: NASA POWER · ยึดพื้นที่แผนที่คนละปีคงที่ตลอด 20 ปี · ไม่ใช่ค่าที่วัดจากสถานีสวน',fontsize=10,color='#5e6462')
    save(fig,'retrospective_weather_profiles')
    plt.show()
    latest = panel.loc[panel.year_ce.eq(2025),['province_name','landuse_year_be','temperature_c','humidity_pct',
                                            'rain_mm_year','solar_mj_m2_day','production_tonnes','bearing_rai','yield_kg_per_rai_source']]
    display(latest)
    ''')
    md('''
    ## 5. เริ่มเรียนโมเดลด้วย baseline ที่ตรวจสอบได้
    เป้าหมายที่มี label จริงตอนนี้คือ **ผลผลิตต่อไร่ของจังหวัดในปีถัดไป** ไม่ใช่สุขภาพต้นหรือปริมาณน้ำที่ควรให้
    ทดสอบสองกฎพื้นฐานโดยใช้ข้อมูลก่อนปีเป้าหมายเท่านั้น:
    - `previous_year`: ผลผลิตต่อไร่ปีหน้าเท่าปีล่าสุด
    - `trailing_5yr_mean`: ค่าเฉลี่ยผลผลิตต่อไร่ 5 ปีก่อนหน้า

    ใช้ช่วงทดสอบเดียวกัน 2554–2568 ทั้งสองกฎ (4 จังหวัด × 15 ปี)
    MAE = ความผิดพลาดสัมบูรณ์เฉลี่ย, RMSE ให้น้ำหนักความผิดพลาดใหญ่เพิ่มขึ้น; หน่วย กก./ไร่
    ไม่มีการใช้อากาศ/ชุดดินใน baseline นี้ จึงยังไม่ใช่ผลทดสอบโมเดลอากาศ
    เป็น retrospective backtest บนสถิติฉบับที่ดาวน์โหลดปัจจุบัน ไม่ได้มี historical data vintages
    จึงไม่อ้างว่าเป็นผล forecast ที่ทำได้จริง ณ วันนั้น
    ''')
    code('''
    backtest = panel[['province_code','province_name','year_ce','yield_kg_per_rai_source']].sort_values(['province_code','year_ce']).copy()
    target='yield_kg_per_rai_source'
    # Shift BEFORE rolling: never include the outcome of the year being predicted.
    backtest['previous_year']=backtest.groupby('province_code')[target].shift(1)
    backtest['trailing_5yr_mean']=backtest.groupby('province_code')[target].transform(lambda s:s.shift(1).rolling(5,min_periods=5).mean())
    backtest=backtest.loc[backtest.year_ce.between(2011,2025)].copy()
    assert len(backtest)==60
    assert backtest[[target,'previous_year','trailing_5yr_mean']].notna().all().all()
    rows=[]
    for model in ['previous_year','trailing_5yr_mean']:
        for province,g in [('รวม 4 จังหวัด',backtest),*backtest.groupby('province_name')]:
            error=g[model]-g[target]
            rows.append({'baseline':model,'จังหวัด':province,'n':len(g),
                         'MAE_kg_rai':error.abs().mean(),'RMSE_kg_rai':np.sqrt((error**2).mean())})
    baseline=pd.DataFrame(rows)
    display(baseline)
    backtest.to_csv(folder/'baseline_predictions.csv',index=False,encoding='utf-8-sig')
    baseline.to_csv(folder/'baseline_metrics.csv',index=False,encoding='utf-8-sig')
    pooled=baseline.loc[baseline['จังหวัด'].eq('รวม 4 จังหวัด')].set_index('baseline')
    display(Markdown(f"""เกณฑ์ตั้งต้น: ใช้ปีก่อนมี MAE **{pooled.loc['previous_year','MAE_kg_rai']:.1f} กก./ไร่**;
    ค่าเฉลี่ย 5 ปีก่อนมี MAE **{pooled.loc['trailing_5yr_mean','MAE_kg_rai']:.1f} กก./ไร่**
    ตัวเลขนี้ไม่ใช่ “ความแม่นยำเป็นเปอร์เซ็นต์” และยังไม่อนุญาตให้เลือกโมเดลจากผลทดสอบซ้ำ ๆ แล้วอ้างผลทดสอบอิสระ"""))
    ''')
    md('''
    ## 6. สิ่งที่สรุปได้ และสิ่งที่ต้องเก็บเพิ่ม

    **สรุปได้:** พื้นที่ในแผนที่มีหน่วยดินอะไร, อากาศย้อนหลังของพื้นที่อ้างอิงเป็นอย่างไร,
    จุดอ้างอิงมีผลต่อค่าข้อมูลเข้าเพียงใด, และ baseline ผลผลิตพลาดเฉลี่ยเท่าไร

    **ยังสรุปไม่ได้:** ดินไหนทำให้ผลผลิตสูงกว่า, อุณหภูมิเพิ่ม 1°C ทำให้ผลผลิตเปลี่ยนกี่เปอร์เซ็นต์,
    ต้นทุเรียนของเราเป็นโรค/ขาดน้ำหรือควรให้น้ำกี่ลิตร

    ลำดับทำต่อให้ตรงโจทย์อาจารย์:
    1. ขอความเห็นเรื่องหน่วยเป้าหมาย “จังหวัด–ปี / ผลผลิตต่อไร่” และช่วงออกดอก–ติดผลแต่ละภูมิภาค
    2. ตรวจความต่างพื้นที่ LDD–สศก. ในหัวข้อ 2.1 กับนิยาม/รอบสำรวจของแหล่งก่อน; เพิ่มจังหวัดและพื้นที่ปลูกที่เทียบปีได้
       ทดสอบความไวเมื่อรวมรหัสผสมโดยไม่ถือทั้งหมดเป็นพื้นที่ทุเรียน
    3. เพิ่มฝนช่วงวิกฤต/วันแห้งต่อเนื่อง/อุณหภูมิสุดขั้วจากข้อมูลรายวัน ไม่สร้างขึ้นจากค่าเฉลี่ยรายเดือน
    4. ตรวจเทียบสถานีสวนกับแหล่งภายนอกในช่วงที่ข้อมูลสด ใช้ outdoor_temp/outdoor_humidity;
       ช่วง gateway ค้างไม่นำ weather features มาเป็นค่าจริง และไม่ลบ raw
    5. สร้างโมเดลอย่างง่ายและ walk-forward validation โดยยึดเวลาที่ข้อมูลพร้อมจริง
       กันปีสุดท้าย/จังหวัดสำหรับประเมินแยก และเทียบ baseline ข้างบน
    6. หากจำลองอุณหภูมิ ±1°C ต้องเขียนว่า scenario ภายใต้สมมติฐาน ไม่ใช่ causal effect
       เพราะปัจจัยพันธุ์ อายุสวน การจัดการ ฤดูผลิต และพื้นที่ให้ผลยังเป็นตัวแปรกวน
    7. ก่อนตีพิมพ์ dataset ต้องยืนยันสิทธิ์เผยแพร่ผลดัดแปลง LDD และเงื่อนไขแต่ละแหล่ง
       ขณะนี้เก็บ raw/derived/notebook ที่มีผลข้อมูลไว้ในเครื่อง ไม่ push หรือเผยแพร่

    ### คำถามสั้น ๆ ที่ใช้คุยกับอาจารย์
    “ผมเชื่อม 4 จังหวัดกับอากาศย้อนหลัง 20 ปีได้แล้ว แต่พื้นที่ทุเรียนในแผนที่ LDD กับเนื้อที่ยืนต้น สศก.
    ปีเดียวกันต่างกันค่อนข้างมากครับ ควรใช้ผลผลิตต่อไร่ระดับจังหวัดเป็นเป้าหมายก่อน
    และใช้แผนที่เป็นเพียงบริบทพื้นที่ พร้อมตรวจนิยาม/รอบสำรวจก่อนใช้อากาศถ่วงพื้นที่ในโมเดลดีไหมครับ
    ส่วนช่วงอากาศที่นำมาวิเคราะห์ควรอิงช่วงออกดอกหรือติดผลของแต่ละภาคอย่างไรครับ”

    ## เปิดใน VS Code โดยไม่ล็อกอิน
    เปิด `notebooks/03_regional_orchards_soil_weather.ipynb` → Select Kernel →
    เลือก `C:/project/.build/national-analysis-venv/Scripts/python.exe` → Run All
    ถ้าต้องการอ่านอย่างเดียว เปิด `research_data/regional_orchards/ANALYSIS_NOTEBOOK.html`
    ลองแก้ปี 2025 ในหัวข้อเปรียบเทียบเป็น 2024 แล้วดูผลต่าง ก่อนเริ่มปรับโมเดล
    ''')
    nb=nbformat.v4.new_notebook(cells=cells,metadata={
        'kernelspec':{'display_name':'Durian national analysis','language':'python','name':'durian-national'},
        'language_info':{'name':'python','version':sys.version.split()[0]}})
    nbformat.validate(nb)
    nbformat.write(nb,NOTEBOOK)
    os.environ['JUPYTER_PATH']=str(ROOT/'.build/national-analysis-venv/share/jupyter')+os.pathsep+os.environ.get('JUPYTER_PATH','')
    NotebookClient(nb,timeout=180,kernel_name='durian-national',resources={'metadata':{'path':str(ROOT)}}).execute()
    nbformat.validate(nb)
    assert all(o.output_type!='error' for c in nb.cells for o in c.get('outputs',[]))
    nbformat.write(nb,NOTEBOOK)
    # Reading export shows findings and figures; editable code stays in .ipynb.
    exporter=HTMLExporter(template_name='lab',exclude_input=True,exclude_input_prompt=True,exclude_output_prompt=True)
    markup,_=exporter.from_notebook_node(nb)
    markup=markup.replace('<title>Notebook</title>','<title>ทุเรียน 4 ภูมิภาค: ดิน อากาศ และผลผลิต</title>')
    (OUT/'ANALYSIS_NOTEBOOK.html').write_text(markup,encoding='utf-8')
    print('Executed:',NOTEBOOK,flush=True)
    print('Readable export:',OUT/'ANALYSIS_NOTEBOOK.html',flush=True)


if __name__=='__main__': main()
