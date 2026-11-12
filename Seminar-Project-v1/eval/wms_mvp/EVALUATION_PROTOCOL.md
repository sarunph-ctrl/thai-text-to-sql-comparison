# Evaluation Protocol — WMS MVP

**Version:** 1.0-draft

**Updated:** 2026-11-12

**Status:** Protocol draft; ยังไม่สร้างหรือเปิด Held-out cases

## เป้าหมายการประเมิน

เปรียบเทียบ Rule-based กับ LLM บนคำถาม Schema, Business rules, Data snapshot และ Reference SQL เดียวกัน โดยวัดความถูกต้องจากผลลัพธ์ที่รันจริง ไม่ตัดสินจากความเหมือนของข้อความ SQL

ผลที่รายงานต้องเป็นผลของ WMS MVP เท่านั้น ห้ามรวมผลเดโม Sales/Inventory เดิม

## เงื่อนไขก่อนเริ่ม

1. Independent review ของ Scope, Business rules และ Ground Truth ผ่านหรือมีการแก้ครบแล้ว
2. Schema, Seed, Rules และ Ground Truth มี Version/Manifest ที่ตรวจ Hash ผ่าน
3. Development และ Held-out ถูกแยกก่อนเริ่มปรับ Rule-based/Prompt สำหรับ WMS
4. Environment, Model ID, Temperature, Token limit, Timeout และ Code commit ถูกบันทึก
5. ห้ามมี API key หรือข้อมูลจริงใน Dataset/Output

## การแบ่ง Dataset

### Development set

ใช้เพื่อ:

- เพิ่มคำศัพท์และปรับ Intent/SQL Builder
- ปรับ Prompt และ Few-shot examples หากการทดลองอนุญาต
- แก้ Bug จาก Error analysis

ดูผลซ้ำได้และเปลี่ยนระบบได้ แต่ทุกการเปลี่ยนต้องไม่ใช้ Held-out outcomes

### Held-out test set

ใช้ประเมินรอบสุดท้าย ห้ามใช้คำถามหรือผลรายข้อเพื่อปรับกฎ Prompt หรือเลือกโมเดลก่อน Freeze ผล

แนวทางที่แนะนำ:

- ให้ Reviewer เป็นผู้ถือชุดคำถามจนถึง Final run หรือ
- หากทำคนเดียว ให้สร้างและ Hash ชุดทดสอบก่อนรันครั้งแรก แล้วห้ามปรับระบบจากผลรายข้อ

คำว่า “โมเดลไม่เห็น Test” หมายถึงคำถาม Test ไม่ถูกใช้เป็น Prompt example หรือข้อมูลสำหรับปรับระบบก่อนประเมิน โมเดลยังต้องได้รับคำถามนั้นตอน Final inference ตามปกติ

## ขนาดขั้นต่ำและการกระจาย

| Split | In-scope | Out-of-scope | รวม |
|---|---:|---:|---:|
| Development | 25 | 10 | 35 |
| Held-out | 25 | 10 | 35 |
| รวม | 50 | 20 | 70 |

In-scope แต่ละ Split มี 5 ข้อต่อ Query family รวม 25 ข้อ:

1. Current stock summary
2. Current stock detail
3. Inbound progress
4. Outbound progress
5. Operational order status

ในแต่ละ Family ควรมีภาษาอย่างน้อย:

- รูปตรงตามนิยาม
- คำพ้องหรือการเรียงคำต่างกัน
- ภาษาสุภาพหรือมีคำฟุ่มเฟือยที่ไม่เปลี่ยนความหมาย
- ตัวกรอง/ตัวระบุที่รองรับ
- Boundary case เช่น ศูนย์, วันที่ขอบเดือน, Location ว่าง หรือสถานะเฉพาะ

ห้ามสร้าง Held-out ด้วยการเปลี่ยนเพียงคำลงท้ายจาก Development ข้อเดียวกัน ต้องแยกตาม Semantic template หรือเงื่อนไข ไม่ใช่สุ่มแยกประโยคหลัง Paraphrase

## Scope Labels

### `in_scope`

คำถามมีความหมายครบและตอบได้ด้วยหนึ่งใน 5 Query families โดยใช้เฉพาะ 10 ตาราง MVP และเงื่อนไขที่รองรับ

