# Independent Review Guide — WMS MVP

## วัตถุประสงค์

ให้บุคคลที่ไม่ได้ปรับ Rule-based หรือ Prompt ตรวจว่า Scope, Schema, Business rules, Reference SQL และ Expected results สมเหตุสมผลก่อนนำไปสร้าง Development/Test set

การมี Test ผ่านหมายถึงไฟล์สอดคล้องกันทางเทคนิค แต่ไม่ยืนยันว่าความหมายธุรกิจถูกต้อง Independent review จึงยังจำเป็น

## ผู้ที่เหมาะเป็น Reviewer

Reviewer ควร:

- อ่าน SQL ที่มี JOIN, GROUP BY, CTE และ Aggregate ได้
- เข้าใจหลักการรับเข้า จัดเก็บ และจ่ายออกสินค้าอย่างน้อยระดับพื้นฐาน
- ไม่ได้ใช้ผลของ Rule-based/LLM ชุดนี้ในการสร้างหรือแก้เฉลย
- กล้าระบุว่า “ไม่ทราบ” เมื่อกฎต้องใช้ความรู้จากเจ้าของกระบวนการ

ตัวอย่างผู้ตรวจ: อาจารย์ ผู้ช่วยสอน เพื่อนที่เข้าใจ SQL แต่ไม่ได้พัฒนาระบบส่วนนี้ หรือผู้มีประสบการณ์คลังสินค้า หากคนเดียวไม่ครอบคลุมทั้ง SQL และโดเมน ให้แยก Technical reviewer กับ Domain reviewer

## สิ่งที่ห้ามแสดงก่อนตรวจเสร็จ

- Accuracy ของ Rule-based หรือ LLM
- SQL ที่ Rule-based/LLM สร้าง
- ข้อที่แต่ละวิธีตอบผิด
- การเปรียบเทียบเวลา Token หรือต้นทุนรายข้อ

เหตุผลคือข้อมูลเหล่านี้อาจทำให้ Reviewer ปรับเฉลยให้เข้ากับผลของระบบโดยไม่ตั้งใจ

## Artifact ที่ต้องตรวจ

ตรวจ Hash ด้วย `manifest.json` ก่อนเริ่ม:

1. `SCOPE_WMS_MVP.md`
2. `db/wms_mvp_schema.sql`
3. `db/wms_mvp_seed.sql`
4. `WMS_DATA_DICTIONARY.md`
5. `WMS_BUSINESS_RULES.md`
6. `eval/wms_mvp/ground_truth.yaml`

บันทึกผลลง `review_record.yaml` ห้ามแก้ Ground Truth โดยไม่เก็บข้อเสนอแนะเดิม

## ขั้นตอนตรวจ

### 1. Scope review

- 10 ตาราง MVP เพียงพอสำหรับ 5 Query families หรือไม่
- Out-of-scope ชัดเจนและไม่สื่อว่าเป็น WMS เต็มระบบหรือไม่
- ไม่มีคำถามที่ต้องใช้ Customer, Shipment, User หรือ Movement history แอบอยู่ใน Phase 1 หรือไม่

### 2. Schema review

- Grain ของทุกตารางชัดเจนหรือไม่
- PK/FK/UNIQUE/CHECK สอดคล้องกับความหมายหรือไม่
- Nullability ทำให้คำถามใดกำกวมหรือไม่
- การตัด Phase-2 dependencies ทำให้ความหมาย Core เปลี่ยนหรือไม่

### 3. Business-rule review

- “พร้อมใช้” = `Available` + `Good` เหมาะสมหรือไม่
- วิธีนับรับจริงและหยิบจริงด้วย Serial ไม่ซ้ำถูกต้องหรือไม่
- ฐานวันที่ของ Inbound/Outbound ถูกต้องหรือไม่
- `Received` และ `Completed` ต่างกันอย่างไร
- Serial เดียวควรปรากฏในหลาย Order ได้หรือไม่
- การรับ/หยิบเกินแผนควรแสดงเป็น Exception หรือถูกห้าม

### 4. Ground-truth review

ตรวจทีละ Case โดยไม่ดูผลระบบ:

1. คำถามมีคำตอบเดียวภายใต้ Business rules หรือไม่
2. Rule IDs ที่อ้างครอบคลุมความหมายของคำถามหรือไม่
3. SQL ใช้ตาราง, JOIN, Filter, Grouping และ Date boundary ถูกหรือไม่
4. Parameter ไม่ถูกฝังเป็น String ใน SQL หรือไม่
5. Expected columns และชนิดข้อมูลเหมาะกับคำถามหรือไม่
6. Expected rows ตรวจย้อนกลับถึง Seed ได้หรือไม่
7. ค่า `ordered` สอดคล้องกับความหมายของคำถามหรือไม่

### 5. Mechanical verification

รัน:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_wms_schema.py tests\test_wms_ground_truth.py -q -p no:cacheprovider
```

Test ต้องผ่าน แต่ผลผ่านไม่สามารถแทนการอนุมัติด้านความหมายได้

## ผลการ Review ที่เลือกได้

- `approved`: ไม่มีการแก้ที่มีผลต่อความหมาย
- `approved_with_changes`: มีข้อแก้เล็กน้อยและตรวจไฟล์รุ่นแก้แล้ว
- `changes_required`: ต้องแก้กฎ/Schema/SQL/Expected result ก่อนใช้
- `rejected`: Scope หรือวิธีสร้าง Ground Truth ไม่เหมาะกับวัตถุประสงค์

## หลังได้รับ Feedback

1. เก็บ `review_record.yaml` ที่กรอกแล้ว
2. แก้ Artifact โดยอ้าง Case/Rule ที่ได้รับ Feedback
3. เพิ่ม Version หากความหมายหรือ Expected result เปลี่ยน
4. สร้าง Manifest hash ใหม่
5. รัน Test ใหม่ทั้งหมด
6. ให้ Reviewer ตรวจ Version ที่แก้ก่อนเปลี่ยน `review_status`

ห้ามสร้าง Held-out test set ขั้นสุดท้ายจาก Ground Truth ที่ยังมีสถานะ `pending_independent_review`
