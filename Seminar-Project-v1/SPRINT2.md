# Sprint 2 — Rule-based เทียบกับ IntelSphere

## สิ่งที่ทำเสร็จ

- คง schema ห้าตารางและกฎเดิม ไม่แก้กฎตามชุดประเมิน
- เชื่อม IntelSphere KKU แบบ OpenAI-compatible ตามหน้า API Platform ที่ผู้ใช้ให้
- ใช้ Model ID **gpt-5.6-luna ตามที่ผู้ใช้เลือก** และตรวจว่ามีใน `/models`
- Zero-shot prompt ส่งเฉพาะ schema, นิยามธุรกิจ, รูปแบบผลลัพธ์ และคำถาม
- ไม่ส่งข้อมูล seed, SQL อ้างอิง, คำตอบ หรือ SQL ที่ Rule-based สร้างให้โมเดล
- ตรวจ SQL ด้วย SQLGlot แบบ PostgreSQL ก่อน execute และใช้บัญชีอ่านอย่างเดียว
- เพิ่มการเปรียบเทียบผลทั้งตาราง รวมแถวซ้ำและลำดับของ Top-N
- มีคำถามพัฒนา 10 ข้อ กับชุดประเมินสังเคราะห์ 10 ข้อ แยกไฟล์
- ตรึง source, prompt, schema, ชุดคำถาม และการตั้งค่าโมเดลไว้ก่อนรันชุดประเมิน
- บันทึก SQL ที่โมเดลสร้าง/SQL ที่ execute, เวลา, Token และผลเทียบอ้างอิงรายข้อ

## ลองผ่าน Swagger

เปิด `http://127.0.0.1:8000/docs` รุ่น **0.3.0**

| Endpoint | ใช้ทำอะไร | เรียก LLM จริงไหม |
|---|---|---|
| POST /query | Rule-based เดิม | ไม่ |
| POST /llm/prompt | ดูข้อความที่ส่งให้ LLM และ hashes | ไม่ |
| GET /llm/status | ดู provider/model และสถานะการตั้งค่า โดยไม่แสดง key | ไม่ |
| POST /llm/query | ให้ IntelSphere สร้าง SQL ตรวจแล้วรันฐานข้อมูล | ใช่ หนึ่งครั้ง |
| POST /compare | รัน Rule-based และ LLM บน snapshot ฐานข้อมูลเดียวกัน | ใช่ หนึ่งครั้ง |
| POST /llm/check | ตรวจ JSON ที่นำมาวางเอง ระบุเป็น manual_output ไม่มี Token/เวลา API | ไม่ |

ตัวอย่างสำหรับ `/compare`:

```json
{"text": "เดือนกันยายน 2569 ขายของได้เงินรวมเท่าไร"}
```

ในชุดประเมิน รูปประโยคนี้ Rule-based ไม่จับเจตนา แต่ LLM ได้ 1250.00 บาท
ดู `rule_based`, `llm`, `generated_sql`, `executed_sql`, `rows`, `generation`
และ `same_rows_as_rule` ในผลตอบกลับ

**same_rows_as_rule ไม่ใช่คะแนนความถูกต้อง** หากสองระบบตอบผิดเหมือนกันก็ตรงกันได้
ถ้าฝั่งใดไม่ตอบสำเร็จ ค่านี้เป็น null; ต้องใช้การประเมินกับ SQL อ้างอิงเพื่อตัดสิน

## เส้นทางของฝั่ง LLM

```text
Thai question + five-table schema + business definitions
    -> fixed zero-shot messages
    -> IntelSphere /chat/completions (gpt-5.6-luna)
    -> JSON reply: ok + SQL หรือ unsupported
    -> PostgreSQL AST allowlist
    -> EXPLAIN และ SELECT ใน transaction READ ONLY
    -> rows + generation/validation/database time + usage
```

ไม่มีการให้ Rule-based ช่วยแปลคำถามให้ LLM ไม่มี fallback ไม่มี retry หรือซ่อม SQL
อัตโนมัติในการทดลองนี้ จึงเห็นข้อผิดพลาดของแต่ละเส้นทางตรงตามที่เกิดขึ้น
temperature = 0 แต่ไม่ถือว่าโมเดลรับประกันผลเหมือนเดิมทุกครั้ง

## Prompt ให้ข้อมูลอะไร

ดู `app/llm/prompt.py` หรือ POST `/llm/prompt`

- DDL จริงของห้าตาราง และ foreign keys
- ยอดขายนับ paid ตาม order_date และใช้ราคาขณะขาย
- คงเหลือ = opening + receipt - issue ทุกเหตุการณ์ แยกสินค้าและคลัง
- จ่ายออกรายเดือนอิง movement_date ไม่กรอง paid และรวมทุกคลัง
- งานห้ารูปแบบเดียวกับ baseline; นอกขอบเขตให้ปฏิเสธ
- เดือนต้องมีชื่อเดือนและปีสี่หลัก; พ.ศ. แปลงเป็น ค.ศ.
- รูปแบบและลำดับคอลัมน์ให้เปรียบเทียบได้ ไม่ส่ง query template เฉลย
- ให้ส่ง JSON สั้น ๆ พร้อม SQL ไม่ขอ chain-of-thought