Expected status คือ `ok` และต้องมี Reference SQL/Expected result

### `out_of_scope`

คำถามต้องถูกปฏิเสธโดยไม่รัน SQL เมื่อขอข้อมูล/การทำงานที่อยู่นอก Scope เช่น:

- ราคาหรือยอดขาย
- สต็อกย้อนหลัง
- Customer, Shipment, Provider, Driver หรือ User analytics
- Return/Transfer/Reservation/Lot/Expiry
- เขียนหรือแก้ข้อมูล
- คำถามต่อเนื่องที่ต้องใช้ Conversation memory
- เงื่อนไขที่ระบบไม่รองรับและห้ามละทิ้ง

Expected status คือ `unsupported`, `sql = null` และต้องไม่มี Database execution

อย่ารวมคำถามไร้ความหมายหรือกำกวมจนมนุษย์ยังระบุ Expected behavior ไม่ได้ ให้แยกเป็น Dataset ด้าน Clarification ในอนาคต

## Primary Metrics

### 1. In-scope Execution Accuracy

```text
จำนวน In-scope cases ที่ผลลัพธ์ตรง Reference
------------------------------------------------
จำนวน In-scope cases ทั้งหมด
```

ผลลัพธ์ต้องตรง:

- จำนวนคอลัมน์และชื่อคอลัมน์ที่กำหนด
- ทุกแถวและทุกค่า
- แถวซ้ำ
- ลำดับเฉพาะ Case ที่ `ordered: true`

`unsupported`, Invalid SQL, Guard rejection, Database error, Timeout และผลถูกตัด (`truncated`) นับเป็นผิดและยังอยู่ในตัวหาร

SQL text ไม่จำเป็นต้องเหมือน Reference หากรันแล้วคืนผลที่ถูกต้องภายใต้ Snapshot เดียวกัน

### 2. Out-of-scope Rejection Accuracy

```text
จำนวน Out-of-scope cases ที่ปฏิเสธโดยไม่สร้าง/รัน SQL
------------------------------------------------------
จำนวน Out-of-scope cases ทั้งหมด
```

ต้องรายงานแยกจาก Execution Accuracy ห้ามรวมจนความสามารถปฏิเสธกลบความถูกต้องของคำถาม In-scope

## Secondary Metrics

### Valid SQL Rate

สัดส่วน In-scope cases ที่สร้างหนึ่ง `SELECT`, ผ่าน AST allowlist และ PostgreSQL `EXPLAIN`/Execution ได้ ไม่ได้แปลว่าคำตอบถูก

### Latency

วัดเวลาตั้งแต่ Method รับข้อความจนได้ผล/การปฏิเสธ:

- Rule-based: Normalize + Tokenize + Intent + Builder + Validation + DB
- LLM: Prompt construction + API generation + Parse + AST validation + DB

เปิด Connection/Pool ไว้ก่อนวัดและไม่รวมเวลาเริ่มโปรแกรม รายงาน Median และ p95 แยก Method รวมทั้งจำนวน Timeout

### Token Usage

รายงาน Input, Output และ Total tokens ของ LLM พร้อม Coverage ว่ามีกี่ Call ที่ Provider ส่ง Usage จริง ค่าไม่ทราบต้องเป็น `null` ไม่ใช่ศูนย์

ต้นทุนเป็นเงินรายงานเฉพาะเมื่อมีอัตราค่าบริการที่ตรวจสอบได้ มิฉะนั้นรายงาน Token เท่านั้น

### LLM Consistency

รัน Held-out ทุกข้อ 3 รอบด้วย Model/Prompt/Temperature เดียวกัน:

- Per-case correctness rate: ถูกกี่รอบจาก 3
- Stable correct: ถูกทั้ง 3 รอบ
- Result agreement: สัดส่วนของผลลัพธ์แบบเดียวกันที่พบบ่อยที่สุด

การเปลี่ยน Model ID, Prompt, Temperature หรือ Provider ถือเป็น Configuration ใหม่และห้ามรวมรอบเข้าด้วยกัน

### Error Taxonomy

จัดข้อผิดพลาดหนึ่ง Primary category ต่อ Case-run:

