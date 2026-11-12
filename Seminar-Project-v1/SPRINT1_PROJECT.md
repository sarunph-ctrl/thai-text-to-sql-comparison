# Sprint 1 — WMS Scope, Schema, and Ground Truth

ระยะเวลาแนะนำ: 2 สัปดาห์

เป้าหมาย: ตรึงขอบเขต WMS MVP จัด Schema ให้สร้างฐานข้อมูลใหม่ได้ ทำ Data Dictionary/Business rules และสร้าง SQL อ้างอิง ก่อนขยาย Rule-based หรือปรับ Prompt

## Research Question

ภายใต้ขอบเขตข้อมูลคลังสินค้า รับเข้า และจ่ายออก แนวทาง Rule-based และ LLM แตกต่างกันอย่างไรในด้าน Execution Accuracy, การรองรับรูปแบบภาษาไทย, เวลา, Token, ความสม่ำเสมอ และประเภทข้อผิดพลาด

## Decisions Frozen for Sprint 1

- ใช้ Domain-specific Warehouse Operations ไม่อ้างว่าเป็น General Text-to-SQL หรือ WMS เต็มระบบ
- ใช้โครงสร้างจาก `Succeed_BDMS` Branch `develop` เป็นจุดตั้งต้น
- Phase 1 ใช้ 10 ตาราง Core ตาม `SCOPE_WMS_MVP.md`
- ข้อมูลทดลองต้องเป็น Synthetic data ไม่มีข้อมูลส่วนบุคคลหรือข้อมูลธุรกิจจริง
- เปรียบเทียบ Rule-based กับ LLM ด้วย Schema, คำถาม, Snapshot และ Reference SQL เดียวกัน
- สร้างเฉพาะ `SELECT` และรับคำถามครั้งละหนึ่งคำถาม
- เดโม Sales/Inventory 5 ตารางเดิมเป็น Legacy baseline ไม่ใช่ผลของ WMS MVP
- ตาราง Customer, Shipment, Provider, Driver และ User อยู่ Phase 2 เท่านั้น

## In-scope Query Families

1. Current stock summary แยกตาม Part, Location, Status หรือ Condition
2. Current stock detail ระดับ Serial Number
3. Inbound plan เทียบกับจำนวนที่รับจริง
4. Outbound plan เทียบกับจำนวนที่หยิบจริง
5. Inbound/Outbound Order ตามสถานะและช่วงวันที่

## Out of Scope

- ยอดขาย ราคา ต้นทุน กำไร และภาษี
- Customer, Shipment, Provider, Driver และ User analytics
- สต็อกย้อนหลัง ก่อนมี Movement ledger ที่สมบูรณ์
- Return/RTV/Transfer/Reservation, Lot และวันหมดอายุ
- Prediction, Recommendation และ Optimization
- Multi-turn conversation
- `INSERT`, `UPDATE`, `DELETE` และ DDL
- การอ้างว่า Schema และผลทดลองแทน WMS จริงขององค์กร

## Source Schema Review

พบ `ALL_SQL.sql` ใน Branch `develop` และ `feature/boss` โดยไฟล์ทั้งสองมีเนื้อหาเดียวกัน ณ วันที่ตรวจ มี 15 ตาราง แต่ MVP เลือกเพียง 10 ตาราง

ข้อที่ต้องแก้ก่อนใช้:

- จัดลำดับสร้างตารางตาม Foreign key
- เติม Function ที่ Trigger เรียกแต่ไม่มี Definition ในไฟล์ต้นทาง
- ตรึงค่าของ Status/Condition ที่ปัจจุบันเป็นข้อความอิสระ
- ทบทวนคอลัมน์และ Foreign key ที่อนุญาต `NULL`
- เพิ่ม Constraint ของจำนวนที่ต้องไม่ติดลบ
- สร้าง Seed แบบกำหนดค่าคงที่และไม่มีข้อมูลจริง
- ตัด Dependency ของ 5 ตาราง Phase 2 ออกจาก Fixture ของ MVP

## Sprint Backlog

### A. Scope

- [x] เปลี่ยนโดเมนเป้าหมายเป็น Warehouse Operations
- [x] แยก Phase 1 และ Phase 2
- [x] กำหนด 10 ตาราง MVP และ 5 Query families
- [x] ระบุว่าเดโมเดิมเป็น Legacy baseline
- [ ] ให้อาจารย์หรือผู้ตรวจยืนยันว่า Scope ตรงวัตถุประสงค์ Seminar

### B. Reproducible Schema

- [x] นำ DDL ของ 10 ตารางเข้าสู่โปรเจกต์พร้อมระบุ Provenance
- [x] เรียง DDL และแก้ Dependency ให้สร้างฐานใหม่ได้
- [x] แยก Trigger/function ที่จำเป็นออกจากสิ่งที่ไม่ใช้ใน Text-to-SQL
- [x] เพิ่ม CHECK/NOT NULL ที่สอดคล้องกับ Business rules รุ่น Draft
- [x] ทดสอบสร้าง Schema จากฐานข้อมูลว่าง
- [x] สร้าง Data Dictionary รุ่น WMS MVP

### C. Business Rules

