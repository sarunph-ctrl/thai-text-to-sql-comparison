"""Raw-run records are reproducible, append-only, and secret resistant."""
from __future__ import annotations

import json

import pytest

from app.evaluation_records import (
    InvalidRunRecord,
    append_jsonl,
    finalize_run_record,
    read_jsonl,
    result_fingerprint,
)


def base_record(**overrides):
    record = {
        "experiment_id": "wms-draft",
        "case_id": "dev-001",
        "split": "development",
        "snapshot_id": "wms_seed_v1",
        "method": "rule",
        "repeat_index": 1,
        "scope_label": "in_scope",
        "status": "ok",
        "execution_correct": True,
        "sql_valid": True,
        "sql_executed": True,
        "columns": ["part_id", "count"],
        "rows": [["PART-A", 2], ["PART-B", 1]],
        "ordered": False,
        "method_ms": 1.25,
        "input_tokens": None,
        "output_tokens": None,
    }
    record.update(overrides)
    return record


def test_unordered_fingerprint_ignores_order_but_keeps_duplicates():
    first = result_fingerprint(status="ok", columns=["v"], rows=[[1], [2], [2]], ordered=False)
    reordered = result_fingerprint(status="ok", columns=["v"], rows=[[2], [1], [2]], ordered=False)
    fewer = result_fingerprint(status="ok", columns=["v"], rows=[[1], [2]], ordered=False)
    ordered = result_fingerprint(status="ok", columns=["v"], rows=[[2], [1], [2]], ordered=True)
    assert first == reordered
    assert first != fewer
    assert first != ordered


def test_finalize_adds_metadata_without_questions_or_secrets():
    finalized = finalize_run_record(base_record())
    assert finalized["record_version"] == "1.0"
    assert finalized["run_id"]
    assert finalized["recorded_at"].endswith("+00:00")
    assert len(finalized["result_fingerprint"]) == 64
    assert "question" not in finalized


def test_append_and_read_jsonl_round_trip(tmp_path):
    path = tmp_path / "raw" / "runs.jsonl"
    first = append_jsonl(path, base_record(case_id="dev-001"))
    second = append_jsonl(path, base_record(case_id="dev-002", execution_correct=False))
    records = read_jsonl(path)
    assert [record["run_id"] for record in records] == [first["run_id"], second["run_id"]]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.parametrize("secret_field", ["api_key", "password", "authorization", "access_token"])
def test_secret_fields_are_rejected(secret_field):
    with pytest.raises(InvalidRunRecord, match="unknown fields|forbidden secret field"):
        finalize_run_record({**base_record(), secret_field: "do-not-store"})


def test_secret_like_values_and_unknown_fields_are_rejected():
    with pytest.raises(InvalidRunRecord, match="possible secret"):
        finalize_run_record(base_record(message="Bearer abcdefghijklmnopqrstuvwxyz"))
    with pytest.raises(InvalidRunRecord, match="unknown fields"):
        finalize_run_record({**base_record(), "question": "held-out text must stay in dataset"})


def test_invalid_rows_and_unsafe_unsupported_record_are_rejected():
    with pytest.raises(InvalidRunRecord, match="column count"):
        finalize_run_record(base_record(rows=[["PART-A"]]))
    with pytest.raises(InvalidRunRecord, match="cannot execute SQL"):
        finalize_run_record(base_record(
            scope_label="out_of_scope", status="unsupported", sql_executed=True,
            execution_correct=False, columns=[], rows=[], sql_valid=None,
        ))


def test_corrupt_jsonl_reports_line_number(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text(json.dumps(finalize_run_record(base_record())) + "\nnot-json\n", encoding="utf-8")
    with pytest.raises(InvalidRunRecord, match=r":2:"):
        read_jsonl(path)
