"""Read-only presentation metadata, kept outside the frozen experiment source."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "output/sprint2/latest-test-both.json"

SCHEMA = [
    {"name": "products", "title": "สินค้า", "grain": "หนึ่งแถวต่อสินค้าหนึ่งรายการ",
     "columns": ["id · PK", "name · ชื่อสินค้า", "price · ราคาปัจจุบัน"]},
    {"name": "orders", "title": "ออเดอร์", "grain": "หนึ่งแถวต่อออเดอร์",
     "columns": ["id · PK", "order_date · วันที่ออเดอร์", "status · paid / pending / cancelled"]},
    {"name": "order_items", "title": "รายการขาย", "grain": "หนึ่งแถวต่อสินค้าหนึ่งบรรทัดในออเดอร์",
     "columns": ["id · PK", "order_id · FK → orders", "product_id · FK → products", "qty · จำนวน", "unit_price · ราคาขณะขาย"]},
    {"name": "warehouses", "title": "คลังสินค้า", "grain": "หนึ่งแถวต่อคลัง",
     "columns": ["id · PK", "name · ชื่อคลัง"]},
    {"name": "stock_movements", "title": "การเคลื่อนไหวสินค้า", "grain": "หนึ่งเหตุการณ์ต่อสินค้าหนึ่งชนิดในคลังหนึ่งแห่ง",
     "columns": ["id · PK", "product_id · FK → products", "warehouse_id · FK → warehouses", "movement_date · วันที่เกิดเหตุการณ์",
                 "movement_type · opening / receipt / issue", "qty · จำนวนบวก", "order_item_id · FK ไม่บังคับ → order_items"]},
]

DEFINITIONS = [
    {"title": "ยอดขาย", "formula": "Σ (จำนวน × ราคาขณะขาย)", "note": "เฉพาะออเดอร์ paid • ช่วงเวลาอิง order_date"},
    {"title": "สินค้าคงเหลือ", "formula": "ตั้งต้น + รับเข้า − จ่ายออก", "note": "แยกสินค้าและคลัง • รวมทุก movement ที่บันทึก"},
    {"title": "ยอดจ่ายออก", "formula": "Σ จำนวนของ issue", "note": "รวมทุกคลัง • ช่วงเวลาอิง movement_date • ไม่กรอง paid"},
]


def recorded_report() -> dict:
    raw = json.loads(REPORT.read_text(encoding="utf-8"))
    config = raw.get("configuration", {})
    return {"recorded": True, "evaluated_at": raw["evaluated_at"],
            "dataset_note": raw["dataset_note"], "source_report": REPORT.name,
            "model": config.get("requested_model"), "provider": config.get("provider"),
            "summary": raw["summary"], "snapshot_row_counts": raw["snapshot_row_counts"],
            "manifest_sha256": raw["manifest_sha256"], "data_snapshot_sha256": raw["data_snapshot_sha256"],
            "cases": [{k: case[k] for k in ("id", "question", "ordered", "expected_columns", "expected_rows", "rule", "llm")}
                      for case in raw["cases"]]}


def schema_payload() -> dict:
    return {"tables": SCHEMA, "definitions": DEFINITIONS,
            "ddl": (ROOT / "db/demo_schema.sql").read_text(encoding="utf-8")}
