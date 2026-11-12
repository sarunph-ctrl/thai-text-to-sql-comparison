# Metric Engine Input Fields

`app/evaluation_metrics.py` รับรายการ Raw case-runs และสรุปตาม `EVALUATION_PROTOCOL.md` โดยไม่เรียกโมเดลหรือฐานข้อมูล

| Field | Type | ความหมาย |
|---|---|---|
| `case_id` | string | ID ของ Case; จำเป็นสำหรับ Consistency |
| `scope_label` | `in_scope` / `out_of_scope` | ตัวหารของ Metric หลัก |
| `status` | string | `ok`, `unsupported`, `error` เป็นต้น |
| `execution_correct` | boolean | ผลตรง Reference หรือไม่ |
| `sql_valid` | boolean/null | SQL ผ่าน Guard และรันได้หรือไม่ |
| `sql_executed` | boolean | มีการส่ง SQL ไปฐานข้อมูลหรือไม่ |
| `method_ms` | number/null | เวลารวมของ Method ตาม Protocol |
| `input_tokens` | integer/null | Input tokens ที่ Provider รายงาน |
| `output_tokens` | integer/null | Output tokens ที่ Provider รายงาน |
| `timed_out` | boolean | หมดเวลาหรือไม่ |
| `truncated` | boolean | ผลถูกตัดด้วย Row limit หรือไม่ |
| `error_category` | string/null | Primary error category |
| `result_fingerprint` | string/null | Hash/ตัวแทนของ Normalized result สำหรับ Repeat agreement |

ค่า Token ที่ไม่ทราบต้องเป็น `null` ไม่ใช่ 0 และ Fingerprint ต้องสร้างจากผลลัพธ์/สถานะที่ Normalize แล้ว ไม่ใช้ข้อความ SQL เพราะ SQL ต่างรูปอาจให้ผลเดียวกัน

ฟังก์ชันหลัก:

- `summarize_runs()` — Correctness, rejection, valid SQL, latency, token, safety และ errors
- `summarize_consistency()` — Correctness/Agreement ของ LLM repeated runs
- `wilson_interval()` — 95% Wilson interval
- `nearest_rank_percentile()` — p95 แบบ Nearest-rank ที่ทำซ้ำได้
