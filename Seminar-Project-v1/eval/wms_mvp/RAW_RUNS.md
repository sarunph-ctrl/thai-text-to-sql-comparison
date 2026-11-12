# Raw-run Recording and Summary

Raw runs ใช้ JSONL: หนึ่งบรรทัดต่อหนึ่ง Method × Case × Repeat × Snapshot

## หลักความปลอดภัย

- ไม่เก็บข้อความคำถามใน Raw record; ใช้ `case_id` เชื่อมกับ Dataset
- Reject ชื่อ Field ที่อาจเก็บ API key, Password หรือ Authorization
- Reject ค่า String ที่มีรูปแบบ Bearer token หรือ `sk_...`
- Raw directory ถูก Git ignore ที่ `output/wms_mvp/raw/`
- ค่า Token ไม่ทราบต้องเป็น `null`
- ทุก Record มี Result fingerprint จาก Status, Columns และ Normalized rows ไม่ใช้ SQL text

## บันทึก Record จาก Python

```python
from pathlib import Path
from app.evaluation_records import append_jsonl

append_jsonl(Path("output/wms_mvp/raw/run.jsonl"), record)
```

`append_jsonl()` จะ Validate, เติม `run_id`, เวลา UTC, Version และ Result fingerprint ก่อน Append

## สรุปผล

```powershell
.\.venv\Scripts\python.exe eval\wms_mvp\summarize_raw_runs.py `
  --input output\wms_mvp\raw\run.jsonl `
  --output output\wms_mvp\summary.json
```

CLI ไม่อ่านคำถามหรือ Dataset และไม่เรียก API/Database ใช้เฉพาะ Raw records กับ Metric engine ที่ตรึงไว้ หาก Output มีอยู่แล้วต้องเลือกชื่อใหม่หรือใส่ `--force`
