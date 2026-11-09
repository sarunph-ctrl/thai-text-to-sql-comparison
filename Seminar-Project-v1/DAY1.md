# Day 1 — Rule-based ที่รันครบเส้นทาง

> **รุ่นปัจจุบันคือ 0.2 มีห้าตารางและคำถามคลังสินค้าเพิ่มแล้ว อ่าน [SCHEMA_GUIDE.md](SCHEMA_GUIDE.md) ก่อน**
> เนื้อหาด้านล่างบันทึกขอบเขตรุ่นแรก ข้อมูลจำนวนตาราง, reset และขอบเขตคำถามปัจจุบันให้ยึดคู่มือใหม่

## เริ่มลองบนเครื่องนี้

เปิด PowerShell ในโฟลเดอร์ `Seminar-Project-v1` แล้วรัน:

```powershell
.\start-demo.ps1
```

เปิด `http://127.0.0.1:8000/docs` → `POST /query` → `Try it out` แล้วส่ง:

```json
{"text": "ยอดขายเดือนกันยายน 2569"}
```

หรือใช้ terminal อีกหน้าต่างโดยไม่ต้องเปิด API:

```powershell
.\.venv\Scripts\python.exe -m scripts.query "ยอดขายเดือนกันยายน 2569"
.\.venv\Scripts\python.exe -m scripts.query "ยอดขายเดือนกันยายน 2569 แยกตามสินค้า"
.\.venv\Scripts\python.exe -m scripts.query "สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569"
```

Python packages ติดตั้งอยู่ใน `.venv` แล้ว ฐานข้อมูลใช้ PostgreSQL ที่ติดตั้งในเครื่อง
และเปิด cluster แยกใน `.local/postgres` ที่ `127.0.0.1:55439` ไม่ใช้ service/ฐานข้อมูลเดิม
credentials สร้างอัตโนมัติใน `.local/connection.json` ซึ่งไม่ถูกเก็บใน Git
ไม่ต้องลง Docker ไม่ต้องใช้ API key และรันคำถามได้แบบ offline
(หน้า Swagger `/docs` ต้องโหลด JavaScript จาก CDN; หากไม่มีอินเทอร์เน็ตใช้ CLI)

## ขอบเขตและนิยาม

- เฉพาะยอดขายรวม / ยอดขายแยกสินค้า / Top-N ตามยอดเงิน
- ระบุชื่อเดือนและปี 4 หลักให้ชัด เช่น กันยายน 2569 หรือ กันยายน 2026
- เลขไทย เช่น ๒๕๖๙ ถูกแปลงเป็นเลขอารบิก
- รายได้ = `SUM(order_items.qty * order_items.unit_price)` เฉพาะสถานะ `paid`
- ไม่นับ `pending` และ `cancelled`
- ใช้ราคาขณะขาย ไม่ใช้ราคาปัจจุบันใน `products.price`
- วันที่เริ่มรวมด้วย วันที่สิ้นสุดไม่รวม เช่น `>= 2026-09-01` และ `< 2026-10-01`
- ถ้ายอดเท่ากันเรียง `products.id ASC` เพื่อให้ Top-N ทำซ้ำได้
- สินค้าที่ไม่มีรายการขายในเดือนนั้นจะไม่ปรากฏในผลแยกสินค้า
- ไม่มีข้อมูลขาย: ยอดรวมเป็น `null` ตาม SQL SUM; รายสินค้าเป็นตารางว่าง
- ไม่รองรับเงื่อนไขชื่อลูกค้า/สินค้า, สต็อก, เปรียบเทียบช่วงเวลา, คำสั่งแก้ไขข้อมูล หรือคำถามต่อเนื่อง
- ข้อความที่เหลือจากการตีความจะถูกปฏิเสธ ไม่ทิ้งเงื่อนไขแล้วตอบยอดกว้างกว่าโจทย์

## คำตอบที่ต้องตรวจได้ด้วยตัวเอง

ข้อมูลจำลองมีสินค้า 5 รายการ ออเดอร์ 10 รายการ และรายการขาย 19 แถว
วันที่เป็นค่าคงที่ในปี 2026 ไม่เปลี่ยนตามวันที่รัน

| สินค้า | ยอดขาย paid ในกันยายน (บาท) |
|---|---:|
| สมุด | 420.00 |
| แฟ้ม | 300.00 |
| ปากกา | 285.00 |
| ดินสอ | 150.00 |
| ยางลบ | 95.00 |
| รวม | **1,250.00** |

ยอดรายออเดอร์ paid เดือนกันยายน: `220 + 200 + 200 + 250 + 260 + 120 = 1250`
มี cancelled 1850, pending 600, สิงหาคม 100 และตุลาคม 50 ปะปนไว้
เพื่อให้ตรวจจับข้อผิดพลาดเรื่องสถานะ/ขอบเขตเดือนได้
ดู SQL อ้างอิงที่เขียนแยกจากตัวสร้างคำสั่งใน `db/demo_reference.sql`

API ส่งเงินเป็น decimal string เช่น `"1250.00"` เพื่อเก็บความแม่นยำ
`elapsed_ms` คือเวลาใน pipeline รวมตัดคำและ query ไม่รวมเปิด connection/HTTP

## อ่านโค้ดตามเส้นทางนี้

