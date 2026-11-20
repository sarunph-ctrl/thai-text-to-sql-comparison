"""WMS development API and page use the real pipeline and disposable data."""
from pathlib import Path
import json

from psycopg.conninfo import make_conninfo

from app import demo_api
from scripts.local_demo import connection_string
from tests.fixtures import fresh_wms_conn


def schema_connection_string(schema: str) -> str:
    return make_conninfo(
        connection_string(admin=True, database="seminar_tests"),
        options=f"-c search_path={schema},public -c timezone=Asia/Bangkok",
    )


def test_wms_health_and_query_endpoint(monkeypatch):
    conn = fresh_wms_conn()
    try:
        dsn = schema_connection_string(conn.test_schema)
        monkeypatch.setattr(demo_api, "database_url", lambda: dsn)

        health = demo_api.wms_health()
        assert health["ok"] is True
        assert health["profile"] == "wms-mvp-development"
        assert health["stock_serials"] > 0

        result = demo_api.wms_query(demo_api.QueryRequest(
            text="สรุปจำนวนสต็อกปัจจุบันแยกตาม Part และสถานะ"
        ))
        assert result["status"] == "ok"
        assert result["family"] == "current_stock_summary"
        assert result["sql_valid"] is True
        assert result["sql_executed"] is True
        assert result["rows"]
    finally:
        conn.close()


def test_wms_api_rejects_out_of_scope_without_sql(monkeypatch):
    conn = fresh_wms_conn()
    try:
        monkeypatch.setattr(
            demo_api, "database_url", lambda: schema_connection_string(conn.test_schema)
        )
        result = demo_api.wms_query(demo_api.QueryRequest(
            text="ลูกค้ารายไหนเบิกสินค้ามากที่สุด"
        ))
        assert result["status"] == "unsupported"
        assert result["sql"] is None
        assert result["sql_executed"] is False
    finally:
        conn.close()


def test_wms_manual_llm_check_uses_wms_guard(monkeypatch):
    conn = fresh_wms_conn()
    try:
        monkeypatch.setattr(
            demo_api, "database_url", lambda: schema_connection_string(conn.test_schema)
        )
        safe = demo_api.wms_llm_check(demo_api.ManualLLMRequest(
            text="เดือนกันยายน 2569 มี Outbound Order แต่ละสถานะกี่รายการ",
            model_output=json.dumps({
                "status": "ok",
                "sql": "SELECT outstatus, COUNT(*)::bigint AS order_count FROM outbound_order WHERE order_date >= DATE '2026-09-01' AND order_date < DATE '2026-10-01' GROUP BY outstatus ORDER BY outstatus LIMIT 200",
                "reason": "monthly outbound status",
            }),
        ))
        assert safe["status"] == "ok"
        assert safe["rows"] == [["Pending", 1], ["Picked", 1]]

        blocked = demo_api.wms_llm_check(demo_api.ManualLLMRequest(
            text="ลบข้อมูล", model_output=json.dumps({
                "status": "ok", "sql": "DELETE FROM current_stock", "reason": "bad"
            }),
        ))
        assert blocked["status"] == "blocked"
    finally:
        conn.close()


def test_wms_page_assets_exist():
    root = Path(__file__).resolve().parent.parent
    for name in ("wms.html", "wms.js", "wms.css"):
        path = root / "web" / name
        assert path.is_file()
        assert path.stat().st_size > 100
