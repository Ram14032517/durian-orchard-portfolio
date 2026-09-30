# ผลตรวจสำเนา portfolio และงานก่อนเผยแพร่

ตรวจ 1 ตุลาคม 2569 เฉพาะสำเนา `durian-orchard-portfolio` ไม่ใช่การรับรอง repo เดิม

## ใช้งานในเครื่องได้

- Python tests 37 รายการ และ JavaScript tests 8 รายการผ่าน
- `SETUP_PORTFOLIO.ps1` รันผ่าน สร้าง environment แยก ไม่แก้ Anaconda หรือ environment เดิม
- รายงาน Python: สุราษฎร์ธานี กรกฎาคม 2025 อ่านข้อมูลและแหล่งอ้างอิงได้
- `00_OPEN_ME.ipynb` ตรวจรูปแบบและรันทุก code cell ผ่านด้วย environment ใหม่ ตรวจกราฟผลรันและตารางผ่าน HTML preview แล้ว เมนู Jupyter ต้องเชื่อม kernel; ยังไม่ได้ทดสอบการเปลี่ยนเมนูใน VS Code ด้วยมือ
- HTTP smoke test เปิด HTML, อากาศสุราษฎร์ธานี, panel, manifest, ZIP เทรน, ชั้นดิน และขอบเขตจังหวัดได้; path ค่าลับและ Git ถูกปิด
- ZIP เทรนเป็นชุดภูมิภาคเท่านั้น มีคำเตือนสิทธิ์ข้อมูล และถูก ignore ไม่ให้อัปโหลดอัตโนมัติ

## ความปลอดภัยและขอบเขตการตรวจ

ไม่มี `.git` เดิม, private headers, snapshot เซนเซอร์สวน หรือไฟล์ Tuya ของสวนในสำเนา ตรวจข้อความเทียบค่าลับที่รู้จักและรูปแบบ token รวมเนื้อหา CSV/JSON/Markdown ภายใน ZIP ไม่พบรายการตามกฎที่ตรวจ

ผลสแกนไม่ใช่หลักประกันว่าปลอดภัยทุกกรณี และไม่ใช่การตรวจสิทธิ์ข้อมูล ภาพที่ฝังและข้อมูลจากบุคคลที่สามต้องพิจารณาแยก Firmware ยังไม่ได้ compile ด้วย Arduino toolchain

## ยังห้ามอัปโหลดทั้งโฟลเดอร์เป็น Public

1. ยืนยันสิทธิ์เผยแพร่ต่อของข้อมูลชุดดิน LDD และขอบเขตจังหวัด GISTDA/DOPA หรือจัดสำเนาเผยแพร่เฉพาะ code ที่ไม่ฝังข้อมูลเหล่านี้ รวมถึง HTML/notebook/ตารางดิน ไม่ใช่ลบแค่ GeoJSON
2. เก็บการระบุที่มาและเงื่อนไข non-commercial ของ สศก. ตาม metadata ที่บันทึกใน `PUBLIC_SHARE_NOTES_TH.md`; อย่าให้ license code ครอบคลุมข้อมูลภายนอกอัตโนมัติ
3. ตรวจไฟล์ staged อีกครั้งก่อน commit และใช้ author/email ที่ผู้ใช้เลือก
4. สร้าง repo portfolio ใหม่แล้ว push เฉพาะสำเนาที่ผ่านสองข้อแรก ไม่ใช้ history ของ repo เดิม

สร้าง repo ใหม่ `Ram14032517/durian-orchard-portfolio` แบบ Private เพื่อเก็บสำเนาวิจัย เริ่ม Git history ใหม่ ไม่ได้เปิด Public, rewrite history เดิม หรือหมุนคีย์ระบบสวน Repo เดิมควรคง Private เพราะคีย์เก่ายังอยู่ใน history; การซ่อนคีย์ปัจจุบันไม่ลบ history

Environment, cache, exports และ ZIP เป็นไฟล์ใช้งานในเครื่อง ไม่ถูก commit โดยอัตโนมัติ เมื่อ clone สามารถใช้ CSV/panel ที่บันทึกไว้ได้ `SETUP_PORTFOLIO.ps1` สร้าง ZIP ในเครื่องจากไฟล์ภูมิภาค หรือรัน `python tools/package_training_bundle.py` โดยไม่แก้ CSV/manifest เดิม

เปิด `README_TH.md` เป็นจุดเริ่ม หรือ `00_OPEN_ME.ipynb` เพื่ออ่านผลวิเคราะห์ ชุดเทรนอยู่ `research_data/five_province_history/training/`
