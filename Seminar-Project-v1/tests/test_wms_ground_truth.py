"""Execute every WMS reference query and verify its frozen expected result."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from tests.fixtures import fresh_wms_conn


ROOT = Path(__file__).resolve().parent.parent
GROUND_TRUTH = ROOT / "eval/wms_mvp/ground_truth.yaml"
MANIFEST = ROOT / "eval/wms_mvp/manifest.json"
TYPE_NAMES = {
    20: "bigint",
    23: "integer",
    25: "text",
    1043: "text",
}


def load_cases():
    document = yaml.safe_load(GROUND_TRUTH.read_text(encoding="utf-8"))
    assert document["version"] == "1.0-draft"
    assert document["review_status"] == "pending_independent_review"
    return document["cases"]


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case["id"])
def test_reference_sql_matches_frozen_expected_result(case):
    conn = fresh_wms_conn()
    try:
        cursor = conn.execute(case["sql"], case["params"])
        actual_rows = [list(row) for row in cursor.fetchall()]
        actual_columns = [column.name for column in cursor.description]
        actual_types = [TYPE_NAMES.get(column.type_code, str(column.type_code)) for column in cursor.description]
    finally:
        conn.close()

    expected_columns = case["expected_columns"]
    assert actual_columns == [column["name"] for column in expected_columns]
    assert actual_types == [column["type"] for column in expected_columns]

    expected_rows = case["expected_rows"]
    if case["ordered"]:
        assert actual_rows == expected_rows
    else:
        assert Counter(map(tuple, actual_rows)) == Counter(map(tuple, expected_rows))


def test_ground_truth_has_one_unique_case_per_query_family():
    cases = load_cases()
    assert len(cases) == 5
    assert len({case["id"] for case in cases}) == 5
    assert {case["family"] for case in cases} == {
        "current_stock_summary",
        "current_stock_detail",
        "inbound_progress",
        "outbound_progress",
        "operational_order_status",
    }


def test_every_case_is_parameterized_and_traceable():
    for case in load_cases():
        assert case["rules"]
        assert ";" not in case["sql"].strip().rstrip(";")
        for value in case["params"].values():
            assert str(value) not in case["sql"]


def test_manifest_hashes_freeze_all_ground_truth_inputs():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["algorithm"] == "sha256-lf"
    assert manifest["version"] == "1.0-draft"
    for relative_path, expected_hash in manifest["files"].items():
        normalized = (ROOT / relative_path).read_bytes().replace(b"\r\n", b"\n")
        actual_hash = hashlib.sha256(normalized).hexdigest()
        assert actual_hash == expected_hash, relative_path
