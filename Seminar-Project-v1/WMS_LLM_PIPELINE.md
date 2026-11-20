# WMS LLM Pipeline (Development Draft)

สถานะ: Provider integration, prompt, guard และ database execution พร้อมแล้ว แต่ live verification ล่าสุดรอ API key ที่ผ่าน authentication; ผลจาก Development questions **ยังไม่ใช่ Held-out evaluation**

## Pipeline

1. `app.wms_llm.prompt.wms_prompt_bundle` ส่ง Schema 10 ตาราง, Scope, Business definitions และ Result contract พร้อมคำถามทุกครั้ง
2. `app.llm.client.generate` เรียก KKU IntelSphere แบบ OpenAI-compatible และเก็บ latency/token metadata โดยไม่เปิดเผย API key
3. `app.llm.pipeline.decode_reply` บังคับ JSON contract: `ok + sql` หรือ `unsupported + sql=null`
4. `app.wms_llm.sql_guard.check_wms_sql` parse เป็น PostgreSQL AST แล้วตรวจ SELECT-only, allowlist ตาราง/คอลัมน์/function และ row cap
5. `execute_wms_checked` ใช้ `EXPLAIN` ก่อน execute ภายใน read-only transaction, restricted search path และ timeout

ไม่มี Rule-based fallback ในฝั่ง LLM เพื่อให้เปรียบเทียบสองแนวทางได้จริง

## API

- `POST /wms/llm/prompt` — ดู prompt โดยไม่เรียกโมเดล
- `POST /wms/llm/query` — เรียก IntelSphere หนึ่งครั้งแล้วตรวจ/รัน SQL
- `POST /wms/llm/check` — ตรวจ model output ที่มีอยู่แล้ว ไม่อ้างว่าเป็น live measurement
- `POST /wms/compare` — รัน Rule-based และ LLM บน database snapshot เดียวกัน

ค่า `same_rows_as_rule` บอกเพียงว่าทั้งสองวิธีให้ผลตรงกัน ไม่ได้พิสูจน์ว่าถูก ต้องเทียบแต่ละวิธีกับ Reference SQL

## สิ่งที่ Prompt ส่งและไม่ส่ง

ส่งทุกคำถาม:

- DDL ของ 10 ตาราง WMS MVP
- 5 Query families และรายการ out-of-scope
- Business definitions ที่ใช้ร่วมกับ Rule-based
- รูปแบบคอลัมน์และลำดับผลลัพธ์
- คำถามของผู้ใช้

ไม่ส่ง:

- Synthetic seed rows
- Reference SQL หรือ expected answers
- ผลของ Rule-based
- API key
- ประวัติคำถามก่อนหน้า

## หลักฐานอัตโนมัติ

`tests/test_wms_llm_pipeline.py` ตรวจ SQL ตัวแทนครบ 5 families เทียบ Reference results, JSON contract, prompt leakage, metadata และ SQL Guard ส่วน `tests/test_wms_demo_api.py` ตรวจ API ด้วย disposable schema จริง

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_wms_llm_pipeline.py tests/test_wms_demo_api.py -q
```

## ข้อจำกัดก่อน Evaluation

- Prompt และ Candidate Development questions ยังรอ Independent review
- Live provider check วันที่ 2026-11-20 ได้ HTTP 401 จึงไม่เกิด model output, token usage หรือ SQL execution; ต้องอัปเดต key ใน `.env.llm` แล้วตรวจซ้ำ
- การเรียกจริงหนึ่งครั้งเป็นเพียง integration check ไม่ใช่ accuracy result
- ต้อง Freeze prompt/rules ก่อนสร้าง Held-out set
- ต้องรัน LLM ซ้ำตาม protocol เพื่อวัด consistency ไม่เลือกเฉพาะรอบที่ตอบถูก