`prompt_sha256` ผูกกับข้อความและคำถาม ส่วน `schema_sha256` ผูกกับ schema
ทำให้ตรวจย้อนกลับได้ว่ารอบนั้นใช้บริบทชุดใด

## SQL ที่สร้างต้องผ่านอะไร

1. Parse เป็น PostgreSQL ได้ และมี SELECT เดียว
2. ใช้เฉพาะห้าตาราง; CTE และ subquery แบบที่อนุญาตใช้ได้
3. ปฏิเสธ writes, SELECT INTO, locking, recursive CTE, system catalogs,
   table functions และฟังก์ชันนอก allowlist เช่น pg_sleep/pg_read_file
4. จำกัดจำนวนแถว อ่านจริงสูงสุด 201 เพื่อตรวจว่าเกิน 200 หรือไม่
5. ใช้ PostgreSQL role ที่มีเฉพาะ SELECT และ transaction READ ONLY
6. EXPLAIN ตรวจว่า SQL resolve ได้ แล้ว execute โดยมี timeout 3 วินาที

`generated_sql` คือของโมเดล ส่วน `executed_sql` คือ SQL จาก AST ที่อาจเพิ่ม/จำกัด LIMIT
ถ้าผลเกิน 200 แถว ระบุ truncated และไม่นับเป็นตอบถูก
นี่เป็น allowlist สำหรับเดโม ไม่ใช่ sandbox SQL อเนกประสงค์
การผ่าน guard หรือรันได้ไม่ยืนยันว่าความหมายตรงคำถาม

## ผลทดลองที่บันทึกจริง

### ชุดพัฒนา

`eval/sprint2/dev.yaml` มี 10 ข้อ ทดสอบ Rule-based ได้ **10/10**
มีหนึ่งตัวอย่าง live LLM สำหรับตรวจการเชื่อมต่อ เก็บแยกจากผลชุดประเมิน

### ชุดประเมินสังเคราะห์ 10 ข้อ

ใช้ `gpt-5.6-luna` ผ่าน IntelSphere หนึ่ง call ต่อข้อ โดยไม่มีการปรับ prompt/กฎ
ตามคำตอบในชุดนี้ระหว่างรัน

| ตัวชี้วัด | Rule-based | IntelSphere / gpt-5.6-luna |
|---|---:|---:|
| คำตอบตรง SQL อ้างอิง | 6/10 | 10/10 |
| SQL รันสำเร็จ | 6/10 | 10/10 |
| เวลาเฉลี่ยของวิธี | 6.382 ms | 3874.181 ms |
| เวลามัธยฐาน | 5.625 ms | 3589.264 ms |
| Canonical SQL exact match | 0/10 | 0/10 |
| Input tokens ที่บริการรายงาน | ไม่เรียก API | 12,314 |
| Output tokens ที่บริการรายงาน | ไม่เรียก API | 2,330 |

4 ข้อที่ Rule-based ไม่ผ่านเป็น **unmatched/unsupported** ไม่ใช่กรณีที่รันแล้วคืนค่าผิด
เวลาเฉลี่ยฝั่ง Rule-based รวมการปฏิเสธที่ใช้เวลาสั้น จึงควรดูสถานะและเวลารายข้อร่วมด้วย
เวลาวัดภายในวิธี ไม่รวมเปิด connection หรือ HTTP ของหน้าเดโม
LLM รวมสร้าง prompt, รอ generation, validation/EXPLAIN และ SELECT
ตัวเลขอาจเปลี่ยนในการรันครั้งต่อไปตามเครือข่ายและบริการ

**Canonical SQL exact match = 0 ไม่ได้แปลว่าคำตอบผิด** ตัวชี้วัดนี้เปรียบเทียบรูปแบบ SQL
หลัง normalize แต่ยังไวต่อชื่อ alias, LIMIT และวิธีเขียนที่เทียบเท่ากัน
จึงใช้ Execution Accuracy เป็นหลัก โดยเทียบค่าจริงทั้งตาราง รักษาแถวซ้ำ
และตรวจลำดับสำหรับ Top-N ไม่ใช้ชื่อ alias ของคอลัมน์ตัดสิน

ยังไม่สรุปเป็นค่าเงินหรือต้นทุนต่อ 300 ข้อ เพราะไม่ทราบอัตรา quota/billing ของ
IntelSphere ที่บัญชีนี้ใช้ ค่า cost จึงเป็น null ไม่ใช่ศูนย์
ไม่มีค่า API ของ Rule-based ไม่ได้แปลว่าต้นทุนเครื่อง/พัฒนาเป็นศูนย์

### ข้อจำกัดของผล