1. `app/nlp/normalize.py`: ทำความสะอาดข้อความ แปลงเลขไทย และตัดคำด้วย PyThaiNLP
2. `app/nlp/intents.py` + `config/lexicon.yaml`: จับ metric, dimension, Top-N จากพจนานุกรมและ regex
3. `app/nlp/time_parser.py`: แปลงเดือน/ปี พ.ศ. เป็นช่วงวันที่ ค.ศ.
4. `app/nlp/demo.py`: จำกัดขอบเขต ตรวจข้อความที่ยังไม่ได้ตีความ และประกอบ Intent
5. `app/sql/schema.py`: หาเส้นทาง JOIN ตาม foreign key
6. `app/sql/builder.py`: สร้าง SELECT และ bind parameters
7. `app/nlp/demo.py`: execute ใน transaction อ่านอย่างเดียว มี timeout 3 วินาที
8. `app/demo_api.py`: ส่ง tokens, interpretation, rules, SQL, params, rows และเวลา

**คำอธิบายที่ตรงกับ implementation:** tokens แสดงขั้นตอนตัดคำ แต่ตัวจับ slots
ใช้ substring/regex บน `clean_text` ไม่ได้ใช้ tokens เป็น parser หรือใช้โมเดล NER
ส่วนคำพ้อง/กฎอธิบายย้อนกลับได้จาก YAML และ regex

`app.main` และ schema/seed เดิมเป็น prototype ขอบเขตกว้าง เก็บไว้ให้ศึกษา
สำหรับ Sprint นี้ใช้ `app.demo_api` กับ `db/demo_*` เท่านั้น

## ทดลองว่าอ่านฐานข้อมูลจริง

เริ่มจาก reset แล้วถาม Top 3:

```powershell
.\.venv\Scripts\python.exe -m scripts.local_demo reset
.\.venv\Scripts\python.exe -m scripts.query "สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569"
.\.venv\Scripts\python.exe -m scripts.local_demo add-sale
.\.venv\Scripts\python.exe -m scripts.query "ยอดขายเดือนกันยายน 2569"
.\.venv\Scripts\python.exe -m scripts.query "สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569"
```

หลังเพิ่มรายการปากกา `20 × 15 = 300` ยอดรวมต้องเป็น **1550.00**
และ Top 3 เปลี่ยนเป็น **ปากกา 585, สมุด 420, แฟ้ม 300**
คำสั่ง add-sale เรียกซ้ำไม่สะสมเพิ่ม เป็นขั้นตอนเตรียมข้อมูลของผู้สาธิต
ระบบถามตอบยังอ่านอย่างเดียว จากนั้น reset เพื่อกลับสู่ข้อมูลตั้งต้น

```powershell
.\.venv\Scripts\python.exe -m scripts.local_demo reset
```

คำสั่ง reset ล้างเฉพาะสามตารางของฐานข้อมูลเดโมใน cluster ของโปรเจกต์

## ตรวจระบบก่อนนำเสนอ

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe eval/run_day1.py
```

Tests ใช้ schema ชั่วคราวในฐานข้อมูล `seminar_tests` แยกจาก `seminar_demo`
ตรวจค่าจริงทั้งตาราง รวมลำดับของการจัดอันดับและความเปลี่ยนแปลงเมื่อเพิ่มยอดขาย
รายงาน `output/day1-report.json` มีคำถามในขอบเขต 8 ข้อ เทียบผลเต็มกับ SQL อ้างอิง
และคำถามนอกขอบเขต 4 ข้อ แยกคะแนนการปฏิเสธออกจากการตอบถูก
ทั้งหมดเป็น **development smoke checks** ที่ใช้พัฒนาระบบแล้ว ไม่ใช่ held-out test
และไม่ใช่ผลเปรียบเทียบ LLM หรือ benchmark วิจัย

## การติดตั้งใหม่ / หยุดระบบ

บนเครื่องอื่นที่มี Python 3.12 และ PostgreSQL binaries:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\start-demo.ps1
```

ถ้า PostgreSQL ไม่อยู่ใน `C:\Program Files\PostgreSQL\<version>\bin` ให้ตั้ง `PG_BIN`
ให้ตรงตำแหน่งติดตั้งก่อนรัน ส่วน local helper นี้ออกแบบสำหรับ Windows
กด Ctrl+C ใน terminal API เพื่อหยุด API แล้วหยุด cluster ด้วย:

```powershell
.\.venv\Scripts\python.exe -m scripts.local_demo stop
```

## สถานะ Sprint

- [x] ข้อมูลเล็กและคำตอบตรวจเองได้
- [x] Rule-based ครบเส้นทางบน PostgreSQL จริง
- [x] ยอดรวม / แยกสินค้า / Top-N และตัวอย่าง paraphrase
- [x] แสดง SQL, parameters, interpretation และกฎที่ใช้
- [x] reset และเพิ่มรายการขายแบบทำซ้ำได้
- [x] ทดสอบผลทั้งตารางกับ SQL อ้างอิง
- [ ] ฝั่ง LLM และชุดทดสอบแยกสำหรับการเปรียบเทียบ — งานวันถัดไป
- [ ] หน้าจอนำเสนอและซ้อม — งานวันสุดท้าย
