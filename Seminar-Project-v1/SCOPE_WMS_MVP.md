# Scope — Thai Text-to-SQL for Warehouse Operations

**Version:** 1.0-draft

**Updated:** 2026-11-12

**Status:** ขอบเขตเป้าหมายของโครงการ รอการตรวจโดยอาจารย์/ผู้ตรวจอิสระ

## เป้าหมาย

ศึกษาการแปลงคำถามภาษาไทยเป็น SQL ในโดเมน Warehouse Operations โดยเปรียบเทียบ Rule-based กับ LLM ภายใต้ Schema, ข้อมูล, คำถาม และ SQL อ้างอิงชุดเดียวกัน

งานนี้เป็น Domain-specific Text-to-SQL ไม่ใช่ General Text-to-SQL และไม่อ้างว่าเป็น WMS เต็มระบบ

## Research Question

ภายใต้ขอบเขตข้อมูลคลังสินค้า รับเข้า และจ่ายออก แนวทาง Rule-based และ LLM แตกต่างกันอย่างไรในด้าน Execution Accuracy, การรองรับรูปแบบภาษาไทย, เวลา, Token, ความสม่ำเสมอ และประเภทข้อผิดพลาด

## แหล่งที่มาของ Schema

ต่อยอดจากโครงสร้างฐานข้อมูลในโครงการ `Succeed_BDMS`:

- Repository: `https://github.com/ongsarun25/Succeed_BDMS`
- Branch ที่พบ Schema: `develop`
- ไฟล์ต้นทาง: `ALL_SQL.sql`
- Database family: PostgreSQL / Supabase

Schema ต้นทางเป็นงานที่เคยออกแบบและพัฒนามาก่อน แต่ต้องจัดลำดับ DDL เติม Trigger functions และตรวจ Business rules ก่อนนำมาใช้เป็นฐานทดลองที่ทำซ้ำได้

## Phase 1 — MVP

### ตารางที่อยู่ในขอบเขต

ใช้ 10 ตารางที่เกี่ยวข้องโดยตรงกับการปฏิบัติงานคลัง:

| กลุ่ม | ตาราง | หน้าที่ |
|---|---|---|
| Master/Stock | `part_master` | ข้อมูลชนิดสินค้า/อะไหล่ |
| Master/Stock | `part_obj` | สินค้าแต่ละชิ้นที่ระบุด้วย Serial Number |
| Master/Stock | `location` | ตำแหน่งจัดเก็บ |
| Master/Stock | `current_stock` | สถานะและตำแหน่งปัจจุบันของแต่ละ Serial |
| Inbound | `inbound_order` | ส่วนหัวรายการรับเข้า |
| Inbound | `inbound_plan` | จำนวนที่วางแผนรับ แยกตาม Part |
| Inbound | `inbound_detail` | Serial ที่รับจริงและผลตรวจรับ |
| Outbound | `outbound_order` | ส่วนหัวรายการจ่ายออก |
| Outbound | `outbound_plan` | จำนวนที่วางแผนจ่าย แยกตาม Part |
| Outbound | `outbound_detail` | Serial ที่หยิบ/จ่ายจริง |

### Query families ที่รองรับ

1. **Current stock summary** — จำนวน Serial ปัจจุบัน แยกตาม Part, Location, Status หรือ Condition
2. **Current stock detail** — รายการ Serial และตำแหน่งปัจจุบันตามตัวกรองที่รองรับ
3. **Inbound progress** — จำนวนที่วางแผนรับเทียบกับจำนวนที่รับจริง แยกตาม Inbound Order และ Part
4. **Outbound progress** — จำนวนที่วางแผนจ่ายเทียบกับจำนวนที่หยิบจริง แยกตาม Outbound Order และ Part
5. **Operational order status** — จำนวนหรือรายการ Inbound/Outbound Order ตามสถานะและช่วงวันที่

คำถามตัวอย่างเป็นเพียงรูปแบบเป้าหมาย ยังไม่ถือว่าโค้ดปัจจุบันรองรับจนกว่าจะมี Test ยืนยัน:

