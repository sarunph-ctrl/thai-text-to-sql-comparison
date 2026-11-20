# WMS MVP — Development Run Results

**Run date:** 2026-11-20

**Code commit:** `947b62a52c9aca4220427109a53ca95fd9387197`

**Dataset:** `dev.candidate.yaml` (`draft_before_independent_review`)

**Review status:** Pending independent review

ผลหน้านี้เป็นการตรวจว่า Rule-based implementation ทำงานตรงกับ Candidate Development set ที่ใช้พัฒนาระบบ ไม่ใช่ Held-out accuracy และห้ามนำไปสรุปว่าใช้กับ WMS จริงหรือภาษาไทยทั่วไปได้แม่นยำ 100%

## Rule-based results

| Snapshot | In-scope Execution Accuracy | Out-of-scope Rejection | Valid SQL | Median | p95 | Unsafe acceptance |
|---|---:|---:|---:|---:|---:|---:|
| `wms_seed_v1` | 25/25 | 10/10 | 25/25 | 4.103 ms | 7.024 ms | 0 |
| `wms_seed_v2` | 25/25 | 10/10 | 25/25 | 4.295 ms | 7.925 ms | 0 |

ช่วงความเชื่อมั่น Wilson 95% ของ In-scope 25/25 คือประมาณ 86.68%–100% และของ Out-of-scope 10/10 คือประมาณ 72.25%–100% ช่วงยังค่อนข้างกว้างเพราะจำนวนคำถามน้อย

## Reproducibility evidence

- Manifest SHA-256 ผ่านก่อนเริ่มรัน
- ใช้ Shuffle seed `20261120` เหมือนกันทั้งสอง snapshots
- สร้าง Disposable PostgreSQL schema ใหม่ต่อ snapshot
- Expected results มาจากการรัน Reference SQL บน snapshot เดียวกัน
- Raw JSONL มี 35 records ต่อ snapshot และทุก record อ้าง commit เดียวกัน
- Raw records ไม่เก็บข้อความคำถามหรือ API key
- ไม่มี timeout, truncated result หรือ unsafe acceptance

Experiment IDs:

- `wms-mvp-development-wms_seed_v1-20261120-113728`
- `wms-mvp-development-wms_seed_v2-20261120-113730`

Raw files อยู่ใน `output/wms_mvp/raw/` และถูก Git ignore ตามนโยบาย secret-resistant recording

## LLM status

ยังไม่มีผล LLM Development run ที่สมบูรณ์ การตรวจ Live integration ล่าสุดได้ IntelSphere HTTP 401 ก่อนมี model output จึงไม่เกิด token usage หรือ SQL execution และไม่ได้ยิงซ้ำครบ Dataset

## สิ่งที่ผลนี้บอกได้

- Rule parser/builder ครอบคลุม Candidate Development 25 ข้อที่ใช้ปรับระบบ
- Out-of-scope rules ปฏิเสธ Candidate 10 ข้อโดยไม่รัน SQL
- SQL รูปเดียวกันยังให้คำตอบถูกเมื่อเปลี่ยนข้อมูลจาก v1 เป็น v2 จึงไม่ได้ hard-code ค่า expected answer ของ v1
- Evaluation harness บันทึกผลและคำนวณ metric ตาม protocol ได้จริง

## สิ่งที่ผลนี้ยังบอกไม่ได้

- ไม่ได้พิสูจน์ performance บน Held-out questions
- ไม่ได้พิสูจน์ว่า Candidate questions เป็นตัวแทนคำถามผู้ใช้ WMS จริง
- ยังเปรียบเทียบ Rule-based กับ LLM ไม่ได้จนกว่า API authentication ใช้งานได้
- Business rules, Ground Truth และคำถามยังต้องผ่าน Independent review
- Schema และข้อมูลเป็น synthetic domain-specific MVP ไม่ใช่ WMS เต็มระบบ
