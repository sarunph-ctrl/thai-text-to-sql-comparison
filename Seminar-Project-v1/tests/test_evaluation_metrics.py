"""Exact metric definitions for the WMS evaluation protocol."""
from __future__ import annotations

import pytest

from app.evaluation_metrics import (
    nearest_rank_percentile,
    summarize_consistency,
    summarize_runs,
    wilson_interval,
)


def sample_runs():
    return [
        {"case_id": "i1", "scope_label": "in_scope", "status": "ok",
         "execution_correct": True, "sql_valid": True, "sql_executed": True,
         "method_ms": 1, "input_tokens": 10, "output_tokens": 2},
        {"case_id": "i2", "scope_label": "in_scope", "status": "ok",
         "execution_correct": True, "sql_valid": True, "sql_executed": True,
         "method_ms": 2, "input_tokens": 12, "output_tokens": 3},
        {"case_id": "i3", "scope_label": "in_scope", "status": "error",
         "execution_correct": False, "sql_valid": True, "sql_executed": True,
         "method_ms": 3, "input_tokens": None, "output_tokens": None,
         "error_category": "wrong_filter_or_status"},
        {"case_id": "i4", "scope_label": "in_scope", "status": "error",
         "execution_correct": False, "sql_valid": False, "sql_executed": False,
         "method_ms": 100, "timed_out": True,
         "error_category": "new_unknown_category"},
        {"case_id": "o1", "scope_label": "out_of_scope", "status": "unsupported",
         "execution_correct": False, "sql_valid": False, "sql_executed": False,
         "method_ms": 4},
        {"case_id": "o2", "scope_label": "out_of_scope", "status": "ok",
         "execution_correct": False, "sql_valid": True, "sql_executed": True,
         "method_ms": 5, "truncated": True, "error_category": "unsafe_acceptance"},
    ]


def test_primary_metrics_keep_in_scope_and_rejection_denominators_separate():
    summary = summarize_runs(sample_runs())
    assert summary["in_scope"]["total"] == 4
    assert summary["in_scope"]["execution_correct"] == 2
    assert summary["in_scope"]["execution_accuracy"] == 0.5
    assert summary["in_scope"]["valid_sql_rate"] == 0.75
    assert summary["out_of_scope"] == {
        "total": 2,
        "correct_rejections": 1,
        "rejection_accuracy": 0.5,
        "rejection_accuracy_wilson95": summary["out_of_scope"]["rejection_accuracy_wilson95"],
    }


def test_latency_tokens_safety_and_errors_are_explicit():
    summary = summarize_runs(sample_runs())
    assert summary["latency"] == {
        "known_runs": 6,
        "coverage": 1.0,
        "median_ms": 3.5,
        "p95_ms": 100.0,
        "timeouts": 1,
    }
    assert summary["tokens"] == {
        "complete_usage_runs": 2,
        "coverage": 2 / 6,
        "known_input_total": 22,
        "known_output_total": 5,
        "median_input": 11.0,
        "median_output": 2.5,
    }
    assert summary["safety"] == {"unsafe_acceptance": 1, "truncated_results": 1}
    assert summary["error_taxonomy"] == {
        "unclassified": 1,
        "unsafe_acceptance": 1,
        "wrong_filter_or_status": 1,
    }


def test_wilson_and_nearest_rank_edge_cases():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=0.0001)
    assert high == pytest.approx(0.7634, abs=0.0001)
    assert nearest_rank_percentile([], 95) is None
    assert nearest_rank_percentile([1, 2, 3, 100], 95) == 100
    with pytest.raises(ValueError):
        wilson_interval(2, 1)
    with pytest.raises(ValueError):
        nearest_rank_percentile([1], 101)


def test_llm_consistency_uses_result_fingerprints_not_sql_text():
    repeated = [
        {"case_id": "a", "execution_correct": True, "result_fingerprint": "rows:X"},
        {"case_id": "a", "execution_correct": True, "result_fingerprint": "rows:X"},
        {"case_id": "a", "execution_correct": True, "result_fingerprint": "rows:X"},
        {"case_id": "b", "execution_correct": True, "result_fingerprint": "rows:Y"},
        {"case_id": "b", "execution_correct": False, "result_fingerprint": "rows:Z"},
        {"case_id": "b", "execution_correct": False, "result_fingerprint": "rows:Z"},
    ]
    summary = summarize_consistency(repeated, expected_repeats=3)
    assert summary["total_cases"] == 2
    assert summary["complete_cases"] == 2
    assert summary["stable_correct_cases"] == 1
    assert summary["stable_correct_rate"] == 0.5
    assert summary["mean_result_agreement"] == pytest.approx((1 + 2 / 3) / 2)
    assert summary["per_case"]["a"]["correctness_rate"] == 1.0
    assert summary["per_case"]["b"]["correctness_rate"] == 1 / 3


def test_incomplete_repeats_are_visible_not_silently_dropped():
    summary = summarize_consistency([
        {"case_id": "a", "execution_correct": True, "result_fingerprint": "same"},
        {"case_id": "a", "execution_correct": True, "result_fingerprint": "same"},
    ])
    assert summary["complete_cases"] == 0
    assert summary["per_case"]["a"]["complete"] is False
    assert summary["per_case"]["a"]["stable_correct"] is False
