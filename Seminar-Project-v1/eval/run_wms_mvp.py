"""Record reproducible WMS MVP development runs as secret-resistant JSONL.

Examples:
  python eval/run_wms_mvp.py --ack-draft --method rule --snapshot v1
  python eval/run_wms_mvp.py --ack-draft --method both --snapshot v2

The candidate dataset is pending independent review. This command never labels
its output as a held-out benchmark and never calls an LLM unless requested.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
import yaml


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.demo_api import jsonable
from app.evaluation_metrics import summarize_consistency, summarize_runs
from app.evaluation_records import append_jsonl
from app.llm.comparison import resultsets_equal
from app.wms.pipeline import run_wms_rule_pipeline
from app.wms_llm.pipeline import run_wms_llm_pipeline
from scripts.local_demo import connection_string


DATA = ROOT / "eval/wms_mvp"
SNAPSHOTS = {"v1": ("wms_seed_v1", "wms_mvp_seed.sql"),
             "v2": ("wms_seed_v2", "wms_mvp_seed_v2.sql")}


def sha256_lf(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return sha256(text.encode("utf-8")).hexdigest()


def verify_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("algorithm") != "sha256-lf" or not isinstance(manifest.get("files"), dict):
        raise RuntimeError(f"Unsupported manifest format: {path}")
    mismatches = []
    for relative, expected in manifest["files"].items():
        source = ROOT / relative
        actual = sha256_lf(source) if source.is_file() else None
        if actual != expected:
            mismatches.append(relative)
    if mismatches:
        raise RuntimeError("Frozen inputs changed: " + ", ".join(mismatches))
    return manifest


def verify_frozen_inputs(snapshot: str) -> dict:
    primary = verify_manifest(DATA / "manifest.json")
    candidate = verify_manifest(DATA / "dev_candidate_manifest.json")
    robustness = verify_manifest(DATA / "snapshot_v2_manifest.json") if snapshot == "v2" else None
    return {"primary": primary, "candidate": candidate, "snapshot": robustness}


def current_commit() -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, timeout=5)
    return result.stdout.strip() if result.returncode == 0 else None


def working_tree_is_clean() -> bool:
    result = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, timeout=5)
    return result.returncode == 0 and not result.stdout.strip()


def open_snapshot(seed_file: str) -> tuple[psycopg.Connection, str]:
    conn = psycopg.connect(connection_string(admin=True, database="seminar_tests"), autocommit=True)
    schema = "eval_" + uuid4().hex
    try:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        conn.execute((ROOT / "db/wms_mvp_schema.sql").read_text(encoding="utf-8"))
        conn.execute((ROOT / "db" / seed_file).read_text(encoding="utf-8"))
    except Exception:
        conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        conn.close()
        raise
    return conn, schema


def close_snapshot(conn: psycopg.Connection, schema: str) -> None:
    if not conn.closed:
        conn.rollback()
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.close()


def reference_result(conn: psycopg.Connection, reference: dict) -> tuple[list[str], list]:
    cursor = conn.execute(reference["sql"], reference.get("params") or {})
    return [column.name for column in cursor.description], cursor.fetchall()


def is_execution_correct(result: dict, case: dict, expected_columns: list[str],
                         expected_rows: list) -> bool:
    if case["scope_label"] == "out_of_scope":
        return result.get("status") == "unsupported" and not result.get("sql_executed", False)
    return (
        result.get("status") == "ok"
        and result.get("columns") == expected_columns
        and resultsets_equal(
            result.get("rows") or [], expected_rows,
            actual_columns=len(result.get("columns") or []),
            expected_columns=len(expected_columns), ordered=case["ordered"],
        )
    )


def error_category(result: dict, case: dict, correct: bool) -> str | None:
    if correct:
        return None
    if case["scope_label"] == "out_of_scope" and result.get("sql_executed"):
        return "unsafe_acceptance"
    if case["scope_label"] == "in_scope" and result.get("status") == "unsupported":
        return "incorrect_unsupported"
    if result.get("status") == "blocked" or result.get("sql_valid") is False:
        return "invalid_or_rejected_sql"
    if result.get("status") == "sql_error":
        return "database_error_or_timeout"
    if result.get("truncated"):
        return "truncated_result"
    return None  # semantic errors require manual taxonomy review


def make_record(*, experiment_id: str, case: dict, snapshot_id: str, method: str,
                repeat_index: int, result: dict, expected_columns: list[str],
                expected_rows: list, commit: str | None) -> dict:
    correct = is_execution_correct(result, case, expected_columns, expected_rows)
    generation = result.get("generation") or {}
    message = result.get("message") or result.get("reason")
    return {
        "experiment_id": experiment_id,
        "case_id": case["id"],
        "split": "development",
        "snapshot_id": snapshot_id,
        "method": method,
        "repeat_index": repeat_index,
        "scope_label": case["scope_label"],
        "status": result.get("status", "error"),
        "execution_correct": correct,
        "sql_valid": result.get("sql_valid"),
        "sql_executed": bool(result.get("sql_executed", False)),
        "columns": list(result.get("columns") or []),
        "rows": jsonable(result.get("rows") or []),
        "ordered": bool(case["ordered"]),
        "method_ms": result.get("elapsed_ms"),
        "code_commit": commit,
        "family": case.get("family"),
        "generated_sql": result.get("generated_sql") or result.get("sql"),
        "generation_ms": generation.get("generation_ms"),
        "validation_ms": result.get("validation_ms"),
        "database_ms": result.get("database_ms"),
        "input_tokens": generation.get("input_tokens"),
        "output_tokens": generation.get("output_tokens"),
        "timed_out": bool(message and "timeout" in message.casefold()),
        "truncated": bool(result.get("truncated", False)),
        "error_category": error_category(result, case, correct),
        "message": str(message)[:1000] if message else None,
        "provider": generation.get("provider"),
        "model": generation.get("returned_model") or generation.get("requested_model"),
        "prompt_version": result.get("prompt_version"),
        "retries": generation.get("retries"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-draft", action="store_true",
                        help="Acknowledge candidate questions and ground truth await independent review")
    parser.add_argument("--method", choices=["rule", "llm", "both"], default="rule")
    parser.add_argument("--snapshot", choices=sorted(SNAPSHOTS), default="v1")
    parser.add_argument("--llm-repeats", type=int, default=3)
    parser.add_argument("--shuffle-seed", type=int, default=20261120)
    parser.add_argument("--output", type=Path,
                        help="Raw JSONL path; defaults inside gitignored output/wms_mvp/raw")
    parser.add_argument("--continue-provider-errors", action="store_true",
                        help="Continue after provider/configuration errors; may consume many failed calls")
    parser.add_argument("--allow-dirty-smoke", action="store_true",
                        help="Allow a non-reproducible development smoke run from a dirty worktree")
    args = parser.parse_args(argv)
    if not args.ack_draft:
        parser.error("pass --ack-draft: this is a development candidate, not held-out evaluation")
    if args.llm_repeats < 1 or args.llm_repeats > 10:
        parser.error("--llm-repeats must be between 1 and 10")
    if not working_tree_is_clean() and not args.allow_dirty_smoke:
        parser.error("working tree is not clean; commit first or use --allow-dirty-smoke for a non-final smoke run")

    manifests = verify_frozen_inputs(args.snapshot)
    snapshot_id, seed_file = SNAPSHOTS[args.snapshot]
    dataset = yaml.safe_load((DATA / "dev.candidate.yaml").read_text(encoding="utf-8"))
    references = {case["id"]: case for case in yaml.safe_load(
        (DATA / "ground_truth.yaml").read_text(encoding="utf-8"))["cases"]}
    cases = list(dataset["cases"])
    random.Random(args.shuffle_seed).shuffle(cases)

    timestamp = datetime.now(ZoneInfo("Asia/Bangkok"))
    experiment_id = f"wms-mvp-development-{snapshot_id}-{timestamp:%Y%m%d-%H%M%S}"
    if args.allow_dirty_smoke and not working_tree_is_clean():
        experiment_id += "-dirty-smoke"
    output = args.output or ROOT / "output/wms_mvp/raw" / f"{experiment_id}-{args.method}.jsonl"
    if output.exists():
        raise RuntimeError(f"Refusing to append to existing run: {output}")
    commit = current_commit()
    recorded = []
    conn, eval_schema = open_snapshot(seed_file)
    try:
        expected: dict[str, tuple[list[str], list]] = {}
        for reference_id, reference in references.items():
            expected[reference_id] = reference_result(conn, reference)

        for case in cases:
            if case["scope_label"] == "in_scope":
                expected_columns, expected_rows = expected[case["reference_id"]]
            else:
                expected_columns, expected_rows = [], []

            methods = ["rule", "llm"] if args.method == "both" else [args.method]
            for method in methods:
                repeats = args.llm_repeats if method == "llm" else 1
                for repeat_index in range(1, repeats + 1):
                    if method == "rule":
                        raw = run_wms_rule_pipeline(case["question"], conn)
                        result = vars(raw)
                    else:
                        result = run_wms_llm_pipeline(case["question"], conn)
                    record = make_record(
                        experiment_id=experiment_id, case=case, snapshot_id=snapshot_id,
                        method=method, repeat_index=repeat_index, result=result,
                        expected_columns=expected_columns, expected_rows=expected_rows,
                        commit=commit,
                    )
                    finalized = append_jsonl(output, record)
                    recorded.append(finalized)
                    label = "correct" if finalized["execution_correct"] else finalized["status"] + "/wrong"
                    print(f"{case['id']} {method}#{repeat_index}: {label}", flush=True)
                    if (method == "llm" and result.get("status") in {"not_configured", "llm_error"}
                            and not result.get("generation") and not args.continue_provider_errors):
                        raise RuntimeError(
                            "Provider/configuration failed before model output; stopped after one recorded call. "
                            "Fix credentials or pass --continue-provider-errors explicitly."
                        )
    finally:
        close_snapshot(conn, eval_schema)

    summary = {}
    for method in ("rule", "llm"):
        method_records = [record for record in recorded if record["method"] == method]
        if method_records:
            summary[method] = {"metrics": summarize_runs(method_records)}
            if method == "llm" and args.llm_repeats >= 2:
                summary[method]["consistency"] = summarize_consistency(
                    method_records, expected_repeats=args.llm_repeats
                )
    print(json.dumps({
        "experiment_id": experiment_id,
        "dataset_status": dataset["status"],
        "review_status": manifests["candidate"]["review_status"],
        "shuffle_seed": args.shuffle_seed,
        "raw_output": str(output),
        "summary": summary,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