- `intent_missed`
- `condition_dropped`
- `wrong_table_or_join`
- `wrong_filter_or_status`
- `wrong_date_boundary`
- `wrong_aggregation_or_grouping`
- `wrong_zero_or_null_handling`
- `invalid_or_rejected_sql`
- `database_error_or_timeout`
- `incorrect_unsupported`
- `unsafe_acceptance`
- `truncated_result`

## Multiple Data Snapshots

ขั้นต่ำให้ใช้:

1. `wms_seed_v1`: Baseline snapshot ปัจจุบัน
2. `wms_seed_v2`: Synthetic perturbation ที่เปลี่ยนจำนวน/สถานะ/วันที่ แต่คง Schema และ Business rules

คำถามเชิงโครงสร้างเดียวกันควรถูกกับทั้งสอง Snapshot เพื่อจับ SQL ที่ Hard-code คำตอบ อย่างไรก็ตาม Reference result ต้องสร้างแยกต่อ Snapshot และ Freeze ด้วย Hash

ถ้าเวลาจำกัด ให้รายงานผลหลักบน v1 และใช้ v2 เป็น Robustness check แยกตาราง ห้ามรวมโดยไม่บอกจำนวน Snapshot

Snapshot v2 Draft อยู่ที่ `db/wms_mvp_seed_v2.sql` และ Expected results อยู่ที่ `eval/wms_mvp/snapshot_v2_expected.yaml` ทั้งสองยังรอ Independent review เช่นเดียวกับ Ground Truth v1

## Run Procedure

1. Checkout Commit ที่จะประเมินและยืนยัน Working tree สะอาด
2. ตรวจ Manifest hashes
3. Reset Database ไปยัง Snapshot ที่กำหนด
4. รัน Reference SQL เพื่อยืนยัน Expected result
5. Warm up แต่ละ Method ด้วยคำถามที่ไม่อยู่ใน Dataset 1 ครั้ง
6. รัน Rule-based 1 รอบต่อ Case ต่อ Snapshot
7. รัน LLM 3 รอบต่อ Case ต่อ Snapshot โดยไม่ Retry เงียบ ๆ; บันทึก Retry แยก
8. เก็บ Raw output แบบไม่รวม Secret
9. คำนวณ Metrics จาก Raw output ด้วย Script เดียวกัน
10. Freeze Output, Config และ Manifest ก่อนทำ Error analysis

ลำดับ Case ควรถูก Shuffle ด้วย Seed ที่บันทึกไว้ และใช้ลำดับเดียวกันเมื่อเปรียบเทียบ Configuration

## Reporting

รายงานอย่างน้อย:

- จำนวน Case แยก Split/Scope/Family/Difficulty
- Execution Accuracy และ 95% Wilson interval
- Out-of-scope Rejection Accuracy
- Valid SQL Rate
- Median/p95 latency และ Timeout count
- Token totals/median พร้อม Usage coverage
- Stable-correct และ Result agreement ของ LLM
- Error taxonomy แยก Method
- Model/Prompt/Schema/Seed/Code versions
- ข้อจำกัด: Synthetic data, Domain-specific, Dataset size และ Independent-review status

Rule-based กับ LLM เป็น Paired evaluation บนคำถามเดียวกัน หากจำนวน Case เพียงพออาจใช้ McNemar test ประกอบ แต่ผลหลักยังต้องแสดงจำนวนจริงและช่วงความเชื่อมั่น ไม่สรุปจาก p-value อย่างเดียว

## Leakage Rules

- ห้ามย้าย Held-out case ที่ผิดมา Development แล้วรายงาน Accuracy เดิม
- ห้ามเลือก Prompt/Model จาก Held-out score
- ห้ามแก้ Reference ให้ตรงผลระบบโดยไม่มี Independent review และ Version ใหม่
- ห้ามให้ Ground Truth SQL/Expected rows อยู่ใน LLM prompt
- Prompt ส่งได้เฉพาะ Schema, Business definitions, Allowlist และคำถามปัจจุบันตาม Protocol

หลัง Final run สามารถเปิด Held-out เพื่อวิเคราะห์ข้อผิดพลาดได้ แต่การแก้ระบบหลังจากนั้นต้องรายงานเป็นรอบใหม่บน Test set รุ่นใหม่
