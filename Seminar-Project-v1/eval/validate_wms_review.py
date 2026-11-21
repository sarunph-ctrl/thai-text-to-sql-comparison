"""Validate returned WMS review forms without changing project artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.review_validation import validate_review_pair


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML object: {path}")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path,
                        help="Completed 01_core/review_record.yaml")
    parser.add_argument("--candidate", required=True, type=Path,
                        help="Completed 02_questions/candidate_review_record.yaml")
    parser.add_argument("--dataset", type=Path,
                        default=ROOT / "eval/wms_mvp/dev.candidate.yaml")
    parser.add_argument("--output", type=Path, help="Optional JSON validation report")
    args = parser.parse_args(argv)
    for path in (args.core, args.candidate, args.dataset):
        if not path.is_file():
            parser.error(f"file not found: {path}")

    result = validate_review_pair(
        load_yaml(args.core), load_yaml(args.candidate), load_yaml(args.dataset)
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            parser.error("output already exists; choose a new path")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
