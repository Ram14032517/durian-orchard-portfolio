# สำเนา portfolio และสิทธิ์ข้อมูล

เตรียม 1 ตุลาคม 2569 ไม่คัดลอก .git หรือ remote เดิม ไม่มีการเปลี่ยนคีย์ อุปกรณ์ หรือระบบรับข้อมูลจริง

## สิ่งที่ไม่คัดลอก

- private headers, .secrets, environments และ backups
- snapshot เซนเซอร์สวนจริง ตารางวิเคราะห์และเอกสารบริบทสวนส่วนตัว
- Tuya shadow/specification และ notebooks วิเคราะห์สวนส่วนตัว
- ประวัติ commit ที่มีคีย์เดิม

## แหล่งข้อมูลและเงื่อนไข

- สศก.: https://catalog.oae.go.th/dataset/durian_product และ https://catalog.oae.go.th/dataset/durian_product_month — ตรวจหน้าเจ้าของวันที่ 1 ต.ค. 2569 ระบุ Creative Commons Attributions Non-Commercial ไม่ระบุเวอร์ชัน ไม่อ้างเป็น MIT หรือการใช้เชิงพาณิชย์โดยไม่มีข้อจำกัด ปีใน metadata หน้าเว็บอาจต่างจาก snapshot ให้ตรวจ manifest ก่อนเปรียบเทียบ
- NASA POWER: API URL เวลาและ SHA256 อยู่ใน raw/*.source.json ค่ากริดไม่ใช่ค่าเซนเซอร์สวน รักษาการอ้างอิงเดิม
- LDD/GISTDA/DOPA: **ยังไม่ยืนยันสิทธิ์แจกจ่ายรูปทรงซ้ำครบทุกไฟล์ สำเนานี้เป็น draft วิจัยแบบ Private ห้ามเผยแพร่ทั้งชุด รวม HTML/Notebook ที่ฝังรูปทรง จนยืนยันเงื่อนไข** ดู SOURCE_TH.md ใน soil_layers และ SOURCES_GEOGRAPHY_TH.md
- vendor/ไลบรารีและเนื้อหาภายนอกยังอยู่ภายใต้สิทธิ์เจ้าของ ไม่มีการกำหนด license ครอบทุกไฟล์แทนเจ้าของ

## ก่อนอัปโหลด

1. ตรวจสแกนและรายการไฟล์อีกครั้ง ไม่ใช้ git add -f กับ ignored files
2. ยืนยันสิทธิ์รูปทรง หรือเลือก code-only พร้อมขั้นตอนดาวน์โหลดตรงจากเจ้าของข้อมูล
3. สร้าง repo ใหม่แยก ห้ามตั้ง origin เป็น repo สวนเดิมแล้ว force push
4. หากต้องการ GitHub noreply email ให้ใช้ค่าที่บัญชียืนยัน ไม่สร้างที่อยู่ขึ้นเอง

สร้าง repo ใหม่ชื่อ `Ram14032517/durian-orchard-portfolio` แบบ Private วันที่ 1 ต.ค. 2569 เพื่อเก็บสำเนาวิจัยแยกจากระบบสวน เริ่มประวัติใหม่จากไฟล์ที่ผ่านการตรวจ ไม่ใช้ประวัติ repo เดิม ตรวจผล commit/push ได้จาก `git status -sb` และหน้า GitHub ยังไม่เปิด Public และไม่ได้เขียนประวัติเดิมใหม่
