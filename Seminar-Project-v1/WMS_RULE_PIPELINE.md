# WMS Rule-based Pipeline (Development Draft)

สถานะ: ใช้งานกับ Candidate Development set ได้แล้ว แต่ **ยังไม่ใช่ผล Evaluation** และยังไม่ผ่าน Independent review

## Pipeline

1. `app.normalization.normalize` ทำ Unicode normalization และจัดช่องว่าง
2. `app.wms.parser.parse_wms_question` จับ Query family, ช่วงเวลา และเงื่อนไขที่รองรับ
3. `app.wms.builder.build_wms_query` เลือก SQL template รูปทรงตายตัวและ bind parameters
4. `app.wms.guard.check_wms_template` parse SQL เป็น AST แล้วตรวจ SELECT-only, ตาราง/คอลัมน์/function, parameter และ `LIMIT <= 200`
5. `app.wms.pipeline.run_wms_rule_pipeline` ใช้ `EXPLAIN` ก่อน execute ภายใน read-only transaction และ statement timeout

หากความหมายไม่อยู่ใน 5 families หรือมี filter ที่ยังไม่รองรับ ระบบจะปฏิเสธโดยไม่สร้างหรือรัน SQL แทนการเดา

## Query families ที่ทำงานแล้ว

| Family | ตารางหลัก | ผลลัพธ์ |
|---|---|---|
| Current stock summary | `current_stock`, `part_obj`, `part_master` | จำนวน Serial แยก Part และสถานะ |
| Current stock detail | `current_stock`, `part_obj`, `part_master` | Serial ใน Quarantine พร้อมตำแหน่งและสภาพ |
| Inbound progress | `inbound_plan`, `inbound_detail`, `inbound_order` | แผน รับจริง และคงเหลือ |
| Outbound progress | `outbound_plan`, `outbound_detail`, `outbound_order` | แผน หยิบจริง และคงเหลือ |
| Operational order status | `outbound_order` | จำนวน Outbound แยกสถานะในเดือนที่ระบุ |

## หลักฐานอัตโนมัติ

`tests/test_wms_rule_pipeline.py` รัน Candidate Development 35 ข้อบน `wms_seed_v1` และ `wms_seed_v2`:

- In-scope 25 ข้อ: ต้องรันสำเร็จและผลทั้งตารางตรง Reference SQL
- Out-of-scope 10 ข้อ: ต้องคืน `unsupported` และ `sql_executed = false`
- Guard tests: ปฏิเสธ non-SELECT, ตารางนอก schema และจำนวน bind parameters ไม่ตรง
- Explicit identifier filter ที่ยังไม่รองรับ: ต้องปฏิเสธ ไม่ทิ้งเงื่อนไขเงียบ ๆ

การผ่านชุดนี้พิสูจน์เพียงว่า implementation สอดคล้องกับ **Development set ที่ใช้พัฒนา** ไม่ใช่ค่าความแม่นยำบนข้อมูลที่ระบบไม่เคยเห็น

## จุดที่ต้อง Independent review

1. ตรวจว่า 5 Query families ตรง Scope และคำศัพท์ของผู้ใช้ WMS จริง
2. ตรวจ Business rules และ Reference SQL โดยไม่ดูคำตอบของระบบก่อน
3. ตรวจ label และความเป็นธรรมของ 35 Candidate Development questions
4. หลังแก้และ freeze แล้ว ให้ผู้ตรวจสร้าง Held-out questions แยกต่างหาก
5. ห้ามปรับ parser/builder จาก Held-out; ใช้ Held-out รายงานผลครั้งสุดท้ายเท่านั้น

## คำสั่งตรวจ

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_wms_rule_pipeline.py -q
```

## ทดลองผ่านหน้าเว็บ

```powershell
powershell -ExecutionPolicy Bypass -File .\start-demo.ps1
```

จากนั้นเปิด `http://127.0.0.1:8000/wms` หน้า WMS แยกจาก Legacy demo ที่ `/` และเรียก API `POST /wms/query` โดยไม่เรียก LLM
