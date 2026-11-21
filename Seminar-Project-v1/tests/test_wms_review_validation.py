"""Returned review evidence must be complete before the project gate passes."""
from copy import deepcopy
from pathlib import Path

import yaml

from app.review_validation import validate_review_pair
from scripts.build_wms_review_packet import candidate_review_template


ROOT = Path(__file__).resolve().parent.parent


def forms():
    core = yaml.safe_load((ROOT / "eval/wms_mvp/review_record.yaml").read_text(encoding="utf-8"))
    candidate = yaml.safe_load(candidate_review_template())
    dataset = yaml.safe_load((ROOT / "eval/wms_mvp/dev.candidate.yaml").read_text(encoding="utf-8"))
    return core, candidate, dataset


def approve_reviewer(form):
    form["reviewer"].update({
        "name": "Independent Reviewer",
        "role": "SQL and warehouse reviewer",
        "review_date": "2026-11-22",
        "independent_from_rule_and_prompt_tuning": True,
        "reviewed_before_seeing_system_outputs": True,
    })


def approved_forms():
    core, candidate, dataset = forms()
    approve_reviewer(core)
    approve_reviewer(candidate)
    core["artifact_checks"] = {key: "approved" for key in core["artifact_checks"]}
    for entry in core["open_business_decisions"].values():
        entry["decision"] = "accepted for MVP draft"
        entry["rationale"] = "Reviewed against the stated domain assumptions"
    for case in core["case_reviews"]:
        for field in ("question_is_unambiguous", "rules_match_question", "sql_is_correct",
                      "expected_result_is_correct", "ordering_flag_is_correct"):
            case[field] = True
        case["decision"] = "approve"
    core["overall"].update({
        "decision": "approved",
        "approved_artifact_version": core["artifact_version"],
        "reviewer_signoff": "Independent Reviewer",
    })
    for case in candidate["cases"]:
        for field in ("scope_label_correct", "family_and_reference_correct",
                      "natural_for_intended_user", "meaning_is_unambiguous",
                      "not_too_similar_to_another_case"):
            case[field] = True
        case["decision"] = "approve"
    candidate["overall"].update({
        "decision": "approved",
        "approved_dataset_version": candidate["dataset_version"],
        "reviewer_signoff": "Independent Reviewer",
    })
    return core, candidate, dataset


def test_pending_templates_do_not_pass_review_gate():
    core, candidate, dataset = forms()
    result = validate_review_pair(core, candidate, dataset)
    assert result["gate_passed"] is False
    assert result["next_action"] == "resolve_review_issues"
    assert result["core"]["issues"] and result["candidate"]["issues"]


def test_complete_independent_review_passes_gate():
    core, candidate, dataset = approved_forms()
    result = validate_review_pair(core, candidate, dataset)
    assert result["gate_passed"] is True
    assert result["next_action"] == "freeze_reviewed_artifacts"
    assert result["core"]["issues"] == []
    assert result["candidate"]["case_count"] == 35
    assert result["candidate"]["case_decisions"]["approve"] == 35


def test_one_unreviewed_case_or_different_reviewer_blocks_gate():
    core, candidate, dataset = approved_forms()
    candidate["cases"][0]["meaning_is_unambiguous"] = None
    candidate["reviewer"]["name"] = "Another Reviewer"
    result = validate_review_pair(core, candidate, dataset)
    assert result["gate_passed"] is False
    assert any("meaning_is_unambiguous" in issue for issue in result["candidate"]["issues"])
    assert result["pair_issues"]


def test_missing_or_duplicate_candidate_id_blocks_gate():
    core, candidate, dataset = approved_forms()
    candidate = deepcopy(candidate)
    candidate["cases"][1]["id"] = candidate["cases"][0]["id"]
    result = validate_review_pair(core, candidate, dataset)
    assert result["gate_passed"] is False
    assert any("duplicate" in issue or "missing" in issue for issue in result["candidate"]["issues"])
