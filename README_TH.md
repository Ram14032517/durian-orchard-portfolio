# สำเนา portfolio — เริ่มตรงนี้

แยกจากโปรเจกต์สวนจริง ไม่มีประวัติ Git เดิม คีย์อุปกรณ์ หรือ snapshot สวนส่วนตัว

สร้าง repo ใหม่แบบ **Private**: https://github.com/Ram14032517/durian-orchard-portfolio — ยังไม่ใช่ฉบับเผยแพร่สาธารณะ ห้ามเปลี่ยนเป็น Public จนตรวจสิทธิ์ข้อมูลดิน/ขอบเขตแผนที่หรือแยกฉบับ code-only

1. เปิดโฟลเดอร์นี้ใน VS Code และติดตั้ง Python 3.11+ ไว้ก่อน
2. เปิด Terminal แล้วรัน `powershell -ExecutionPolicy Bypass -File .\SETUP_PORTFOLIO.ps1` เฉพาะสคริปต์โครงการที่ตรวจแล้ว ไม่เปลี่ยนนโยบาย PowerShell ถาวร
3. ดับเบิลคลิก `00_OPEN_REPORT.cmd` หรือรัน `.\.venv-portfolio\Scripts\python.exe tools\serve_orchard_analysis.py`
4. เปิด http://127.0.0.1:8871/research_data/five_province_history/UNIFIED_MAP.html

หากพอร์ต 8871 แสดงโปรเจกต์เดิมอยู่ launcher จะใช้เซิร์ฟเวอร์เดิม ให้ปิดเซิร์ฟเวอร์เดิมก่อนเมื่อต้องการดูสำเนานี้โดยเฉพาะ ไม่หยุดโปรเซสอื่นให้อัตโนมัติ

ดูรายงานด้วย Python: `.\.venv-portfolio\Scripts\python.exe tools\read_monthly_report.py --province 84 --year 2025 --month 7`

เปิด `00_OPEN_ME.ipynb` อ่านผลที่บันทึกไว้ได้ หาก Run All ให้ติดตั้ง dependencies ตาม README.md และเลือก kernel ให้ตรง

ข้อมูลโมเดล: `research_data/five_province_history/training/` ส่วน CSV อากาศส่งออกใหม่อยู่ใน `research_data/five_province_history/exports/` และถูก ignore

**ยังเป็น draft ในเครื่อง** อ่าน PUBLIC_SHARE_NOTES_TH.md ก่อนอัปโหลด ต้องยืนยันสิทธิ์แจกจ่ายรูปทรงจากหน่วยงานภายนอก หรือเผยแพร่เฉพาะโค้ดพร้อมขั้นตอนดาวน์โหลด
