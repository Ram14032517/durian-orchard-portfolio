# แหล่งข้อมูลและวิธีตรวจกลับ

ดาวน์โหลดรอบนี้ 18 กันยายน 2569; ไม่มีการนำพิกัดสวนส่วนตัวไปเรียก API

## ดินและการใช้ที่ดิน: กรมพัฒนาที่ดิน

ค้นไฟล์จาก [ดัชนีดิน](https://tswc.ldd.go.th/DownloadGIS/Index_Soil.html) และ [ดัชนีการใช้ที่ดิน](https://tswc.ldd.go.th/DownloadGIS/Index_Lu.html)
หน้า index สำเนาเก็บพร้อม SHA-256 ใน `../external/ldd_regions_2026-09-18/`

| จังหวัด | soil archive | land-use archive | ปีไฟล์การใช้ที่ดิน |
|---|---|---|---|
| จันทบุรี | [sr_cti.rar](https://tswc.ldd.go.th/DownloadGIS/web_Soil/SoilSeries/E/sr_cti.rar) | [Landuse_cti.zip](https://tswc.ldd.go.th/DownloadGIS/web_LU/DataLu/E/Landuse_cti.zip) | 2568 |
| ชุมพร | [sr_cpn.rar](https://tswc.ldd.go.th/DownloadGIS/web_Soil/SoilSeries/S/sr_cpn.rar) | [Landuse_cpn.zip](https://tswc.ldd.go.th/DownloadGIS/web_LU/DataLu/S/Landuse_cpn.zip) | 2564 |
| ศรีสะเกษ | [sr_ssk.rar](https://tswc.ldd.go.th/DownloadGIS/web_Soil/SoilSeries/NE/sr_ssk.rar) | [Landuse_ssk.zip](https://tswc.ldd.go.th/DownloadGIS/web_LU/DataLu/NE/Landuse_ssk.zip) | 2565 |
| อุตรดิตถ์ | [sr_utt.rar](https://tswc.ldd.go.th/DownloadGIS/web_Soil/SoilSeries/N/sr_utt.rar) | [Landuse_utt.zip](https://tswc.ldd.go.th/DownloadGIS/web_LU/DataLu/N/Landuse_utt.zip) | 2563 |

raw จันทบุรีอยู่ `../external/ldd_chanthaburi_2026-09-17`; จังหวัดที่เพิ่มอยู่ `../external/ldd_regions_2026-09-18`
`00_ReadMe.txt` soil ทั้ง 4 ระบุปีผลิต 2561 และมาตราส่วน 1:25,000 ไม่ใช้วันดาวน์โหลดเป็นปีสำรวจ
DBF ดิน cp874; DBF land use UTF-8; field ชื่อชุดดินต่างกันตามจังหวัด ตรวจ schema ก่อนเลือก
ชื่อ directory ภายใน ZIP บางชุดแสดงผิด encoding หลัง 7-Zip แต่เนื้อหา DBF และชื่อ SHP ที่ใช้ผ่านการตรวจ; เก็บ path จริงไว้ใน manifest

คำนวณ intersection ด้วยรูปทรงเต็ม ไม่ใช้รูปทรงลดจุดสำหรับแผนที่ประเทศ
ดินทุกจังหวัด EPSG:32647; land use ศรีสะเกษ EPSG:32648 ต้อง reproject ดินก่อน; จังหวัดอื่น UTM47
ซ่อม geometry invalid ด้วย make_valid และบันทึกผลต่างพื้นที่; แปลง m² เป็นไร่โดยหาร 1,600
ตรวจ soil/land-use overlap และ pure–mixed overlap <0.1 ไร่ ก่อนใช้ผลรวมเป็นสัดส่วน
กรอบแบ่งชั้น 0.25° เลือก representative point ภายในชิ้น A403 ใหญ่สุดของส่วน แล้วถ่วงด้วยพื้นที่ A403 ทุกชิ้นในส่วนนั้น
วิธีนี้คือ approximate point quadrature ไม่ใช่การซ้อนกริดต้นฉบับ NASA แบบแม่นตรงทุก cell; ยังไม่ได้ทดสอบ sensitivity ของขนาดกรอบ

## NASA POWER

[Monthly API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/), [Meteorology methodology](https://power.larc.nasa.gov/docs/methodology/meteorology/)

endpoint `https://power.larc.nasa.gov/api/temporal/monthly/point`; community AG; start=2006 end=2025; JSON
parameters: T2M C, RH2M %, PRECTOTCORR mm/day, ALLSKY_SFC_SW_DWN MJ/m²/day
เวลา LST, fill_value -999; ใช้เดือน 01–12 ไม่ใช้ 13 ซ้ำ
อุตุนิยมวิทยาเป็น MERRA-2 กริดประมาณ 0.5°×0.625°; solar SYN1DEG มีความละเอียดต่างกัน
จุดหลายจุดอาจใช้กริดเดียวกัน: profile hash ใช้ตรวจค่าซ้ำ ไม่ใช่ตัวนับจำนวนตัวอย่างอิสระทางสถิติ
raw 59 response + `.source.json` อยู่ `../external/power_orchards_2026-09-18`
download concurrency 2; cache ไม่ทับ response เดิม; ถ้าดาวน์โหลดไม่ครบ บันทึก failure และ mark missing ไม่เติมข้อมูล

## ผลผลิต

[OAE durian_product](https://catalog.oae.go.th/dataset/durian_product)
raw `../external/oae_2026-09-17/durian_province.xlsx`
SHA-256 `6a3ae44026b5ef8037a8bb091852281d890168a8d795c9c44d5cde9a48613d4c`
อ่านผ่าน pipeline เดิมเป็น `../thailand_comparison/production_province_year.csv` แล้ว join จังหวัด–ปีแบบ one-to-one
เก็บผลผลิตต่อไร่ตามแหล่งกับผลคำนวณจากตัน/ไร่แยกกัน; baseline ใช้ค่าตามแหล่ง
ปี production ไม่ใช่ Data_date; ผลผลิตรวมไม่แยกพันธุ์หมอนทอง

## สิทธิ์ / การเผยแพร่

metadata ที่ตรวจในชุดงานก่อนระบุ OAE CC Attribution Non-Commercial;
LDD [ดิน](https://lddcatalog.ldd.go.th/dataset/ldd_11_01) และ [การใช้ที่ดิน](https://lddcatalog.ldd.go.th/dataset/ldd_21_01)
ระบุ CC Attribution Non-Commercial No-Derivs โดยไม่ระบุรุ่นชัดเจน
จึงต้องขอคำยืนยันเรื่องการแจกจ่ายผลแปลง/ซ้อนทับก่อนเผยแพร่ dataset ไม่ถือว่า download ได้ = publish derived ได้
ครั้งนี้เก็บ raw, CSV, รูป และ executed notebook ไว้ในเครื่อง; Git เก็บ code และเอกสารวิธีทำเท่านั้น ไม่มี push