- สินค้าแต่ละ Part ที่พร้อมใช้งานเหลือกี่ชิ้น
- Location แต่ละจุดมีสินค้าอยู่กี่ชิ้น
- Inbound Order นี้วางแผนรับและรับจริงแล้วกี่ชิ้น
- Outbound Order นี้ต้องจ่ายและหยิบแล้วกี่ชิ้น
- เดือนนี้มี Outbound Order สถานะ Pending กี่รายการ

### ข้อกำหนดร่วม

- สร้างเฉพาะคำสั่ง `SELECT`
- รับคำถามครั้งละหนึ่งคำถาม ไม่มี Conversation memory
- ใช้ Schema และข้อมูลสังเคราะห์ที่ดัดแปลงจากโครงสร้างเดิม ไม่ใช้ข้อมูลธุรกิจจริง
- Rule-based และ LLM ต้องใช้ขอบเขตตาราง คอลัมน์ และ Business rules ชุดเดียวกัน
- คำถามที่มีเงื่อนไขไม่รองรับต้องถูกปฏิเสธ ไม่ตัดเงื่อนไขทิ้งแล้วเปลี่ยนความหมาย
- ตรวจ SQL ด้วย AST allowlist และรันผ่านผู้ใช้ฐานข้อมูลแบบ Read-only

## Out of Scope ของ Phase 1

- ยอดขาย รายได้ ราคา ต้นทุน กำไร หรือภาษี เพราะ Schema ไม่มีข้อมูลราคา
- Customer analytics และคำถามแยกลูกค้า
- Logistics provider, Driver และการวิเคราะห์ผู้ให้บริการขนส่ง
- Shipment route, Proof of Delivery และประสิทธิภาพการขนส่ง
- User performance, Role และ Audit log
- การพยากรณ์ การแนะนำตำแหน่งจัดเก็บ หรือ Optimization
- สต็อกย้อนหลัง ณ วันที่กำหนด เพราะ Schema มี `current_stock` แต่ยังไม่มี Movement history ที่สมบูรณ์
- Return, RTV, Transfer history, Reservation, Lot และวันหมดอายุ
- คำสั่ง `INSERT`, `UPDATE`, `DELETE`, DDL และการดำเนินธุรกรรมจริง
- การอ้างว่า Schema นี้แทน WMS ขององค์กรทั่วไป

## Phase 2 — เพิ่มเมื่อเวลาเพียงพอ

พิจารณาเพิ่มทีละกลุ่มหลัง Phase 1 ผ่านเกณฑ์ประเมินแล้ว:

1. `customer` และคำถาม Outbound ตามลูกค้า
2. `shipment`, `driver`, `logistics_provider` และสถานะการขนส่ง
3. `app_user` และข้อมูลผู้ปฏิบัติงาน โดยต้องตรวจเรื่อง Privacy ก่อน
4. Movement ledger สำหรับตอบสต็อกย้อนหลัง
5. Return/RTV/Transfer/Reservation

การเพิ่ม Phase 2 ต้องเพิ่ม Data Dictionary, Business rules, Reference SQL และชุดทดสอบใหม่ ไม่รวมผลกับ Phase 1 โดยอัตโนมัติ

## เกณฑ์ก่อนขยาย Scope

จะเริ่ม Phase 2 เมื่อ:

- DDL ของ 10 ตาราง MVP สามารถสร้างฐานข้อมูลใหม่ได้ตั้งแต่ศูนย์
- Data Dictionary และ Business rules ได้รับการตรวจ
- Reference SQL ของทุก Query family มี Expected result
- Development/Test split ถูกตรึงก่อนปรับระบบ
- Rule-based และ LLM รัน Evaluation protocol เดียวกันได้
- ข้อผิดพลาดของ Phase 1 ถูกบันทึกและอธิบายได้

## Migration Note

เดโม 5 ตารางด้าน Sales/Inventory ที่มีอยู่ก่อนหน้าเป็น Legacy baseline สำหรับพิสูจน์ Pipeline เท่านั้น ไม่ใช่ Scope เป้าหมายใหม่ ผล 6/10 และ 10/10 จากเดโมเดิมห้ามนำมาเป็นผลของ WMS MVP
