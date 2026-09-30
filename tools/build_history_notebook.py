"""Create and execute an audit companion to the interactive history page."""
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from jupyter_client import KernelManager

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_data/five_province_history'
nb=nbformat.v4.new_notebook()
nb.cells=[
nbformat.v4.new_markdown_cell('# ประวัติทุเรียน 5 จังหวัด\n\n## tl;dr\nชุดข้อมูลนี้ใช้ตรวจอากาศย้อนหลังและยอดผลผลิตจังหวัด ยังไม่ใช่หลักฐานเชิงเหตุว่าความร้อนทำให้ผลร่วงรายสวน ดูแผนที่และกราฟโต้ตอบใน HISTORY.html'),
nbformat.v4.new_markdown_cell('## Context & Methods\n### Key Assumptions\nอากาศ NASA POWER ณ จุดอ้างอิง 5 จังหวัด วันแบบ LST; ผลผลิต สศก. ระดับจังหวัด ทุกพันธุ์; ชุดดิน LDD ปี 2561 ไม่ใช่ผลตรวจดินสวนปัจจุบัน ช่วงดอกบานนับย้อนเป็น scenario ต้องยืนยันวันเก็บจริงและพันธุ์ก่อนใช้'),
nbformat.v4.new_code_cell("from pathlib import Path\nimport pandas as pd\nroot=Path.cwd()\nif not (root/'research_data').exists():\n    root=root.parents[1]\np=root/'research_data/five_province_history'\na=pd.read_csv(p/'production_weather_annual.csv',dtype={'province_code':str})\nd=pd.read_csv(p/'weather_daily.csv',dtype={'province_code':str})\ns=pd.read_csv(p/'soil_properties_by_district.csv',dtype={'province_code':str})\nassert not d.duplicated(['province_code','date']).any()\nassert a.province_code.nunique()==5\nprint('อากาศรายวัน:',len(d),'ระเบียน; ผลผลิต:',len(a),'จังหวัด–ปี')"),
nbformat.v4.new_markdown_cell('## Data\nแหล่ง URL และ hash ใน raw/*.source.json; ผลผลิตต้นทาง ../external/oae_2026-09-17; ชื่อและคุณสมบัติหน่วยดินต้นทาง LDD ระบุใน README_TH.md'),
nbformat.v4.new_code_cell("display(pd.read_csv(p/'coverage.csv').query(\"parameter == 'T2M'\"))\ndisplay(s.groupby('province').size().rename('จำนวนชุดคุณสมบัติไม่ซ้ำ').to_frame())"),
nbformat.v4.new_markdown_cell('## Results\nตัวอย่างตรวจปี 2567 เทียบปีก่อน: ผลผลิตรวมกับผลผลิตต่อไร่อาจเปลี่ยนต่างกันเพราะพื้นที่ให้ผลเปลี่ยน ตารางนี้เป็นการเปรียบเทียบ ไม่ใช่ causal estimate'),
nbformat.v4.new_code_cell("display(a[a.year_ce.eq(2024)][['province_name','production_tonnes','production_yoy_pct','yield_kg_per_rai_calculated','yield_yoy_pct','annual_temperature_c','annual_max_c','annual_rain_mm']].round(2))"),
nbformat.v4.new_markdown_cell('## Takeaways\nการระบุผลกระทบรายอำเภอ/ชุดดินยังต้องเพิ่มพิกัดพื้นที่ปลูก วันเกิดเหตุและปริมาณสูญเสีย ณ พื้นที่เดียวกัน กราฟรายเดือนและเครื่องมือนับย้อนอยู่ใน HISTORY.html ไม่ควรใช้ลมเฉลี่ยรายวันแทนลมกระโชกจากพายุ')]
nb.metadata['kernelspec']={'display_name':'Python 3','language':'python','name':'python3'}
km=KernelManager(kernel_name='python3')
km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
NotebookClient(nb,km=km,timeout=120,resources={'metadata':{'path':str(ROOT)}}).execute()
nbformat.validate(nb)
nbformat.write(nb,OUT/'HISTORY_ANALYSIS.ipynb')
body,_=HTMLExporter().from_notebook_node(nb)
(OUT/'HISTORY_ANALYSIS.html').write_text(body,encoding='utf-8')
print('Notebook executed and exported')
