"""The WMS runner validates frozen inputs and records real development runs."""
import pytest

from app.evaluation_records import read_jsonl
from eval.run_wms_mvp import main, verify_frozen_inputs


def test_frozen_manifests_match_current_evaluation_inputs():
    v1 = verify_frozen_inputs("v1")
    v2 = verify_frozen_inputs("v2")
    assert v1["candidate"]["review_status"] == "pending_independent_review"
    assert v1["snapshot"] is None
    assert v2["snapshot"]["snapshot_id"] == "wms_seed_v2"


def test_runner_requires_explicit_draft_acknowledgement():
    with pytest.raises(SystemExit):
        main(["--method", "rule"])


def test_rule_runner_records_all_candidate_cases_without_questions(tmp_path, capsys):
    output = tmp_path / "rule-v1.jsonl"
    assert main([
        "--ack-draft", "--method", "rule", "--snapshot", "v1",
        "--output", str(output), "--allow-dirty-smoke",
    ]) == 0
    records = read_jsonl(output)
    assert len(records) == 35
    assert {record["method"] for record in records} == {"rule"}
    assert {record["snapshot_id"] for record in records} == {"wms_seed_v1"}
    assert all("question" not in record for record in records)
    assert sum(record["execution_correct"] for record in records) == 35
    printed = capsys.readouterr().out
    assert '"review_status": "pending_independent_review"' in printed
