# Portable Docker Demo

ชุดนี้สร้าง WMS development demo และ Legacy baseline ด้วย PostgreSQL ใน Docker โดยไม่ต้องติดตั้ง Python หรือ PostgreSQL ลงเครื่องปลายทาง

## สิ่งที่รัน

- หน้า WMS: `http://127.0.0.1:8000/wms`
- หน้า Legacy baseline: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`
- PostgreSQL 17 อยู่ใน Docker network เท่านั้นและไม่เปิดพอร์ตออกสู่เครื่อง
- แอปเชื่อมฐานข้อมูลด้วย `seminar_reader` ซึ่งถูกบังคับเป็น read-only
- ข้อมูลทั้งหมดเป็น Synthetic data ไม่ใช่ข้อมูลจริงของ WMS เดิม

## เริ่มรัน

เปิด PowerShell ในโฟลเดอร์ `Seminar-Project-v1` แล้วรัน:

```powershell
docker compose up -d --build
docker compose ps
```

เมื่อทั้ง `postgres_db` และ `app` เป็น `healthy` ให้เปิด `http://127.0.0.1:8000/wms`

ถ้าพอร์ต 8000 ถูกใช้งานอยู่:

```powershell
$env:DEMO_HTTP_PORT = "18000"
docker compose up -d --build
```

จากนั้นเปิด `http://127.0.0.1:18000/wms`

## โหมดที่ไม่ใช้ LLM

ไม่ต้องตั้ง API key ระบบ Rule-based, Schema, Ground Truth และ Recorded results ยังสาธิตได้ครบ ส่วนการเรียก LLM สดจะแสดงว่าไม่ได้ตั้งค่า ซึ่งเป็นพฤติกรรมที่ตั้งใจไว้

## เปิดการเรียก LLM สดแบบชั่วคราว

ตั้งค่าใน PowerShell session ปัจจุบันก่อนสั่ง `up` โดยไม่เขียน key ลง Git:

```powershell
$env:LLM_API_KEY = "วาง-key-ใน-terminal-เท่านั้น"
$env:LLM_MODEL = "gpt-5.6-luna"
docker compose up -d --build
```

API key ไม่ถูก COPY เข้า image แต่ Docker Compose จะส่งเป็น environment variable ให้ container ขณะรัน ห้าม commit `.env` หรือวาง key ในภาพหน้าจอ

## ตรวจสถานะและดู Log

```powershell
docker compose ps
docker compose logs --tail 100 app
docker compose logs --tail 100 postgres_db
```

ตรวจ Health API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/wms/health
```

## หยุดและรีเซ็ต

หยุดโดยเก็บข้อมูลใน Docker volume:

```powershell
docker compose down
```

รีเซ็ต Synthetic database ใหม่ทั้งหมด:

```powershell
docker compose down -v
docker compose up -d --build
```

คำสั่ง `down -v` ลบเฉพาะ named volume ของ Compose project นี้และข้อมูลใน volume กู้คืนไม่ได้ แต่ Seed สามารถสร้างใหม่ได้จาก Git

## ข้อจำกัดที่ต้องบอกตอนสาธิต

- Container นี้พิสูจน์ว่า Prototype รันซ้ำได้ ไม่ได้พิสูจน์ว่า Schema ตรงกับ WMS ขององค์กรจริง
- ค่าเริ่มต้นของ Compose เป็นรหัสผ่านสำหรับ Local demo เท่านั้น ห้ามใช้ใน Production
- Live LLM ยังขึ้นกับ Provider, Quota และ Network จึงควรเตรียม Recorded result เป็นแผนสำรอง
- หากแก้ไฟล์ Seed หลัง volume ถูกสร้าง ต้องใช้ `docker compose down -v` เพื่อให้ Init script รันใหม่
