# Sprint 1 - Scope, Schema, and Ground Truth

ระยะเวลาแนะนำ: 2 สัปดาห์
เป้าหมาย: ตรึงขอบเขต โครงสร้างข้อมูล นิยามธุรกิจ และ SQL อ้างอิง ก่อนขยาย Rule-based หรือปรับ Prompt

## Research question

ภายใต้โดเมนการขายและคลังสินค้า แนวทาง Rule-based และ LLM แตกต่างกันอย่างไรในด้าน Execution Accuracy ความสามารถในการรองรับภาษาไทยที่หลากหลาย เวลา Token ความสม่ำเสมอ และประเภทข้อผิดพลาด

## Decisions frozen for Sprint 1

- เริ่มจาก Domain-specific ไม่อ้างว่าเป็น General Text-to-SQL
- โดเมนเป็นข้อมูลสังเคราะห์ด้านการขายและคลังสินค้า ไม่อ้างแทน WMS จริง
- เปรียบเทียบ Rule-based กับ LLM โดยใช้คำถาม Schema ข้อมูล และ SQL อ้างอิงชุดเดียวกัน
- สร้างเฉพาะคำสั่ง SELECT
- รับคำถามครั้งละหนึ่งคำถาม ไม่มี conversation memory
- IntelSphere เป็น LLM baseline รุ่นแรก; Local/Enterprise LLM เป็นการทดลองเพิ่มเติมภายหลัง

## In-scope query families

1. ยอดขายรวมรายเดือน
2. ยอดขายรายเดือนแยกตามสินค้า
3. Top-N สินค้าตามยอดขายเป็นเงิน
4. สินค้าคงเหลือแยกตามสินค้าและคลัง จาก movement ทั้งหมดที่บันทึก
5. จำนวนสินค้าจ่ายออกรายเดือน แยกตามสินค้าและรวมทุกคลัง

## Out of scope

- คำสั่ง INSERT, UPDATE, DELETE และ DDL
- ตัวกรองสินค้า คลัง หรือลูกค้าที่ระบุชื่อ
- การเปรียบเทียบหลายช่วงเวลา
- สต็อกย้อนหลัง ณ วันที่กำหนด
- การโอนคลัง การจอง การคืนสินค้า Lot, Serial และวันหมดอายุ
- คำถามต่อเนื่องหลายรอบ
- การอ้างว่า Schema และผลทดลองแทน WMS ขององค์กรจริง

## Business definitions to review

### Sales revenue

- ยอดขาย = SUM(order_items.qty * order_items.unit_price)
- นับเฉพาะ orders.status = paid
- ใช้ orders.order_date เป็นฐานเวลา
- ใช้ order_items.unit_price ซึ่งเป็นราคาขณะขาย ไม่ใช้ products.price
- "ขายดีที่สุด" หมายถึงยอดเงิน ไม่ใช่จำนวนชิ้น
- หากยอดเท่ากัน เรียง products.id จากน้อยไปมาก

### Stock balance

- คงเหลือ = opening + receipt - issue
- คำนวณจากทุก movement ที่บันทึก
- แยกตามสินค้าและคลัง
- แสดงคู่สินค้า/คลังที่ไม่มี movement เป็นศูนย์
- ไม่กรองด้วย orders.status
- ไม่ใช่ยอดย้อนหลัง ณ วันที่กำหนด

### Monthly outbound

- จ่ายออก = SUM(stock_movements.qty) เมื่อ movement_type = issue
- ใช้ stock_movements.movement_date เป็นฐานเวลา
- แยกตามสินค้าและรวมทุกคลัง
- ไม่กรองด้วย orders.status
- รวม movement ที่เกี่ยวและไม่เกี่ยวกับการขาย

## Existing evidence to review

- Schema: `db/demo_schema.sql`
- Sales seed: `db/demo_seed.sql`
- Inventory seed: `db/demo_inventory_seed.sql`
- Sales definition: `config/demo.yaml`
- Inventory definitions: `config/inventory.yaml`
- Reference SQL: `eval/sprint2/references.yaml`
- Existing development questions: `eval/sprint2/dev.yaml`
- Existing preliminary test questions: `eval/sprint2/test.yaml`

## Sprint backlog

### A. Scope review

- [ ] ตรวจว่า 5 query families ตรงกับวัตถุประสงค์ของรายงาน
- [ ] ตรวจว่า In-scope และ Out-of-scope ใช้ถ้อยคำเดียวกันในรายงาน สไลด์ Prompt และหน้าเดโม
- [ ] ตัดคำอ้างที่สื่อว่าเป็น WMS เต็มระบบ
- [ ] ระบุว่าผล 10 ข้อเดิมเป็น preliminary evaluation

### B. Schema review

