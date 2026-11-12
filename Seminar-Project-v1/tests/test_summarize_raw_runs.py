"""The CLI summary uses the frozen metric engine and never needs questions."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "eval/wms_mvp/summarize_raw_runs.py"
SPEC = spec_from_file_location("summarize_raw_runs", SCRIPT)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def run(case_id, method, repeat, correct, fingerprint):
    return {
        "case_id": case_id,
        "method": method,
        "repeat_index": repeat,
        "scope_label": "in_scope",
        "status": "ok",
        "execution_correct": correct,
        "sql_valid": True,
        "sql_executed": True,
        "method_ms": repeat,
        "result_fingerprint": fingerprint,
    }


def test_summary_separates_methods_and_adds_llm_consistency_only():
    records = [
        run("c1", "rule", 1, True, "r"),
        run("c1", "llm", 1, True, "x"),
        run("c1", "llm", 2, True, "x"),
        run("c1", "llm", 3, True, "x"),
    ]
    report = MODULE.build_summary(records)
    assert report["total_records"] == 4
    assert report["methods"]["rule"]["metrics"]["in_scope"]["execution_accuracy"] == 1
    assert "consistency" not in report["methods"]["rule"]
    assert report["methods"]["llm"]["consistency"]["stable_correct_rate"] == 1
