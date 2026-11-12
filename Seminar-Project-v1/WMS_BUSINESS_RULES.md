# WMS MVP Business Rules

**Version:** 1.0-draft

**Updated:** 2026-11-12

**Review status:** ตรวจเทียบ Schema, Seed และโค้ดต้นทางแล้ว; รอ Independent review

กฎเหล่านี้ใช้ร่วมกันทั้ง Rule-based, LLM และ Reference SQL เพื่อให้การเปรียบเทียบวัดวิธีแปลงภาษาเป็น SQL ไม่ใช่วัดความแตกต่างของนิยาม

## กฎสต็อกปัจจุบัน

### STOCK-01 — หน่วยการนับ

หนึ่งแถวใน `current_stock` แทน Serial หนึ่งชิ้น ดังนั้นจำนวนสต็อกปัจจุบันคำนวณด้วย `COUNT(DISTINCT current_stock.serial_no)`

อย่านับจาก `part_obj` โดยตรง เพราะ Serial อาจมี Master record แต่ไม่อยู่ใน Snapshot สต็อกปัจจุบัน

### STOCK-02 — การจำแนก Part

เชื่อม `current_stock.serial_no → part_obj.serial_no → part_master.part_id` เพื่อหาชนิดสินค้า

### STOCK-03 — พร้อมใช้งาน/พร้อมหยิบ

คำว่า “พร้อมใช้งาน”, “พร้อมหยิบ” หรือ “สต็อกที่ใช้ได้” หมายถึง:

```text
current_stock.status = 'Available'
AND current_stock.condition = 'Good'
```

คำว่า “สต็อกทั้งหมดในระบบ” หมายถึงทุกแถวใน `current_stock` โดยไม่กรอง Status หรือ Condition

### STOCK-04 — Status และ Condition เป็นคนละแกน

- `status`: `Receiving`, `Available`, `In Transit`, `Quarantine`
- `condition`: `Good`, `Damaged`

ห้ามตีความ `Damaged` เป็น Status หรือ `Quarantine` เป็น Condition

### STOCK-05 — Location ว่าง

`location_id = NULL` หมายถึงไม่มี Location ปัจจุบันใน Schema ไม่ได้แปลว่าข้อมูลผิดเสมอ เช่น Serial ที่ `In Transit`

เมื่อสรุปทุก Location ให้แสดงกลุ่ม `ไม่ระบุตำแหน่ง` สำหรับค่า `NULL` แทนการละทิ้งแถวนั้น

### STOCK-06 — Snapshot เท่านั้น

`current_stock` ใช้ตอบสถานะปัจจุบัน ไม่ใช้คำนวณ “คงเหลือ ณ วันที่...” เพราะไม่มี Movement history สำหรับย้อนเวลา

## กฎ Inbound

### IN-01 — จำนวนที่วางแผนรับ

จำนวนที่วางแผนรับต่อ Inbound Order และ Part คือ `inbound_plan.expected_qty`

### IN-02 — จำนวนที่รับจริง

จำนวนรับจริงต่อ Inbound Order และ Part คือจำนวน Serial ไม่ซ้ำใน `inbound_detail` โดยหา Part ผ่าน `part_obj`:

```text
COUNT(DISTINCT inbound_detail.serial_no)
```

### IN-03 — เปรียบเทียบแผนกับผลจริง

ผลต้องแสดงแผนที่ยังรับเป็นศูนย์ด้วย จึงใช้ `inbound_plan` เป็นฐานและ `LEFT JOIN` ยอดรับจริง สำหรับ MVP รุ่นแรก

ถ้าภายหลังอนุญาตรับ Part ที่ไม่มีในแผน ต้องเปลี่ยน Reference SQL ให้รวมคู่ Order–Part จากทั้ง Plan และ Actual และเพิ่ม Version ของกฎนี้

### IN-04 — Progress

```text
remaining_qty = expected_qty - received_qty
progress_percent = received_qty * 100.0 / expected_qty
```

ไม่บังคับให้ `remaining_qty` ต้องไม่ติดลบและไม่ตัด Progress ไว้ที่ 100% เพราะค่าที่เกินแผนเป็นความผิดปกติที่ควรถูกมองเห็น

