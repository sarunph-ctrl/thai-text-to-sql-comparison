"""Run the same frozen WMS references against a different synthetic snapshot."""
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
V2_EXPECTED = ROOT / "eval/wms_mvp/snapshot_v2_expected.yaml"
V2_MANIFEST = ROOT / "eval/wms_mvp/snapshot_v2_manifest.json"


def documents():
    references = yaml.safe_load(GROUND_TRUTH.read_text(encoding="utf-8"))
    snapshot = yaml.safe_load(V2_EXPECTED.read_text(encoding="utf-8"))
    return references, snapshot


@pytest.mark.parametrize(
    "case",
    documents()[0]["cases"],
    ids=lambda case: "v2_" + case["id"],
)
def test_frozen_reference_sql_matches_v2_expected_rows(case):
    _, snapshot = documents()
    conn = fresh_wms_conn(seed_name="wms_mvp_seed_v2.sql")
    try:
        cursor = conn.execute(case["sql"], case["params"])
        actual = [list(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    expected = snapshot["expected_rows"][case["id"]]
    if case["ordered"]:
        assert actual == expected
    else:
        assert Counter(map(tuple, actual)) == Counter(map(tuple, expected))


def test_v2_covers_all_references_and_changes_every_answer():
    references, snapshot = documents()
    v1 = {case["id"]: case["expected_rows"] for case in references["cases"]}
    assert set(snapshot["expected_rows"]) == set(v1)
    for reference_id, v2_rows in snapshot["expected_rows"].items():
        assert Counter(map(tuple, v2_rows)) != Counter(map(tuple, v1[reference_id]))


def test_v2_is_synthetic_and_pending_review():
    _, snapshot = documents()
    assert snapshot["snapshot_id"] == "wms_seed_v2"
    assert snapshot["review_status"] == "pending_independent_review"
    seed = (ROOT / snapshot["seed"]).read_text(encoding="utf-8")
    assert "SYN2-" in seed


def test_v2_manifest_freezes_snapshot_inputs():
    manifest = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["algorithm"] == "sha256-lf"
    assert manifest["snapshot_id"] == "wms_seed_v2"
    assert manifest["review_status"] == "pending_independent_review"
    for relative_path, expected_hash in manifest["files"].items():
        normalized = (ROOT / relative_path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(normalized).hexdigest() == expected_hash, relative_path
