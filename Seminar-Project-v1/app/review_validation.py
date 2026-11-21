"""Pure validation for returned WMS independent-review forms.

Validation never edits artifacts or turns pending review into approval. It only
reports whether the evidence is complete enough to pass the next project gate.
"""
from __future__ import annotations

from datetime import date
from typing import Any


CORE_CASE_IDS = {f"wms_ref_{index:02d}" for index in range(1, 6)}
OVERALL_DECISIONS = {"approved", "approved_with_changes", "changes_required", "rejected"}
CASE_DECISIONS = {"approve", "change", "remove", "unknown"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _reviewer_issues(form: dict, prefix: str) -> list[str]:
    issues: list[str] = []
    reviewer = form.get("reviewer")
    if not isinstance(reviewer, dict):
        return [f"{prefix}.reviewer is missing"]
    for field in ("name", "role", "review_date"):
        if not _text(reviewer.get(field)):
            issues.append(f"{prefix}.reviewer.{field} is required")
    review_date = reviewer.get("review_date")
    if _text(review_date):
        try:
            date.fromisoformat(review_date)
        except ValueError:
            issues.append(f"{prefix}.reviewer.review_date must use YYYY-MM-DD")
    if reviewer.get("independent_from_rule_and_prompt_tuning") is not True:
        issues.append(f"{prefix}.reviewer must confirm independence")
    if reviewer.get("reviewed_before_seeing_system_outputs") is not True:
        issues.append(f"{prefix}.reviewer must confirm blinded review")
    return issues


def validate_core_review(form: dict) -> dict:
    issues = _reviewer_issues(form, "core")
    artifact_version = form.get("artifact_version")
    if not _text(artifact_version):
        issues.append("core.artifact_version is required")

    checks = form.get("artifact_checks")
    if not isinstance(checks, dict) or not checks:
        issues.append("core.artifact_checks are missing")
    else:
        for name, decision in checks.items():
            if decision != "approved":
                issues.append(f"core.artifact_checks.{name} is not approved")

    decisions = form.get("open_business_decisions")
    if not isinstance(decisions, dict) or not decisions:
        issues.append("core.open_business_decisions are missing")
    else:
        for name, entry in decisions.items():
            if not isinstance(entry, dict) or not _text(entry.get("decision")):
                issues.append(f"core.open_business_decisions.{name}.decision is required")
            if not isinstance(entry, dict) or not _text(entry.get("rationale")):
                issues.append(f"core.open_business_decisions.{name}.rationale is required")

    case_reviews = form.get("case_reviews")
    seen: set[str] = set()
    if not isinstance(case_reviews, list):
        issues.append("core.case_reviews are missing")
    else:
        for entry in case_reviews:
            case_id = entry.get("id") if isinstance(entry, dict) else None
            if not _text(case_id) or case_id in seen:
                issues.append("core.case_reviews contain a missing or duplicate id")
                continue
            seen.add(case_id)
            for field in ("question_is_unambiguous", "rules_match_question", "sql_is_correct",
                          "expected_result_is_correct", "ordering_flag_is_correct"):
                if entry.get(field) is not True:
                    issues.append(f"core.case_reviews.{case_id}.{field} is not true")
            if entry.get("decision") != "approve":
                issues.append(f"core.case_reviews.{case_id}.decision is not approve")
        missing = CORE_CASE_IDS - seen
        extra = seen - CORE_CASE_IDS
        if missing:
            issues.append("core.case_reviews missing: " + ", ".join(sorted(missing)))
        if extra:
            issues.append("core.case_reviews unknown: " + ", ".join(sorted(extra)))

    overall = form.get("overall")
    if not isinstance(overall, dict):
        issues.append("core.overall is missing")
        decision = None
    else:
        decision = overall.get("decision")
        if decision not in OVERALL_DECISIONS:
            issues.append("core.overall.decision is invalid or pending")
        if decision not in {"approved", "approved_with_changes"}:
            issues.append("core.overall.decision does not pass the gate")
        if overall.get("approved_artifact_version") != artifact_version:
            issues.append("core.overall.approved_artifact_version does not match artifact_version")
        if not _text(overall.get("reviewer_signoff")):
            issues.append("core.overall.reviewer_signoff is required")

    return {"valid": not issues, "gate_passed": not issues, "issues": issues,
            "artifact_version": artifact_version, "decision": decision}


def validate_candidate_review(form: dict, expected_case_ids: set[str],
                              expected_dataset_version: str) -> dict:
    issues = _reviewer_issues(form, "candidate")
    dataset_version = form.get("dataset_version")
    if dataset_version != expected_dataset_version:
        issues.append("candidate.dataset_version does not match the reviewed dataset")

    entries = form.get("cases")
    seen: set[str] = set()
    decision_counts = {decision: 0 for decision in sorted(CASE_DECISIONS)}
    if not isinstance(entries, list):
        issues.append("candidate.cases are missing")
    else:
        for entry in entries:
            case_id = entry.get("id") if isinstance(entry, dict) else None
            if not _text(case_id) or case_id in seen:
                issues.append("candidate.cases contain a missing or duplicate id")
                continue
            seen.add(case_id)
            for field in ("scope_label_correct", "family_and_reference_correct",
                          "natural_for_intended_user", "meaning_is_unambiguous",
                          "not_too_similar_to_another_case"):
                if entry.get(field) is not True:
                    issues.append(f"candidate.cases.{case_id}.{field} is not true")
            decision = entry.get("decision")
            if decision not in CASE_DECISIONS:
                issues.append(f"candidate.cases.{case_id}.decision is invalid or pending")
            else:
                decision_counts[decision] += 1
                if decision != "approve":
                    issues.append(f"candidate.cases.{case_id}.decision is {decision}")
        missing = expected_case_ids - seen
        extra = seen - expected_case_ids
        if missing:
            issues.append("candidate.cases missing: " + ", ".join(sorted(missing)))
        if extra:
            issues.append("candidate.cases unknown: " + ", ".join(sorted(extra)))

    overall = form.get("overall")
    if not isinstance(overall, dict):
        issues.append("candidate.overall is missing")
        overall_decision = None
    else:
        overall_decision = overall.get("decision")
        if overall_decision not in OVERALL_DECISIONS:
            issues.append("candidate.overall.decision is invalid or pending")
        if overall_decision not in {"approved", "approved_with_changes"}:
            issues.append("candidate.overall.decision does not pass the gate")
        if overall.get("approved_dataset_version") != expected_dataset_version:
            issues.append("candidate.overall.approved_dataset_version does not match dataset_version")
        if not _text(overall.get("reviewer_signoff")):
            issues.append("candidate.overall.reviewer_signoff is required")

    return {"valid": not issues, "gate_passed": not issues, "issues": issues,
            "dataset_version": dataset_version, "decision": overall_decision,
            "case_count": len(seen), "case_decisions": decision_counts}


def validate_review_pair(core: dict, candidate: dict, dataset: dict) -> dict:
    expected_ids = {case["id"] for case in dataset.get("cases", [])}
    core_result = validate_core_review(core)
    candidate_result = validate_candidate_review(
        candidate, expected_ids, dataset.get("dataset_version")
    )
    same_reviewer = (
        core.get("reviewer", {}).get("name") == candidate.get("reviewer", {}).get("name")
        and core.get("reviewer", {}).get("review_date") == candidate.get("reviewer", {}).get("review_date")
    )
    pair_issues = [] if same_reviewer else [
        "core and candidate forms must identify the same reviewer and review date"
    ]
    gate_passed = core_result["gate_passed"] and candidate_result["gate_passed"] and not pair_issues
    return {"validation_version": "1.0", "gate_passed": gate_passed,
            "core": core_result, "candidate": candidate_result,
            "pair_issues": pair_issues,
            "next_action": "freeze_reviewed_artifacts" if gate_passed else "resolve_review_issues"}