### IN-05 — ฐานเวลา

คำถาม Inbound ตามวันหรือเดือนใช้ `inbound_order.arrival_date` ไม่ใช้ `created_at`, `updated_at` หรือ `time_received_by` เว้นแต่คำถามระบุชัดว่าต้องการเวลารับจริง

Order ที่ `arrival_date IS NULL` ไม่อยู่ในช่วงวันที่ แต่ต้องไม่ถูกนับเป็นวันที่อื่นโดยสมมติค่าเอง

### IN-06 — สถานะ

Phase 1 รองรับการกรอง Exact value: `Draft Plan`, `Received`, `Completed`, `Cancelled`

ยังไม่รวม `Received` และ `Completed` เป็นกลุ่มเดียวกัน เพราะโค้ดต้นทางมีการเขียนทั้งสองค่าแต่ความต่างทางธุรกิจยังไม่ได้รับการยืนยัน

## กฎ Outbound

### OUT-01 — จำนวนที่วางแผนจ่าย

จำนวนที่วางแผนจ่ายต่อ Outbound Order และ Part คือ `outbound_plan.expected_qty`

### OUT-02 — จำนวนที่หยิบจริง

จำนวนที่หยิบจริงต่อ Outbound Order และ Part คือจำนวน Serial ไม่ซ้ำใน `outbound_detail` โดยหา Part ผ่าน `part_obj`:

```text
COUNT(DISTINCT outbound_detail.serial_no)
```

### OUT-03 — เปรียบเทียบแผนกับผลจริง

ใช้ `outbound_plan` เป็นฐานและ `LEFT JOIN` ยอดหยิบจริง เพื่อให้แผนที่ยังหยิบเป็นศูนย์ยังปรากฏในผลลัพธ์ กฎเรื่อง Remaining และ Progress ใช้หลักเดียวกับ IN-04

### OUT-04 — ฐานเวลา

คำถาม Outbound ตามวันหรือเดือนใช้ `outbound_order.order_date` เว้นแต่ระบุชัดว่าต้องการเวลาหยิบจริงจาก `time_picked_by`

### OUT-05 — สถานะ Phase 1

- `Pending`: ยังอยู่ในคิวการหยิบ
- `Picked`: บันทึกการหยิบเสร็จตามกระบวนการ MVP

`Shipped`, `Delivered` และ POD เป็น Phase 2 จึงต้องถูกปฏิเสธใน Phase 1

## กฎเวลาและภาษา

### TIME-01 — ช่วงเดือน

เดือนใช้ช่วงครึ่งเปิด:

```text
date_column >= วันแรกของเดือน
AND date_column < วันแรกของเดือนถัดไป
```

รองรับปีสี่หลักทั้ง พ.ศ. และ ค.ศ. โดยแปลง พ.ศ. เป็น ค.ศ. ก่อนสร้าง Parameter

### TIME-02 — Timestamp

Timestamp มี Time zone และ Fixture ใช้ `Asia/Bangkok` (`+07:00`) การตัดช่วงวันจาก Timestamp ต้องกำหนด Time zone เดียวกันก่อนประเมิน

### TEXT-01 — ตัวระบุเฉพาะ

Part ID, Serial Number, Location ID, Inbound ID และ Outbound ID ต้องใช้เป็น Parameter ไม่ต่อ String เข้า SQL โดยตรง

### TEXT-02 — คำที่ไม่ทราบความหมาย

ห้ามละทิ้งเงื่อนไขที่ Parser/LLM ไม่เข้าใจ หากเงื่อนไขมีผลต่อคำตอบต้องปฏิเสธพร้อมเหตุผล

## กฎผลลัพธ์

### RESULT-01 — แถวศูนย์

- Plan-vs-actual ต้องแสดงแผนที่ Actual เป็น 0
- Stock summary ตาม Master ทุก Part จะแสดง Part ที่ไม่มี Stock เป็น 0 ก็ต่อเมื่อคำถามใช้คำว่า “ทุก Part” หรือ “รวม Part ที่ไม่มีของ”
- Stock summary ทั่วไปแสดงเฉพาะ Part ที่มีแถวใน `current_stock`

