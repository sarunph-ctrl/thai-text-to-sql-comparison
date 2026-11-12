"""Guardrails for WMS dataset authoring before independent review is complete."""
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "eval/wms_mvp"


def load(name: str):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def test_development_and_heldout_templates_are_separate_and_empty():
    development = load("dev.template.yaml")
    heldout = load("heldout.template.yaml")
    assert development["split"] == "development"
    assert heldout["split"] == "heldout"
    assert development["status"] == heldout["status"] == "empty_template"
    assert development["cases"] == heldout["cases"] == []
    assert development["snapshot_ids"] == heldout["snapshot_ids"] == ["wms_seed_v1"]


def test_templates_pin_the_same_scope_and_ground_truth_versions():
    development = load("dev.template.yaml")
    heldout = load("heldout.template.yaml")
    for dataset in (development, heldout):
        assert dataset["scope_version"] == "1.0-draft"
        assert dataset["ground_truth_version"] == "1.0-draft"
        assert dataset["allowed_scope_labels"] == ["in_scope", "out_of_scope"]


def test_protocol_defines_required_metrics_and_leakage_controls():
    protocol = (DATA / "EVALUATION_PROTOCOL.md").read_text(encoding="utf-8")
    required_terms = [
        "Execution Accuracy",
        "Out-of-scope Rejection Accuracy",
        "Valid SQL Rate",
        "Median",
        "p95",
        "Token Usage",
        "LLM Consistency",
        "Error Taxonomy",
        "Multiple Data Snapshots",
        "Leakage Rules",
    ]
    for term in required_terms:
        assert term in protocol
