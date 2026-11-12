# Thai Text-to-SQL Comparison

A comparative study of rule-based and large language model approaches for Thai Text-to-SQL in warehouse operations.

โครงการนี้ศึกษาการแปลงคำถามภาษาไทยเป็นคำสั่ง SQL โดยเปรียบเทียบสองแนวทางภายใต้คำถาม Schema ฐานข้อมูล และ SQL อ้างอิงชุดเดียวกัน:

- **Rule-based:** ทำความสะอาดข้อความ ตัดคำด้วย PyThaiNLP/NewMM จับ Intent ด้วยพจนานุกรมและ Regular Expression แล้วประกอบ SQL ด้วย SQL Builder
- **LLM:** ส่งคำถาม Schema และนิยามธุรกิจให้โมเดลสร้าง SQL จากนั้นตรวจ AST และข้อจำกัดก่อนรัน

โครงการเป็น **Domain-specific prototype** สำหรับ Warehouse Operations โดยต่อยอดโครงสร้างฐานข้อมูลจากโปรเจกต์ `Succeed_BDMS` และใช้ข้อมูลสังเคราะห์ในการทดลอง ไม่ใช่ WMS เต็มระบบและไม่ใช้แทนผลจากระบบขององค์กรจริง

## Research question

ภายใต้ขอบเขตข้อมูลคลังสินค้า รับเข้า และจ่ายออก แนวทาง Rule-based และ LLM แตกต่างกันอย่างไรในด้าน Execution Accuracy การรองรับรูปแบบภาษาไทย เวลา Token ความสม่ำเสมอ และประเภทข้อผิดพลาด

## Scope

MVP กำหนดคำถามหลัก 5 รูปแบบ:

1. จำนวนสต็อกปัจจุบัน แยกตาม Part, Location, Status หรือ Condition
2. รายละเอียด Serial Number และตำแหน่งปัจจุบัน
3. จำนวนที่วางแผนรับเข้าเทียบกับรับจริง
4. จำนวนที่วางแผนจ่ายออกเทียบกับหยิบจริง
5. จำนวนหรือรายการ Inbound/Outbound Order ตามสถานะและช่วงวันที่

ข้อกำหนดหลัก:

- สร้างเฉพาะคำสั่ง `SELECT`
- รับคำถามครั้งละหนึ่งคำถาม
- ใช้ข้อมูลสังเคราะห์และ Schema MVP 10 ตาราง
- คำถามนอกขอบเขตต้องถูกปฏิเสธโดยไม่ละทิ้งเงื่อนไขของผู้ใช้

สิ่งที่ยังไม่รองรับ ได้แก่ ยอดขาย/ราคา Customer analytics, Shipment/Provider/Driver analytics, User performance, สต็อกย้อนหลัง การโอน/คืน/จองสินค้า Lot และวันหมดอายุ รายละเอียดอยู่ใน [`Seminar-Project-v1/SCOPE_WMS_MVP.md`](Seminar-Project-v1/SCOPE_WMS_MVP.md)

## Data model

| Table | Purpose |
|---|---|
| `part_master`, `part_obj` | ชนิดสินค้าและสินค้าแต่ละ Serial |
| `location`, `current_stock` | ตำแหน่งและสถานะสต็อกปัจจุบัน |
| `inbound_order`, `inbound_plan`, `inbound_detail` | แผนและผลการรับเข้า |
| `outbound_order`, `outbound_plan`, `outbound_detail` | แผนและผลการจ่ายออก |

Schema เป้าหมายกำลังอยู่ระหว่างจัด DDL, Data Dictionary และ Business rules ให้ทำซ้ำได้ โค้ดเดโม 5 ตารางเดิมยังคงอยู่เป็น Legacy baseline จนกว่า Migration จะเสร็จ และยังไม่ควรอ้างว่าโค้ดปัจจุบันรองรับ WMS MVP แล้ว

## Architecture

```mermaid
flowchart LR
    Q[Thai question] --> R[Rule-based]
    Q --> L[LLM prompt]
    R --> N[Normalize and NewMM]
    N --> I[Dictionary, Regex and Intent]
    I --> B[SQL Builder]
    L --> M[LLM generates SQL]
    M --> G[SQLGlot AST guard]
    B --> D[(PostgreSQL read-only)]
    G --> D
    D --> E[Result and evaluation]
```

ฝั่ง LLM ใช้ SQLGlot ตรวจว่าเป็น `SELECT` เพียงคำสั่งเดียว ใช้เฉพาะตาราง คอลัมน์ และฟังก์ชันที่อนุญาต ก่อนให้ PostgreSQL ตรวจด้วย `EXPLAIN` และรันใน Read-only transaction พร้อม timeout และ row limit

## Evaluation

ตัวชี้วัดหลักคือ **Execution Accuracy** โดยรัน SQL ของระบบและ SQL อ้างอิงกับ Database snapshot เดียวกัน แล้วเปรียบเทียบผลครบทุกแถวและทุกคอลัมน์ รวมแถวซ้ำ และตรวจลำดับสำหรับ Top-N

ตัวชี้วัดประกอบ:

- Valid SQL / Execution success rate
- ความถูกต้องในการปฏิเสธคำถามนอกขอบเขต
- Median และ p95 latency
- Input/output tokens และต้นทุนเมื่อมีอัตราค่าบริการ
- Consistency จากการรัน LLM ซ้ำ
- Error analysis แยกตามประเภทข้อผิดพลาด

ผลทดลองเดิม 10 ข้อเป็นเพียง **preliminary synthetic evaluation** ไม่ใช่ Benchmark มาตรฐานหรือผลสรุปของโครงการ ดูรายละเอียดที่ [`Seminar-Project-v1/SPRINT2.md`](Seminar-Project-v1/SPRINT2.md)

