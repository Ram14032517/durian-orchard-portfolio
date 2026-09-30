"""Create a teaching notebook with real table outputs, without a web interface.

Plain Python cells are executed in order here. This is not a Jupyter-kernel
validation; that remaining check is recorded in the notebook itself.
"""
from pathlib import Path
import contextlib
import io
import json
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'notebooks/01_soil_durian_comparison.ipynb'
cells = []
namespace = {'__name__': '__main__'}
execution_count = 0


def markdown(source):
    cells.append({'cell_type':'markdown','id':f'cell-{len(cells):02}',
                  'metadata':{},'source':textwrap.dedent(source).strip()})


def code(source):
    global execution_count
    source = textwrap.dedent(source).strip()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(source, '<notebook-cell>', 'exec'), namespace)
    execution_count += 1
    outputs = [{'output_type':'stream','name':'stdout','text':buffer.getvalue()}] if buffer.getvalue() else []
    cells.append({'cell_type':'code','id':f'cell-{len(cells):02}','metadata':{},
                  'source':source,'execution_count':execution_count,'outputs':outputs})


markdown('''
# วิเคราะห์เปรียบเทียบชุดดินกับพื้นที่ทุเรียน: จันทบุรี

## สรุปสั้น
ใช้ข้อมูลจริงของกรมพัฒนาที่ดินและผลการซ้อนทับจากสคริปต์ GIS ของโปรเจกต์
เปรียบเทียบ **พื้นที่ที่สำรวจว่าเป็นทุเรียนอยู่บนหน่วยดินใด** ไม่ได้วัดผลผลิตหรือสุขภาพต้น
ดินปีผลิต 2561 กับไฟล์การใช้ที่ดิน 2568 เป็นคนละปี

เอกสารนี้เป็นสมุดวิเคราะห์ ไม่ใช่เว็บแอป รอบนี้แสดงผลเป็นตารางก่อน
เซลล์ Python ด้านล่างรันตามลำดับด้วย Python จริงและเก็บผลไว้แล้ว
แต่ยังไม่ได้ทดสอบด้วย Jupyter kernel และยังไม่มีกราฟใน notebook นี้
''')
markdown('''
## วิธีเปิดและสิ่งที่เรียนรู้

เปิดไฟล์นี้ใน VS Code หรือ Anaconda Jupyter Notebook เลือก Python environment ที่มี pandas แล้วกด Run All
ไม่ต้องล็อกอิน GitHub โค้ดใช้ pathlib, json, hashlib และ pandas
หากตรวจด้วย Jupyter จาก terminal ใช้ `jupyter nbconvert --execute --to notebook --inplace notebooks/01_soil_durian_comparison.ipynb`

บทนี้ฝึกอ่านข้อมูล ตรวจแหล่งที่มา จัดตาราง คำนวณสัดส่วน และเขียนข้อสรุปที่ไม่เกินหลักฐาน
''')
markdown('''
## บริบทและวิธี

- ข้อมูลดิน: [กรมพัฒนาที่ดิน](https://lddcatalog.ldd.go.th/dataset/ldd_11_01)
- การใช้ที่ดิน: [กรมพัฒนาที่ดิน](https://lddcatalog.ldd.go.th/dataset/ldd_21_01)
- ดาวน์โหลดดิน: https://tswc.ldd.go.th/DownloadGIS/web_Soil/SoilSeries/E/sr_cti.rar
- ดาวน์โหลดการใช้ที่ดิน: https://tswc.ldd.go.th/DownloadGIS/web_LU/DataLu/E/Landuse_cti.zip
- วิธีเตรียมข้อมูลเต็ม: `tools/build_soil_evidence.py` ตัดส่วนซ้อนทับใน EPSG:32647 และคิด 1 ไร่ = 1,600 ตารางเมตร
- ตารางนี้อ่าน `research_data/soil_evidence_chanthaburi/analysis.json` ซึ่งเป็น **ผลคำนวณของโปรเจกต์ ไม่ใช่ตารางสรุปที่กรมฯ เผยแพร่โดยตรง**
- ตัวหารของสัดส่วนคือพื้นที่ A403 ทั้งหมด รวมส่วนที่ยังเชื่อมดินไม่ได้ ไม่แอบตัดส่วนที่ขาดทิ้ง

### ข้อตกลงสำคัญ
ใช้ A403 ตรงตัวแยกจากรหัสผสมที่มี A403 ไม่เปลี่ยนพื้นที่ปลูกผสมให้เป็นทุเรียนล้วน
ไม่ตีความพื้นที่มากว่าเหมาะสมกว่า ไม่แจกผลผลิตทั้งจังหวัดลงแต่ละหน่วยดิน
''')
markdown('## ข้อมูล\n### 1. อ่านผลคำนวณที่เก็บไว้')
code('''
from pathlib import Path
import json
import hashlib
import pandas as pd

root = next((p for p in [Path.cwd(), *Path.cwd().parents]
             if (p/'research_data/soil_evidence_chanthaburi/analysis.json').exists()), None)
if root is None:
    raise FileNotFoundError('เปิด notebook จากโฟลเดอร์โปรเจกต์ที่มี analysis.json')
result = json.loads((root/'research_data/soil_evidence_chanthaburi/analysis.json').read_text(encoding='utf-8'))
soil = pd.DataFrame(result['soil_stats'])
soil['ชื่อ'] = soil['names'].map(lambda x: ' / '.join(x))
print('จังหวัด:', result['province'])
print('ดินปีผลิต:', result['soil_production_year_be'], '| การใช้ที่ดินปีไฟล์:', result['landuse_file_year_be'])
print('ดาวน์โหลด:', result['downloaded_date'])
print('หน่วยดินที่ซ้อนพื้นที่ทุเรียน/ปลูกผสมได้:', len(soil))
''')
markdown('### 2. ตรวจว่าต้นฉบับเป็นไฟล์เดิม\nSHA-256 ยืนยันไฟล์ไม่เปลี่ยน ไม่ใช่ยืนยันความถูกต้องของทุกค่าที่สำรวจ')
code('''
raw = root/'research_data/external/ldd_chanthaburi_2026-09-17'
for source in result['archives']:
    actual = hashlib.sha256((raw/source['file']).read_bytes()).hexdigest()
    assert actual == source['sha256'], f"ไฟล์เปลี่ยน: {source['file']}"
    print(source['file'], ': hash ตรงกับรอบวิเคราะห์')
''')
markdown('## ผลเปรียบเทียบ\n### 3. แยกทุเรียนล้วนตามรหัส กับพื้นที่ปลูกผสม')
code('''
summary = pd.DataFrame(result['summary']).T
summary.index = summary.index.map({'pure':'A403 ตรงตัว','mixed':'รหัสปลูกผสมที่มี A403'})
table = summary[['records','rai','covered_rai','uncovered_rai']].rename(columns={
    'records':'รูปแปลง','rai':'พื้นที่_ไร่','covered_rai':'ซ้อนดินได้_ไร่','uncovered_rai':'ไม่ซ้อนดิน_ไร่'})
print(table.round(1).to_string())
print('รูปแปลงไม่เท่ากับจำนวนสวน; ไม่รวมพื้นที่ปลูกผสมเป็นทุเรียนล้วน')
''')
markdown('### 4. หน่วยดินที่มีพื้นที่ A403 มากที่สุด 10 อันดับ\nเปรียบเทียบขนาดพื้นที่เท่านั้น ไม่ใช่อันดับผลผลิตหรือความเหมาะสม')
code('''
denominator = result['summary']['pure']['rai']
soil['สัดส่วน_A403_ทั้งหมด_pct'] = soil['pure_rai'] / denominator * 100
ranked = soil.sort_values('pure_rai', ascending=False)
top = ranked[['code','ชื่อ','pure_rai','สัดส่วน_A403_ทั้งหมด_pct']].head(10)
print(top.rename(columns={'pure_rai':'พื้นที่_A403_ไร่'}).round(2).to_string(index=False))
''')
markdown('### 5. ตรวจชุดดินทุ่งหว้าแยกต่างหาก\nเลือกเพราะผู้ใช้ระบุชื่อดินนี้ ไม่ใช่หลักฐานยืนยันตำแหน่งสวนของผู้ใช้')
code('''
tg = soil.loc[soil['code'].eq('Tg')].iloc[0]
print('ชื่อ:', tg['ชื่อ'], '| รหัส:', tg['code'])
print(f"พื้นที่ A403: {tg['pure_rai']:,.1f} ไร่")
print(f"สัดส่วนพื้นที่ A403 ทั้งจังหวัด: {tg['สัดส่วน_A403_ทั้งหมด_pct']:.2f}%")
print('เนื้อดิน:', ' / '.join(tg['textures']))
print('ระดับกรด–ด่างตามข้อความต้นทาง:', ' / '.join(tg['ph']))
print('ความอุดมสมบูรณ์ตามต้นทาง:', ' / '.join(tg['fertility']))
print('ไม่สร้างค่า pH ตัวเลขจากข้อความ และไม่ใช้แทนผลตรวจดินปัจจุบัน')
''')
markdown('### 6. ตรวจผลรวมและความขัดแย้งก่อนใช้ต่อ')
code('''
for kind in ['pure','mixed']:
    measured = soil[kind+'_rai'].sum()
    expected = result['summary'][kind]['covered_rai']
    assert abs(measured-expected) < 0.00001
    print(kind, ': ผลรวมรายหน่วยดินตรงพื้นที่ซ้อนทับ')
water = soil.loc[soil['code'].eq('W'),'pure_rai'].sum()
unmatched = result['summary']['pure']['uncovered_rai']
print(f'A403 ซ้อนหน่วยพื้นที่น้ำ W: {water:,.1f} ไร่ — ต้องตรวจตำแหน่ง/ปี/การจำแนก')
print(f'A403 ไม่ซ้อนแผนที่ดิน: {unmatched:,.1f} ไร่ — ไม่เติมชื่อดินเอง')
print('รูปทรงที่ซ่อมเพื่อคำนวณ:', result['repair_counts'])
''')
markdown('''
## ข้อสรุปและสิ่งที่ยังตอบไม่ได้

1. แหล่งข้อมูลจริงมีรายละเอียดเพียงพอให้เชื่อมพื้นที่ทุเรียนกับหน่วยดิน ไม่ต้องสมมติว่าทั้งจังหวัดมีดินแบบเดียว
2. ตารางเปรียบเทียบตอบว่าอยู่บนดินใดและเป็นพื้นที่เท่าไร ไม่ได้ตอบว่าดินใดดีที่สุด
3. พบข้อมูลที่ควรสอบทาน: หน่วยน้ำ W ซ้อน A403, บางพื้นที่ไม่จับคู่, รูปทรงต้องซ่อม และข้อความต้นทางบางรายการสะกดผิด
4. ยังต้องตรวจด้วย QGIS อิสระและดูพื้นที่ก่อน/หลังซ่อมรูปทรงก่อนตีพิมพ์
5. งานต่อไปคือเพิ่มกราฟจากตารางนี้ ขยายจังหวัด และเชื่อมอากาศ/ผลผลิตตามจังหวัดกับปี โดยไม่กระจายผลผลิตทั้งจังหวัดไปเป็นผลจริงของแต่ละชุดดิน
6. การศึกษาผลต่อผลผลิตต้องมีข้อมูลผลผลิตที่ระดับพื้นที่สอดคล้องกัน รวมปัจจัยอายุ พันธุ์ การจัดการ และสภาพอากาศ ไม่ใช้พื้นที่ปลูกแทนผลผลิต

**สถานะการตรวจ:** รันเซลล์ Python ธรรมดาตามลำดับและเก็บ stdout จริงแล้ว ยังไม่ตรวจใน Jupyter kernel เพราะ runtime นี้ไม่มี nbformat/nbclient/ipykernel ยังไม่มีกราฟในเล่มนี้

**สิทธิ์:** ต้นทางระบุ NC-ND เก็บวิเคราะห์ในเครื่องก่อน ตรวจสิทธิ์กับเจ้าของก่อนเผยแพร่ไฟล์ดัดแปลง ผล notebook นี้ยังไม่ push
''')
notebook = {'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
            'language_info':{'name':'python','version':'3.12'},
            'execution_note':'Plain Python cells executed sequentially; Jupyter kernel validation pending.'},
            'nbformat':4,'nbformat_minor':5}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding='utf-8')
loaded = json.loads(OUT.read_text(encoding='utf-8'))
assert all(c['cell_type'] in {'markdown','code'} for c in loaded['cells'])
assert len({c['id'] for c in loaded['cells']}) == len(loaded['cells'])
print(f'Created {OUT}; executed {execution_count} plain-Python cells; Jupyter validation pending.')
