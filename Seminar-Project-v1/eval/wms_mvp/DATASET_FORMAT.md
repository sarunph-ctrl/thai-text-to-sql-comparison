# Dataset Format — WMS MVP

Dataset เก็บเป็น YAML และต้องมี Metadata ระดับไฟล์กับรายการ `cases`

## Metadata ระดับไฟล์

| Field | ความหมาย |
|---|---|
| `dataset_version` | Version ของ Dataset |
| `split` | `development` หรือ `heldout` |
| `status` | `draft`, `frozen` หรือ `empty_template` |
| `scope_version` | Version ของ Scope |
| `ground_truth_version` | Version ของ Ground Truth |
| `snapshot_ids` | Snapshot ที่ Dataset ใช้ |
| `allowed_scope_labels` | `in_scope`, `out_of_scope` |
| `cases` | รายการคำถาม |

## Field ต่อ Case

| Field | Required | ความหมาย |
|---|---:|---|
| `id` | ใช่ | ID ไม่ซ้ำและมี Prefix ของ Split |
| `question` | ใช่ | คำถามภาษาไทยที่ส่งเข้าระบบ |
| `scope_label` | ใช่ | `in_scope` หรือ `out_of_scope` |
| `family` | In-scope | หนึ่งใน 5 Query families |
| `reference_id` | In-scope | ID ของ Reference SQL/Expected result |
| `expected_status` | ใช่ | `ok` หรือ `unsupported` |
| `ordered` | In-scope | ลำดับแถวเป็นส่วนหนึ่งของคำตอบหรือไม่ |
| `difficulty` | ใช่ | `basic`, `paraphrase`, `compositional`, `boundary` |
| `linguistic_features` | ใช่ | ป้ายรูปแบบภาษา เช่น synonym, polite, reordered |
| `out_of_scope_reason` | Out-of-scope | เหตุผลที่ต้องปฏิเสธ |
| `notes` | ไม่ | ข้อมูลสำหรับ Reviewer; ห้ามใส่ผลของระบบ |

## ตัวอย่าง In-scope

```yaml
- id: dev_wms_001
  question: "ขอสรุปจำนวนของแต่ละ Part แยกตามสถานะหน่อยครับ"
  scope_label: in_scope
  family: current_stock_summary
  reference_id: wms_ref_01
  expected_status: ok
  ordered: false
  difficulty: paraphrase
  linguistic_features: [polite, synonym]
  out_of_scope_reason: null
  notes: null
```

## ตัวอย่าง Out-of-scope

```yaml
- id: dev_wms_oos_001
  question: "เมื่อสิ้นเดือนที่แล้ว PART-A คงเหลือเท่าไร"
  scope_label: out_of_scope
  family: null
  reference_id: null
  expected_status: unsupported
  ordered: false
  difficulty: boundary
  linguistic_features: [historical_time]
  out_of_scope_reason: historical_stock_not_supported
  notes: null
```

ตัวอย่างมีไว้สอน Format เท่านั้น ไม่ถูกนับใน Dataset และไม่ควรคัดลอกประโยคเดิมไป Held-out
