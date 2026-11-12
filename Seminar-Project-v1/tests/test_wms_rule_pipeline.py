"""Candidate Development questions traverse the real WMS Rule-based pipeline."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.llm.comparison import resultsets_equal
from app.wms.guard import WMSQueryRejected, check_wms_template
from app.wms.pipeline import run_wms_rule_pipeline
from tests.fixtures import fresh_wms_conn


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "eval/wms_mvp"


def load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def reference_results(conn):
    references = load("ground_truth.yaml")["cases"]
    output = {}
    for case in references:
        cursor = conn.execute(case["sql"], case["params"])
        output[case["id"]] = {
            "rows": cursor.fetchall(),
            "columns": [column.name for column in cursor.description],
            "ordered": case["ordered"],
        }
    return output


def assert_candidate_on_snapshot(seed_name):
    dataset = load("dev.candidate.yaml")
    conn = fresh_wms_conn(seed_name=seed_name)
    try:
        expected = reference_results(conn)
        for case in dataset["cases"]:
            result = run_wms_rule_pipeline(case["question"], conn)
            if case["scope_label"] == "out_of_scope":
                assert result.status == "unsupported", (case["id"], result)
                assert result.sql is None
                assert result.sql_executed is False
                continue
            reference = expected[case["reference_id"]]
            assert result.status == "ok", (case["id"], result)
            assert result.sql_valid is True
            assert result.sql_executed is True
            assert result.truncated is False
            assert resultsets_equal(
                result.rows,
                reference["rows"],
                actual_columns=len(result.columns),
                expected_columns=len(reference["columns"]),
                ordered=case["ordered"],
            ), (case["id"], result.rows, reference["rows"])
    finally:
        conn.close()


def test_candidate_development_set_on_baseline_snapshot():
    assert_candidate_on_snapshot("wms_mvp_seed.sql")


def test_candidate_development_set_on_robustness_snapshot():
    assert_candidate_on_snapshot("wms_mvp_seed_v2.sql")


def test_explicit_filter_is_rejected_instead_of_silently_dropped():
    conn = fresh_wms_conn()
    try:
        result = run_wms_rule_pipeline(
            "สรุปจำนวนสต็อกปัจจุบันแยก Part และสถานะ เฉพาะ PART-A", conn
        )
        assert result.status == "unsupported"
        assert result.sql is None
        assert result.sql_executed is False
    finally:
        conn.close()


def test_guard_rejects_non_select_unknown_tables_and_bad_parameter_counts():
    for query, params in [
        ("DELETE FROM current_stock WHERE serial_no = %s", ["x"]),
        ("SELECT * FROM customer LIMIT 10", []),
        ("SELECT serial_no FROM current_stock WHERE status = %s LIMIT 10", []),
    ]:
        try:
            check_wms_template(query, params)
        except WMSQueryRejected:
            pass
        else:
            raise AssertionError(query)


def test_empty_and_unknown_questions_never_execute_sql():
    conn = fresh_wms_conn()
    try:
        for question in ("", "วันนี้อากาศเป็นอย่างไร", "PART-A มีอะไรบ้าง"):
            result = run_wms_rule_pipeline(question, conn)
            assert result.status == "unsupported"
            assert result.sql_executed is False
    finally:
        conn.close()
