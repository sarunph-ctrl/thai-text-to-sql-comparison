"""Pure evaluation metrics for paired WMS Rule-based/LLM experiments.

The functions consume already-recorded case runs. They never call a model,
execute SQL, or inspect held-out questions, which keeps metric calculation
separate from system tuning and data collection.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil, sqrt
from statistics import median
from typing import Any, Iterable


ERROR_CATEGORIES = {
    "intent_missed",
    "condition_dropped",
    "wrong_table_or_join",
    "wrong_filter_or_status",
    "wrong_date_boundary",
    "wrong_aggregation_or_grouping",
    "wrong_zero_or_null_handling",
    "invalid_or_rejected_sql",
    "database_error_or_timeout",
    "incorrect_unsupported",
    "unsafe_acceptance",
    "truncated_result",
}


def _rate(successes: int, total: int) -> float | None:
    return successes / total if total else None


def wilson_interval(successes: int, total: int, *, z: float = 1.96) -> tuple[float, float] | None:
    """Return the two-sided Wilson score interval for a binomial proportion."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes and total must satisfy 0 <= successes <= total")
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def nearest_rank_percentile(values: Iterable[float], percentile: float) -> float | None:
    """Use the deterministic nearest-rank definition; percentile is in [0, 100]."""
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    rank = max(1, ceil(percentile / 100 * len(ordered)))
    return ordered[rank - 1]


def _known_integer(run: dict[str, Any], field: str) -> int | None:
    value = run.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def summarize_runs(runs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize correctness, safety, latency, tokens, and primary errors."""
    records = list(runs)
    in_scope = [run for run in records if run.get("scope_label") == "in_scope"]
    out_scope = [run for run in records if run.get("scope_label") == "out_of_scope"]

    execution_correct = sum(bool(run.get("execution_correct")) for run in in_scope)
    correct_rejections = sum(
        run.get("status") == "unsupported" and not bool(run.get("sql_executed"))
        for run in out_scope
    )
    valid_sql = sum(run.get("sql_valid") is True for run in in_scope)

    latencies = [
        float(run["method_ms"])
        for run in records
        if isinstance(run.get("method_ms"), (int, float))
        and not isinstance(run.get("method_ms"), bool)
        and run["method_ms"] >= 0
    ]

    input_tokens = [value for run in records if (value := _known_integer(run, "input_tokens")) is not None]
    output_tokens = [value for run in records if (value := _known_integer(run, "output_tokens")) is not None]
    complete_usage = [
        run for run in records
        if _known_integer(run, "input_tokens") is not None
        and _known_integer(run, "output_tokens") is not None
    ]

    errors: Counter[str] = Counter()
    for run in records:
        category = run.get("error_category")
        if category:
            errors[category if category in ERROR_CATEGORIES else "unclassified"] += 1

    interval = wilson_interval(execution_correct, len(in_scope))
    rejection_interval = wilson_interval(correct_rejections, len(out_scope))
    return {
        "total_runs": len(records),
        "in_scope": {
            "total": len(in_scope),
            "execution_correct": execution_correct,
            "execution_accuracy": _rate(execution_correct, len(in_scope)),
            "execution_accuracy_wilson95": list(interval) if interval else None,
            "valid_sql": valid_sql,
            "valid_sql_rate": _rate(valid_sql, len(in_scope)),
        },
        "out_of_scope": {
            "total": len(out_scope),
            "correct_rejections": correct_rejections,
            "rejection_accuracy": _rate(correct_rejections, len(out_scope)),
            "rejection_accuracy_wilson95": list(rejection_interval) if rejection_interval else None,
        },
        "latency": {
            "known_runs": len(latencies),
            "coverage": _rate(len(latencies), len(records)),
            "median_ms": median(latencies) if latencies else None,
            "p95_ms": nearest_rank_percentile(latencies, 95),
            "timeouts": sum(bool(run.get("timed_out")) for run in records),
        },
        "tokens": {
            "complete_usage_runs": len(complete_usage),
            "coverage": _rate(len(complete_usage), len(records)),
            "known_input_total": sum(input_tokens),
            "known_output_total": sum(output_tokens),
            "median_input": median(input_tokens) if input_tokens else None,
            "median_output": median(output_tokens) if output_tokens else None,
        },
        "safety": {
            "unsafe_acceptance": sum(
                run.get("scope_label") == "out_of_scope" and bool(run.get("sql_executed"))
                for run in records
            ),
            "truncated_results": sum(bool(run.get("truncated")) for run in records),
        },
        "error_taxonomy": dict(sorted(errors.items())),
    }


def summarize_consistency(runs: Iterable[dict[str, Any]], *, expected_repeats: int = 3) -> dict[str, Any]:
    """Summarize repeated LLM runs grouped by case_id.

    result_fingerprint must represent the normalized result/status of a run,
    never raw SQL text, because different SQL can return the same answer.
    """
    if expected_repeats < 2:
        raise ValueError("expected_repeats must be at least 2")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        case_id = run.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("every repeated run needs a non-empty case_id")
        groups[case_id].append(run)

    per_case: dict[str, Any] = {}
    complete_cases = 0
    stable_correct = 0
    agreements: list[float] = []
    for case_id, case_runs in sorted(groups.items()):
        repeat_count = len(case_runs)
        is_complete = repeat_count == expected_repeats
        complete_cases += int(is_complete)
        correct_count = sum(bool(run.get("execution_correct")) for run in case_runs)
        fingerprints = [run.get("result_fingerprint") for run in case_runs]
        known_fingerprints = [value for value in fingerprints if isinstance(value, str) and value]
        agreement = (
            max(Counter(known_fingerprints).values()) / repeat_count
            if len(known_fingerprints) == repeat_count and repeat_count
            else None
        )
        if agreement is not None:
            agreements.append(agreement)
        case_stable_correct = is_complete and correct_count == expected_repeats
        stable_correct += int(case_stable_correct)
        per_case[case_id] = {
            "repeat_count": repeat_count,
            "complete": is_complete,
            "correct_count": correct_count,
            "correctness_rate": _rate(correct_count, repeat_count),
            "stable_correct": case_stable_correct,
            "result_agreement": agreement,
        }

    total_cases = len(groups)
    return {
        "expected_repeats": expected_repeats,
        "total_cases": total_cases,
        "complete_cases": complete_cases,
        "stable_correct_cases": stable_correct,
        "stable_correct_rate": _rate(stable_correct, total_cases),
        "mean_result_agreement": sum(agreements) / len(agreements) if agreements else None,
        "per_case": per_case,
    }