- AI ช่วยสร้าง schema, ข้อมูล, คำถาม, reference SQL และ tests
- ชุดนี้เป็น exploratory synthetic evaluation ไม่ใช่ benchmark อิสระหรือหลักฐานทางสถิติ
- ชุดพัฒนาและชุดประเมินมี task families และฐานข้อมูลเดียวกัน
- การตรึงไฟล์ช่วยทำซ้ำ ไม่ได้ทำให้ชุดข้อมูลปราศจากอคติ
- หากนำชุดประเมินนี้ไปใช้ปรับกฎ/Prompt ต่อ ต้องถือว่าถูกใช้พัฒนาแล้ว
- หากต้องสรุปทั่วไปควรเพิ่มคำถามที่คนอื่นเขียนและตรวจเฉลยเอง รวมหลาย data instances
- ชื่อโมเดลเป็น requested/returned ID ที่ IntelSphere รายงาน ไม่ได้ตรวจ deployment ภายในบริการ
- ไม่มีหลักฐานเพิ่มว่าครอบคลุม WMS จริงจากการทดสอบนี้

## ไฟล์ผลและวิธีทำซ้ำ

- `output/sprint2/latest-test-both.md` — สรุปผลล่าสุดอ่านง่าย
- `output/sprint2/latest-test-both.json` — SQL/rows/status/usage/timing รายข้อ
- `output/sprint2/test-both-*.json` — เก็บรอบที่มี timestamp ไม่ทับรอบก่อน
- `eval/sprint2/manifest.json` — hashes ของ source, prompt, schema และ metadata โมเดล

```powershell
.\.venv\Scripts\python.exe -m scripts.llm_query "ยอดขายเดือนกันยายน 2569"
.\.venv\Scripts\python.exe eval/run_sprint2.py --split dev --method rule
.\.venv\Scripts\python.exe eval/run_sprint2.py --split test --method both
```

คำสั่ง method both เรียก IntelSphere จริงข้อละหนึ่งครั้งและใช้ quota
หาก source/model ที่ตรึงไว้เปลี่ยน สคริปต์จะหยุด ให้เก็บ manifest เดิมแล้วแยกเวอร์ชัน
การทดลองใหม่อย่างชัดเจน ไม่เขียนทับเพื่อทำให้ผลเก่าเหมือนมาจากโค้ดใหม่

## การตั้งค่า

ใช้ `.env.llm` ซึ่งถูก Git ignore; ตัวอย่างที่ไม่ใส่ key อยู่ `.env.llm.example`
ตัวเชื่อมต่ออ่านไฟล์ใหม่ทุกคำถาม จึงเปลี่ยน key แล้วบันทึกได้โดยไม่ restart
ไม่ส่ง key กลับผ่าน API ไม่เก็บใน report และไม่ส่งต่อ Authorization เมื่อเกิด redirect

Base URL จาก API Platform: `https://gen.ai.kku.ac.th/api/v1`
Chat endpoint: `/chat/completions` ส่ง `model`, `messages`, `stream=false`
พร้อมค่าทดลอง temperature และ max_tokens

ระหว่างตั้งค่าพบว่าตัวอย่าง Model ID ในภาพไม่อยู่ในรายการบริการปัจจุบัน
IntelSphere ตอบ 401 พร้อม `Invalid model` จึงตรวจ `/models` แล้วใช้ชื่อ
`gpt-5.6-luna` ตามที่ผู้ใช้เลือก ไม่ควรตัดสินว่าทุก 401 แปลว่า key ผิด

## โค้ดสำคัญ

| ไฟล์ | หน้าที่ |
|---|---|
| app/llm/client.py | เรียก IntelSphere อ่าน config และเก็บ usage |
| app/llm/prompt.py | zero-shot prompt, schema/column contract และ hashes |
| app/llm/sql_guard.py | parse/ตรวจ SELECT และ execute แบบ read-only |
| app/llm/pipeline.py | รวมขั้นตอนและแยกสถานะไม่ตอบ/blocked/SQL error |
| app/llm/comparison.py | เทียบค่าจริง แถวซ้ำ และลำดับ |
| app/demo_api.py | endpoints ของ Rule-based, LLM และ compare |
| eval/run_sprint2.py | ตรวจ manifest, pin snapshot, ประเมินและสร้าง report |

หลักการ AST อ้างอิง [SQLGlot documentation](https://sqlglot.com/sqlglot.html)
และ transaction อ้างอิง [PostgreSQL SET TRANSACTION](https://www.postgresql.org/docs/current/sql-set-transaction.html)

## ประโยคใช้พูดนำเสนอ

“เราให้ Rule-based และ LLM รับคำถามชุดเดียวกัน ใช้ schema และนิยามธุรกิจเดียวกัน
แล้วรันกับ snapshot ฐานข้อมูลเดียวกัน โดย LLM ไม่ได้รับข้อมูลหรือคำตอบอ้างอิง
ในการทดลองสังเคราะห์สิบข้อ Rule-based ตอบถูกหกและปฏิเสธสี่ ส่วน LLM ตอบถูกสิบ
แต่ LLM ใช้เวลาและ Token มากกว่า ผลนี้เป็นเพียงการทดลองเบื้องต้น ยังสรุปทั่วไปไม่ได้ครับ”
