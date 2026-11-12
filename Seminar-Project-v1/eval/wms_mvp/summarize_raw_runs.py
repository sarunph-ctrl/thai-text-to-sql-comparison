"""Summarize validated WMS JSONL runs without reading evaluation questions.

Example:
  python eval/wms_mvp/summarize_raw_runs.py --input output/wms_mvp/raw/run.jsonl
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.evaluation_metrics import summarize_consistency, summarize_runs
from app.evaluation_records import group_by_method, read_jsonl


def build_summary(records):
    report = {
        "summary_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
        "methods": {},
    }
    for method, method_records in group_by_method(records).items():
        section = {"metrics": summarize_runs(method_records)}
        if method == "llm" and method_records:
            section["consistency"] = summarize_consistency(method_records, expected_repeats=3)
        report["methods"][method] = section
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Validated JSONL raw runs")
    parser.add_argument("--output", type=Path, help="Optional JSON summary path")
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing summary")
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"input file not found: {args.input}")
    if args.output and args.output.exists() and not args.force:
        parser.error("output already exists; pass --force or choose a new path")

    report = build_summary(read_jsonl(args.input))
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
