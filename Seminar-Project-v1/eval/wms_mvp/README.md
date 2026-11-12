# WMS MVP Ground Truth

`ground_truth.yaml` เก็บคำถามอ้างอิง 5 ข้อ หนึ่งข้อหลักต่อหนึ่ง Query family พร้อม Business rule IDs, Parameterized SQL, Expected columns/types/rows และกติกาเรื่องลำดับ

`manifest.json` เก็บ SHA-256 หลัง Normalize line ending เป็น LF ของ Schema, Seed, Business rules และ Ground Truth ที่ต้องใช้ร่วมกัน หาก Hash ไม่ตรงต้องถือว่าเป็น Snapshot คนละรุ่น วิธีนี้ทำให้ตรวจ Hash เดียวกันได้ทั้ง Windows และระบบที่ใช้ LF

## สถานะ

- เป็น `1.0-draft`
- รันตรวจอัตโนมัติกับ `db/wms_mvp_schema.sql` และ `db/wms_mvp_seed.sql`
- ยังรอ Independent review
- ยังไม่ใช่ Development set หรือ Held-out test set
- ห้ามใช้ผลจากไฟล์นี้อ้าง Accuracy ของ Rule-based หรือ LLM

## หลักการ

- SQL ใช้ Named parameters ของ Psycopg เช่น `%(status)s`
- วันที่ใช้ช่วงครึ่งเปิด `[start_date, end_date)`
- `ordered: true` เฉพาะกรณีที่ลำดับเป็นส่วนหนึ่งของคำตอบ
- เมื่อ `ordered: false` ยังเก็บแถวเรียงแบบคงที่เพื่อให้คนตรวจอ่านง่าย แต่การประเมินต้องไม่ตัดสินจากลำดับ
- Expected rows ต้องมาจากการรัน SQL อ้างอิงบน Snapshot เดียวกัน ไม่คัดลอกจากผล Rule-based หรือ LLM

## ขั้นตอนตรวจ

1. Reset ฐานทดสอบด้วย Schema และ Seed ที่ระบุในไฟล์
2. รัน `pytest tests/test_wms_ground_truth.py -q`
3. ตรวจว่า Hash ใน `manifest.json` ผ่าน
4. ให้ผู้ตรวจอ่านคำถาม Business rules และ SQL โดยไม่ดูผลระบบ
5. บันทึกผู้ตรวจ วันที่ และข้อแก้ไขก่อนเปลี่ยนสถานะจาก Draft
6. หากแก้ Schema, Seed, Rule หรือ SQL ให้เพิ่ม Version, สร้าง Manifest ใหม่ และรันใหม่