### RESULT-02 — ลำดับ

ผล Detail เรียง ID จากน้อยไปมากเพื่อให้ทำซ้ำได้ ผล Ranking เรียง Metric จากมากไปน้อย แล้วใช้ ID จากน้อยไปมากเป็น Tie-break

### RESULT-03 — แถวซ้ำ

Metric ระดับ Serial ใช้ `COUNT(DISTINCT serial_no)` เพื่อไม่ให้ Join ขยายจำนวนโดยไม่ตั้งใจ Reference SQL ต้องกำหนด Grain ก่อนเลือกคอลัมน์และ Grouping

## ขอบเขตความปลอดภัย

### SAFE-01 — Read-only

อนุญาตเฉพาะ `SELECT` หนึ่ง Statement และตรวจ AST กับ Allowlist ของ 10 ตาราง/คอลัมน์ก่อนรัน

### SAFE-02 — ไม่มีข้อมูลจริง

ใช้เฉพาะ Synthetic seed ห้ามนำ Serial, Invoice, Customer, User หรือข้อมูลธุรกิจจริงเข้า Evaluation repository

## Rule-to-Query Mapping

| Query family | กฎหลัก |
|---|---|
| Current stock summary | STOCK-01–06, RESULT-01–03 |
| Current stock detail | STOCK-02–06, TEXT-01, RESULT-02 |
| Inbound progress | IN-01–06, TIME-01–02, RESULT-01–03 |
| Outbound progress | OUT-01–05, TIME-01–02, RESULT-01–03 |
| Operational order status | IN-05–06, OUT-04–05, TIME-01 |

## Baseline Checks จาก Seed

- สต็อกปัจจุบันทั้งหมด 6 Serial
- พร้อมใช้ (`Available` + `Good`) 2 Serial และเป็น `PART-A`
- `PART-A`: Available 2, In Transit 1, Receiving 1
- `PART-B`: In Transit 1, Quarantine 1
- `INB-001`: PART-A แผน 3/รับ 3, PART-B แผน 2/รับ 2
- `INB-002`: PART-A แผน 2/รับ 1, PART-C แผน 1/รับ 0
- `OUT-001`: PART-A แผน 1/หยิบ 1, PART-B แผน 1/หยิบ 1
- `OUT-002`: PART-A และ PART-C แผนอย่างละ 1/หยิบ 0

ตัวเลขเหล่านี้เป็น Sanity check ของ Fixture ไม่ใช่ผลการประเมิน Rule-based หรือ LLM

## ประเด็นรอ Independent Review

1. `Received` กับ `Completed` ต่างกันอย่างไร และควรรวมเป็น “รับเสร็จ” หรือไม่
2. Serial เดียวควรปรากฏใน Inbound/Outbound Detail ได้มากกว่าหนึ่ง Order ตลอดอายุข้อมูลหรือไม่
3. “พร้อมใช้” ต้องตรวจทั้ง `Available` และ `Good` ตามกฎ STOCK-03 หรือไม่
4. `location_id = NULL` อนุญาตกับ Status ใดบ้าง
5. `time_received_by` และ `time_picked_by` ควรเปลี่ยนชื่อเป็น `_at` หรือไม่
6. การรับ/หยิบเกินแผนควรถูกอนุญาตเพื่อแสดง Exception หรือปฏิเสธตั้งแต่ฐานข้อมูล

## Change Control

หากคำตอบของประเด็นข้างต้นทำให้กฎเปลี่ยน ต้องเพิ่ม Version ของเอกสาร, DDL, Seed และ Reference SQL แล้วรัน Evaluation ใหม่ ห้ามแก้เฉลยหลังเห็นผล Held-out test โดยยังรายงานเป็นรอบเดิม

## Independent Review Record

| Reviewer / บทบาท | วันที่ | Version | ผลตรวจ | ข้อเสนอแนะ |
|---|---|---|---|---|
| รอระบุ | — | 1.0-draft | รอตรวจ | — |
