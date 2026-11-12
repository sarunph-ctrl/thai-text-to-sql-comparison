"""Candidate development data is balanced, traceable, and never a held-out set."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "eval/wms_mvp"


def load(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def test_candidate_dev_has_planned_size_and_balance():
    dataset = load("dev.candidate.yaml")
    cases = dataset["cases"]
    assert dataset["split"] == "development"
    assert dataset["status"] == "draft_before_independent_review"
    assert len(cases) == 35
    assert Counter(case["scope_label"] for case in cases) == {
        "in_scope": 25,
        "out_of_scope": 10,
    }
    assert Counter(case["family"] for case in cases if case["scope_label"] == "in_scope") == {
        "current_stock_summary": 5,
        "current_stock_detail": 5,
        "inbound_progress": 5,
        "outbound_progress": 5,
        "operational_order_status": 5,
    }


def test_ids_questions_and_out_of_scope_reasons_are_unique():
    cases = load("dev.candidate.yaml")["cases"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert len({case["question"].strip().casefold() for case in cases}) == len(cases)
    reasons = [case["out_of_scope_reason"] for case in cases if case["scope_label"] == "out_of_scope"]
    assert len(reasons) == len(set(reasons)) == 10


def test_in_scope_cases_reference_frozen_ground_truth_correctly():
    dataset = load("dev.candidate.yaml")
    ground_truth = load("ground_truth.yaml")
    references = {case["id"]: case for case in ground_truth["cases"]}
    for case in dataset["cases"]:
        if case["scope_label"] == "in_scope":
            reference = references[case["reference_id"]]
            assert case["family"] == reference["family"]
            assert case["expected_status"] == "ok"
            assert case["ordered"] == reference["ordered"]
            assert case["out_of_scope_reason"] is None
        else:
            assert case["family"] is None
            assert case["reference_id"] is None
            assert case["expected_status"] == "unsupported"
            assert case["out_of_scope_reason"]


def test_candidate_does_not_populate_or_copy_the_heldout_template():
    development = load("dev.candidate.yaml")
    heldout = load("heldout.template.yaml")
    assert heldout["cases"] == []
    assert {case["id"] for case in development["cases"]}.isdisjoint(
        {case.get("id") for case in heldout["cases"]}
    )


def test_every_case_has_difficulty_and_linguistic_labels():
    allowed_difficulty = {"basic", "paraphrase", "compositional", "boundary"}
    for case in load("dev.candidate.yaml")["cases"]:
        assert case["difficulty"] in allowed_difficulty
        assert case["linguistic_features"]


def test_candidate_manifest_freezes_draft_without_claiming_approval():
    manifest = json.loads((DATA / "dev_candidate_manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "development-candidate"
    assert manifest["algorithm"] == "sha256-lf"
    assert manifest["review_status"] == "pending_independent_review"
    for relative_path, expected_hash in manifest["files"].items():
        normalized = (ROOT / relative_path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(normalized).hexdigest() == expected_hash, relative_path