## Project status

โครงการอยู่ใน **Sprint 1: Scope, Schema, and Ground Truth** โดยกำลังตรึงขอบเขต ตรวจ Schema นิยามธุรกิจ Reference SQL และออกแบบ Development/Test protocol

- Current scope: [`Seminar-Project-v1/SCOPE_WMS_MVP.md`](Seminar-Project-v1/SCOPE_WMS_MVP.md)
- Sprint plan: [`Seminar-Project-v1/SPRINT1_PROJECT.md`](Seminar-Project-v1/SPRINT1_PROJECT.md)
- WMS MVP schema: [`Seminar-Project-v1/db/wms_mvp_schema.sql`](Seminar-Project-v1/db/wms_mvp_schema.sql)
- WMS synthetic seed: [`Seminar-Project-v1/db/wms_mvp_seed.sql`](Seminar-Project-v1/db/wms_mvp_seed.sql)
- WMS robustness seed v2: [`Seminar-Project-v1/db/wms_mvp_seed_v2.sql`](Seminar-Project-v1/db/wms_mvp_seed_v2.sql)
- WMS data dictionary: [`Seminar-Project-v1/WMS_DATA_DICTIONARY.md`](Seminar-Project-v1/WMS_DATA_DICTIONARY.md)
- WMS business rules: [`Seminar-Project-v1/WMS_BUSINESS_RULES.md`](Seminar-Project-v1/WMS_BUSINESS_RULES.md)
- WMS ground truth: [`Seminar-Project-v1/eval/wms_mvp/ground_truth.yaml`](Seminar-Project-v1/eval/wms_mvp/ground_truth.yaml)
- Independent review guide: [`Seminar-Project-v1/eval/wms_mvp/INDEPENDENT_REVIEW_GUIDE.md`](Seminar-Project-v1/eval/wms_mvp/INDEPENDENT_REVIEW_GUIDE.md)
- Evaluation protocol: [`Seminar-Project-v1/eval/wms_mvp/EVALUATION_PROTOCOL.md`](Seminar-Project-v1/eval/wms_mvp/EVALUATION_PROTOCOL.md)
- Metric input fields: [`Seminar-Project-v1/eval/wms_mvp/METRIC_FIELDS.md`](Seminar-Project-v1/eval/wms_mvp/METRIC_FIELDS.md)
- Legacy data dictionary: [`Seminar-Project-v1/DATA_DICTIONARY.md`](Seminar-Project-v1/DATA_DICTIONARY.md)
- Legacy business rules: [`Seminar-Project-v1/BUSINESS_RULES.md`](Seminar-Project-v1/BUSINESS_RULES.md)
- Schema guide: [`Seminar-Project-v1/SCHEMA_GUIDE.md`](Seminar-Project-v1/SCHEMA_GUIDE.md)
- Presentation runbook: [`Seminar-Project-v1/PRESENTATION_RUNBOOK.md`](Seminar-Project-v1/PRESENTATION_RUNBOOK.md)

## Quick start on Windows

Prerequisites:

- Python 3.12+
- PostgreSQL installed locally
- IntelSphere API key สำหรับโหมด LLM แบบรันสด

```powershell
cd Seminar-Project-v1

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt

Copy-Item .env.llm.example .env.llm
notepad .env.llm

powershell -ExecutionPolicy Bypass -File .\start-demo.ps1
```

เปิดหน้า Demo ที่ <http://127.0.0.1:8000/> และเปิด API documentation ที่ <http://127.0.0.1:8000/docs>

หยุดระบบด้วย `Ctrl+C` แล้วหยุดฐานข้อมูล Demo:

```powershell
.\.venv\Scripts\python.exe -m scripts.local_demo stop
```

ไฟล์ Offline demo อยู่ที่:

```text
Seminar-Project-v1/output/presentation/offline-demo.html
```

## Tests

```powershell
cd Seminar-Project-v1
.\.venv\Scripts\python.exe -m pytest -q
```

## Repository structure

```text
Seminar-Project-v1/
├── app/
│   ├── nlp/              Rule-based normalization and intent parsing
│   ├── sql/              Intent-to-SQL builders
│   └── llm/              Prompt, model client, SQL guard and execution
├── config/               Lexicon and business definitions
├── db/                   Schema, synthetic data and reference SQL
├── eval/                 Development/test sets and evaluation runner
├── tests/                Automated tests
├── web/                  Demo user interface
├── output/               Recorded preliminary results and offline demo
└── scripts/              Local database and utility scripts
```

## Configuration and secrets

คัดลอก `.env.llm.example` เป็น `.env.llm` แล้วใส่ API key ในเครื่องเท่านั้น ไฟล์ `.env.llm`, `.env`, `.local`, `.venv`, Log และ ZIP ถูกกันออกจาก Git ด้วย `.gitignore`

ห้าม Commit API key, รหัสผ่านฐานข้อมูล หรือข้อมูลลูกค้าจริงขึ้น Repository

## Current limitations

- Schema ข้อมูล คำถาม และ Ground Truth ปัจจุบันมี AI ช่วยสร้าง
- ยังไม่มีการตรวจสอบกับ WMS ขององค์กรจริง
- Preliminary test มีเพียง 10 คำถามและ Database snapshot เดียว
- LLM อาจให้ผลต่างกันเมื่อรันซ้ำ
- ยังไม่มีอัตราค่าบริการ IntelSphere สำหรับคำนวณต้นทุนเป็นเงินบาท
- การผ่าน SQL Guard ยืนยันว่าคำสั่งอยู่ในขอบเขตและรันได้ ไม่ได้ยืนยันว่าความหมายถูกต้อง

## License

No license has been selected. All rights are reserved until the project owners choose a license.