- [ ] ตรวจ PK, FK, UNIQUE และ CHECK ของทั้ง 5 ตาราง
- [ ] ตรวจความหมายของ `products.price` และ `order_items.unit_price`
- [ ] ตรวจความสัมพันธ์ระหว่าง `stock_movements.order_item_id` กับรายการขาย
- [ ] ตรวจว่าการขายและการจ่ายออกเป็นคนละเหตุการณ์
- [ ] ทำ Data Dictionary ระบุชื่อคอลัมน์ ชนิดข้อมูล ความหมาย และตัวอย่าง

### C. Ground-truth review

- [ ] รัน SQL อ้างอิงทุกคำสั่งกับฐานข้อมูลที่ reset แล้ว
- [ ] ตรวจยอดขายกันยายนด้วยมือ: 220 + 200 + 200 + 250 + 260 + 120 = 1,250 บาท
- [ ] ตรวจว่า pending, cancelled, สิงหาคม และตุลาคมไม่ถูกรวมในยอดกันยายน
- [ ] ตรวจผลแยกสินค้า Top-N คงเหลือ และจ่ายออกกับ Seed data
- [ ] ตรวจลำดับเมื่อยอดเท่ากัน
- [ ] บันทึก expected columns, rows และ ordering ของทุก reference

### D. Independent review

- [ ] ให้ผู้ตรวจที่เข้าใจ SQL ตรวจ Business definitions
- [ ] ให้ผู้ตรวจรันหรืออ่าน Reference SQL โดยไม่ดูผลของ Rule-based/LLM ก่อน
- [ ] บันทึกชื่อบทบาท วันที่ และข้อแก้ไขจากผู้ตรวจ
- [ ] ถ้ามีการแก้ Ground Truth ให้สร้าง version ใหม่และเก็บประวัติ

### E. Evaluation design draft

- [ ] กำหนด Development set และ Held-out test set
- [ ] กำหนด In-scope และ Out-of-scope labels
- [ ] กำหนด Execution Accuracy เป็น Primary metric
- [ ] กำหนด Valid SQL, Unsupported Accuracy, Latency, Token และ Consistency เป็น Secondary metrics
- [ ] วางแผนหลาย Data snapshots และการรัน LLM ซ้ำ

## Two-week schedule

### Week 1

- Day 1: ตรึง Research question, In-scope และ Out-of-scope
- Day 2: ตรวจ Schema และจัดทำ Data Dictionary
- Day 3: ตรวจ Business definitions กับตัวอย่างข้อมูล
- Day 4: รันและตรวจ Reference SQL ทุกประเภท
- Day 5: ทำ Expected-result sheet และรายการ Boundary cases

### Week 2

- Day 6: เตรียมเอกสารสำหรับ Independent review
- Day 7: รับ Feedback และแก้นิยาม/Reference SQL
- Day 8: ออกแบบ Development/Test dataset รุ่นใหม่
- Day 9: กำหนด Evaluation protocol และ Versioning
- Day 10: Sprint review, สรุปข้อแก้ไข และ Freeze Sprint 1 artifacts

## Definition of Done

Sprint 1 เสร็จเมื่อ:

1. ขอบเขต 5 query families และรายการ Out-of-scope ได้รับการยืนยัน
2. Schema และ Data Dictionary อธิบายทุกตารางและคอลัมน์ที่ใช้ได้
3. Business definitions ไม่มีคำกำกวม
4. Reference SQL ทุกรายการรันได้และมี Expected result
5. มีหลักฐานการตรวจโดยบุคคลอื่น หรือระบุชัดว่ายังรอการตรวจ
6. Development/Test protocol ถูกกำหนดก่อนเริ่มปรับ Rule-based และ Prompt รอบใหม่
7. ทุก Artifact มี Version หรือ Hash เพื่อป้องกันการเปลี่ยนหลังเห็นผล Test

## Sprint review questions

- เราอธิบายได้หรือไม่ว่าคำถามแต่ละประเภทใช้ตารางและคอลัมน์ใด
- เราอธิบายได้หรือไม่ว่าทำไมยอดขายกับยอดจ่ายออกจึงไม่เท่ากันเสมอ
- SQL อ้างอิงทุกข้อสามารถตรวจย้อนกลับถึงข้อมูลต้นทางได้หรือไม่
- มีเงื่อนไขใดที่ระบบอาจละทิ้งโดยไม่แจ้งผู้ใช้หรือไม่
- หากเปลี่ยน Data snapshot SQL ที่ถูกต้องยังคืนผลที่ถูกต้องหรือไม่
- มีข้อสรุปใดที่อ้างเกินข้อมูลสังเคราะห์หรือไม่

## Do not do during Sprint 1

- อย่าปรับกฎหรือ Prompt จากผลของ Held-out test
- อย่าเพิ่ม Local/Enterprise model จนกว่าขอบเขตและ Ground Truth จะนิ่ง
- อย่ารายงาน preliminary 6/10 และ 10/10 เป็นผลสรุปของโครงการ
- อย่าเก็บ API key ในไฟล์ส่งมอบหรือหน้าจอนำเสนอ
