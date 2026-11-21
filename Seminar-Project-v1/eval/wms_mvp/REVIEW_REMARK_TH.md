# Remark: Independent Review ต้องทำอย่างไร

## สิ่งที่คุณต้องทำ

วิธีง่ายที่สุดคือสร้าง ZIP ที่จัดไฟล์และแบบฟอร์มไว้แล้ว:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_wms_review_packet
```

ส่งไฟล์ `output/wms-review/WMS-MVP-Independent-Review-1.0-draft.zip` ให้ Reviewer โดยไม่ส่ง `WMS_DEVELOPMENT_RESULTS.md` หรือหน้าผลระบบไปด้วย ภายใน ZIP มี `START_HERE.md`, แบบฟอร์ม Core review และแบบฟอร์มตรวจคำถาม Development 35 ข้อ

1. เลือก Reviewer อย่างน้อย 1 คนที่อ่าน SQL ได้และไม่ได้เป็นคนปรับ Rule-based/Prompt ชุดนี้ เช่น อาจารย์ ผู้ช่วยสอน เพื่อนที่เข้าใจฐานข้อมูล หรือผู้รู้กระบวนการคลัง
2. ส่งไฟล์ต่อไปนี้ให้ Reviewer:
   - `INDEPENDENT_REVIEW_GUIDE.md`
   - `review_record.yaml`
   - `SCOPE_WMS_MVP.md`
   - `WMS_DATA_DICTIONARY.md`
   - `WMS_BUSINESS_RULES.md`
   - `db/wms_mvp_schema.sql`
   - `db/wms_mvp_seed.sql`
   - `eval/wms_mvp/ground_truth.yaml`
3. ก่อนตรวจ **อย่าแสดง** Accuracy, SQL ที่ Rule-based/LLM สร้าง หรือข้อที่ระบบตอบผิด
4. ให้ Reviewer กรอกชื่อ/บทบาท/วันที่ และยืนยันสองข้อใน `review_record.yaml`:
   - เป็นอิสระจากการปรับ Rule/Prompt
   - ตรวจโดยยังไม่เห็นผลระบบ
5. ให้ตรวจ Open business decisions ทั้ง 6 ข้อ และ Ground Truth `wms_ref_01`–`wms_ref_05` ทีละข้อ
6. ให้เลือกผลรวม: `approved`, `approved_with_changes`, `changes_required` หรือ `rejected`
7. ส่งไฟล์ `review_record.yaml` ที่กรอกแล้วกลับมา แล้วจึงแก้ Version/Manifest หรือ Freeze Ground Truth ตามผลตรวจ

สำหรับคำถาม Development ให้ส่ง `candidate_review_record.yaml` ที่กรอกแล้วกลับมาด้วย

## เมื่อได้รับไฟล์กลับมา

แตก ZIP หรือบันทึกไฟล์ที่ Reviewer กรอกแล้ว จากนั้นตรวจ Gate โดยคำสั่ง:

```powershell
.\.venv\Scripts\python.exe eval\validate_wms_review.py `
  --core path\to\review_record.yaml `
  --candidate path\to\candidate_review_record.yaml
```

ผล `gate_passed: true` หมายถึงหลักฐานครบตามเงื่อนไขเชิงกลและพร้อมเข้าสู่ขั้น Freeze เท่านั้น เครื่องมือจะไม่แก้ Artifact, เปลี่ยน Version หรือสร้าง Held-out ให้อัตโนมัติ หากได้ Exit code 2 ให้อ่านรายการ `issues` และส่งกลับให้ Reviewer/ผู้พัฒนาแก้ตามความเป็นจริง ห้ามกรอกแทน Reviewer เพื่อให้ Gate ผ่าน

## สิ่งที่ไม่ควรทำ

- อย่ากรอก Review แทน Reviewer
- อย่าเปลี่ยน `pending` เป็น `approved` เพียงเพราะ Automated tests ผ่าน
- อย่าแก้เฉลยให้ตรงกับผลของระบบโดยไม่มีเหตุผลจาก Schema/Business rule
- อย่าเริ่มใช้ Held-out outcomes ปรับระบบก่อน Freeze

Automated tests ยืนยันเพียงว่าไฟล์สอดคล้องและ SQL รันได้ ส่วน Reviewer เป็นผู้ยืนยันว่าความหมายของธุรกิจและเฉลยเหมาะสม
