"""WMS LLM path is isolated, guarded and comparable to frozen references."""
import json
from pathlib import Path

import pytest
import yaml

from app.llm.comparison import resultsets_equal
from app.wms_llm.pipeline import run_wms_llm_pipeline
from app.wms_llm.prompt import wms_prompt_bundle
from app.wms_llm.sql_guard import check_wms_sql, WMSSQLRejected
from tests.fixtures import fresh_wms_conn


ROOT = Path(__file__).resolve().parent.parent
REFERENCES = yaml.safe_load(
    (ROOT / "eval/wms_mvp/ground_truth.yaml").read_text(encoding="utf-8")
)["cases"]

MODEL_SQL = {
    "wms_ref_01": """SELECT pm.part_id, pm.part_name, cs.status,
        COUNT(DISTINCT cs.serial_no)::bigint AS serial_count
        FROM current_stock cs JOIN part_obj po ON po.serial_no=cs.serial_no
        JOIN part_master pm ON pm.part_id=po.part_id
        GROUP BY pm.part_id, pm.part_name, cs.status
        ORDER BY pm.part_id, cs.status LIMIT 200""",
    "wms_ref_02": """SELECT cs.serial_no, pm.part_id, pm.part_name, cs.location_id,
        cs.condition, cs.status FROM current_stock cs
        JOIN part_obj po ON po.serial_no=cs.serial_no
        JOIN part_master pm ON pm.part_id=po.part_id
        WHERE cs.status='Quarantine' ORDER BY cs.serial_no LIMIT 200""",
    "wms_ref_03": """WITH received AS (
        SELECT id.inbound_id, po.part_id,
        COUNT(DISTINCT id.serial_no)::bigint AS received_qty
        FROM inbound_detail id JOIN part_obj po ON po.serial_no=id.serial_no
        GROUP BY id.inbound_id, po.part_id)
        SELECT io.inbound_id, io.status, pm.part_id, pm.part_name, ip.expected_qty,
        COALESCE(r.received_qty,0)::bigint AS received_qty,
        (ip.expected_qty-COALESCE(r.received_qty,0))::bigint AS remaining_qty
        FROM inbound_plan ip JOIN inbound_order io ON io.inbound_id=ip.inbound_id
        JOIN part_master pm ON pm.part_id=ip.part_id
        LEFT JOIN received r ON r.inbound_id=ip.inbound_id AND r.part_id=ip.part_id
        ORDER BY io.inbound_id, pm.part_id LIMIT 200""",
    "wms_ref_04": """WITH picked AS (
        SELECT od.outbound_id, po.part_id,
        COUNT(DISTINCT od.serial_no)::bigint AS picked_qty
        FROM outbound_detail od JOIN part_obj po ON po.serial_no=od.serial_no
        GROUP BY od.outbound_id, po.part_id)
        SELECT oo.outbound_id, oo.outstatus, pm.part_id, pm.part_name,
        op.expected_qty, COALESCE(p.picked_qty,0)::bigint AS picked_qty,
        (op.expected_qty-COALESCE(p.picked_qty,0))::bigint AS remaining_qty
        FROM outbound_plan op JOIN outbound_order oo ON oo.outbound_id=op.outbound_id
        JOIN part_master pm ON pm.part_id=op.part_id
        LEFT JOIN picked p ON p.outbound_id=op.outbound_id AND p.part_id=op.part_id
        ORDER BY oo.outbound_id, pm.part_id LIMIT 200""",
    "wms_ref_05": """SELECT oo.outstatus, COUNT(*)::bigint AS order_count
        FROM outbound_order oo WHERE oo.order_date >= DATE '2026-09-01'
        AND oo.order_date < DATE '2026-10-01' GROUP BY oo.outstatus
        ORDER BY oo.outstatus LIMIT 200""",
}


@pytest.fixture
def conn():
    connection = fresh_wms_conn()
    yield connection
    connection.close()


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda case: case["id"])
def test_manual_model_sql_matches_each_reference(conn, reference):
    cursor = conn.execute(reference["sql"], reference["params"])
    expected_rows = cursor.fetchall()
    expected_columns = [column.name for column in cursor.description]
    output = json.dumps({"status": "ok", "sql": MODEL_SQL[reference["id"]],
                         "reason": "test fixture"})

    result = run_wms_llm_pipeline(reference["question"], conn, manual_output=output)

    assert result["status"] == "ok", result
    assert result["mode"] == "manual_output" and result["generation"] is None
    assert result["sql_valid"] is True and result["sql_executed"] is True
    assert resultsets_equal(
        result["rows"], expected_rows,
        actual_columns=len(result["columns"]), expected_columns=len(expected_columns),
        ordered=reference["ordered"],
    )


@pytest.mark.parametrize("query", [
    "DELETE FROM current_stock",
    "SELECT * FROM products",
    "SELECT pg_sleep(10) FROM current_stock",
    "SELECT secret FROM current_stock",
    "SELECT * FROM pg_catalog.pg_authid",
    "SELECT * FROM current_stock UNION SELECT * FROM current_stock",
])
def test_wms_guard_blocks_unsafe_or_other_domain_sql(query):
    with pytest.raises(WMSSQLRejected):
        check_wms_sql(query)


def test_blocked_model_sql_records_guard_state_without_execution(conn):
    result = run_wms_llm_pipeline(
        "คำถาม", conn,
        manual_output=json.dumps({"status": "ok", "sql": "DELETE FROM current_stock",
                                  "reason": "unsafe"}),
    )
    assert result["status"] == "blocked"
    assert result["sql_valid"] is False
    assert result["sql_executed"] is False


def test_unsupported_reply_never_executes_sql(conn):
    result = run_wms_llm_pipeline(
        "ลูกค้ารายไหนเบิกสินค้ามากที่สุด", conn,
        manual_output=json.dumps({"status": "unsupported", "sql": None,
                                  "reason": "customer is outside phase 1"}),
    )
    assert result["status"] == "unsupported"
    assert result["generated_sql"] is None
    assert result["rows"] == []


def test_wms_prompt_contains_scope_but_no_seed_or_reference_answers():
    bundle = wms_prompt_bundle("สรุปจำนวนสต็อกปัจจุบันแยกตาม Part และสถานะ")
    prompt = bundle["messages"][0]["content"]
    assert "CREATE TABLE part_master" in prompt
    assert "SUPPORTED TASKS" in prompt and "COUNT(DISTINCT" in prompt
    assert "INSERT INTO" not in prompt and "SYN-A-001" not in prompt
    assert "6 Serial" not in prompt and len(bundle["prompt_sha256"]) == 64


def test_generator_metadata_is_preserved_without_real_api_call(conn):
    def generator(bundle):
        assert bundle["version"] == "wms-mvp-zero-shot-v1"
        return {"content": json.dumps({"status": "unsupported", "sql": None,
                                        "reason": "outside scope"}),
                "provider": "fake", "input_tokens": 123, "output_tokens": 12}

    result = run_wms_llm_pipeline("คำถามนอกขอบเขต", conn, generator=generator)
    assert result["status"] == "unsupported"
    assert result["mode"] == "live_api"
    assert result["generation"]["input_tokens"] == 123
