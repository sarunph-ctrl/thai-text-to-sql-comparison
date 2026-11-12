# Remark: Independent Review ต้องทำอย่างไร

## สิ่งที่คุณต้องทำ

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

## สิ่งที่ไม่ควรทำ

- อย่ากรอก Review แทน Reviewer
- อย่าเปลี่ยน `pending` เป็น `approved` เพียงเพราะ Automated tests ผ่าน
- อย่าแก้เฉลยให้ตรงกับผลของระบบโดยไม่มีเหตุผลจาก Schema/Business rule
- อย่าเริ่มใช้ Held-out outcomes ปรับระบบก่อน Freeze

Automated tests ยืนยันเพียงว่าไฟล์สอดคล้องและ SQL รันได้ ส่วน Reviewer เป็นผู้ยืนยันว่าความหมายของธุรกิจและเฉลยเหมาะสม