- [x] นิยามความหมายของ `current_stock` หนึ่งแถวต่อหนึ่ง Serial
- [x] ตรึงรายการ Status และ Condition ที่ยอมรับใน Draft
- [x] นิยามจำนวนรับจริงจาก `inbound_detail`
- [x] นิยามจำนวนหยิบจริงจาก `outbound_detail`
- [x] นิยามวันที่ที่ใช้กับ Inbound และ Outbound
- [x] ระบุวิธีนับแถวซ้ำและข้อมูลที่ไม่สมบูรณ์

### D. Synthetic Data and Ground Truth

- [x] สร้าง Seed และ Integrity tests ครอบคลุม Normal, Boundary และ Invalid cases รุ่นแรก
- [x] สร้าง Reference SQL รุ่น Draft ครบทุก Query family
- [x] บันทึก Expected columns, rows, types และ ordering
- [x] ตรวจ Reference SQL กับฐานที่ Reset แล้ว
- [x] เตรียม Independent review guide และแบบบันทึกผลที่ครอบคลุมทุก Case
- [ ] ให้ผู้ตรวจอ่าน Business rules และเฉลยโดยไม่ดูผลระบบก่อน

### E. Evaluation Protocol

- [ ] แยก Development set และ Held-out test set
- [x] สร้าง Candidate Development set 35 ข้อโดยยังไม่เปิด/สร้าง Held-out จริง
- [x] สร้าง Template แยก Development/Held-out โดยยังไม่ใส่ Case ก่อน Review
- [x] กำหนด In-scope/Out-of-scope labels
- [x] ใช้ Execution Accuracy เป็น Primary metric
- [x] กำหนด Valid SQL, Rejection Accuracy, Latency, Token และ Consistency
- [x] สร้าง Metric engine และ Unit tests โดยไม่อ่าน Held-out cases
- [x] สร้าง Secret-resistant Raw-run recorder และ Summary CLI
- [x] สร้างและตรึง Robustness snapshot v2 ที่ให้คำตอบต่างจาก Baseline ทุก Query family
- [x] Version และบันทึก SHA-256 ของ Schema, Seed, Rules และ Ground Truth รุ่น Draft

### F. WMS Rule-based Development Draft

- [x] สร้าง Parser สำหรับ 5 Query families โดยแยก Legacy demo ออกจาก WMS
- [x] สร้าง Parameterized SQL builder จาก Reference SQL ที่ตรวจย้อนกลับได้
- [x] เพิ่ม AST allowlist, SELECT-only, read-only transaction, timeout และ row limit
- [x] ทดสอบ Candidate Development 35 ข้อบน Baseline และ Robustness snapshot
- [x] ปฏิเสธ filter/ความหมายที่ยังไม่รองรับโดยไม่รัน SQL
- [ ] Freeze rules หลัง Independent review ก่อนสร้าง Held-out set

## Two-week Schedule

### Week 1

- Day 1: ตรึง Scope และเลือกตาราง/Query families
- Day 2: จัด DDL และ Dependency ของ 10 ตาราง
- Day 3: สร้างและตรวจ Data Dictionary
- Day 4: นิยาม Business rules และ Status lifecycle
- Day 5: สร้าง Synthetic seed และ Boundary cases

### Week 2

- Day 6: สร้าง Reference SQL และ Expected results
- Day 7: Independent review และแก้ Ground Truth
- Day 8: ออกแบบ Development/Test dataset
- Day 9: กำหนด Evaluation protocol และ Versioning
- Day 10: Sprint review และ Freeze artifacts รุ่นแรก

## Definition of Done

Sprint 1 เสร็จเมื่อ:

1. Scope 10 ตารางและ 5 Query families ได้รับการยืนยัน
2. DDL สร้างฐานข้อมูลว่างได้โดยไม่พึ่ง Schema เดิม
3. Data Dictionary อธิบายทุกตารางและคอลัมน์ใน MVP
4. Business rules และ Status lifecycle ไม่มีคำกำกวมที่ทราบอยู่
5. Reference SQL มี Expected result และตรวจย้อนกลับถึง Seed ได้
6. มีหลักฐาน Independent review หรือระบุชัดว่ายังรอการตรวจ
7. Development/Test protocol และ Version ถูกตรึงก่อนปรับระบบ

หลักฐานล่าสุด: Schema 8/8, Ground Truth/Review 9/9, Protocol 3/3, Snapshot v2 8/8, Metrics 5/5, Raw recorder/CLI 11/11, Candidate Development 6/6, WMS Rule pipeline 5/5 และ Regression suite ทั้งโปรเจกต์ 206/206 เมื่อวันที่ 2026-11-12

## Gate for Phase 2

ห้ามเพิ่ม Customer, Shipment, Provider, Driver หรือ User เพียงเพราะมีอยู่ใน Schema ต้นทาง ต้องผ่าน Definition of Done ของ Phase 1 ก่อน และเพิ่มเฉพาะกลุ่มที่ตอบ Research question ได้โดยไม่ทำให้ชุดประเมินลดคุณภาพ

## Do Not Do During Sprint 1

- อย่าปรับ Rule-based หรือ Prompt จาก Held-out test
- อย่าใช้ข้อมูลจริงจากโปรเจกต์เดิมเป็น Seed
- อย่ารายงานผล 6/10 และ 10/10 ของ Legacy demo เป็นผล WMS
- อย่าเพิ่มตารางเพราะ “อาจได้ใช้” โดยยังไม่มี Query family และ Ground Truth
- อย่าเก็บ API key, Supabase URL/secret หรือข้อมูลส่วนตัวใน Git
