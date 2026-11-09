"""Frozen-input exploratory comparison. Run --freeze first; default is rule-only.

python eval/run_sprint2.py --freeze
python eval/run_sprint2.py --split dev --method rule
python eval/run_sprint2.py --split test --method both
"""
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import argparse
import json
from pathlib import Path
import statistics
import sys
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
import sqlglot
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.demo_api import database_url, jsonable
from app.llm.client import configuration_status
from app.llm.comparison import resultsets_equal
from app.llm.pipeline import run_llm_pipeline
from app.llm.prompt import prompt_bundle, TABLE_COLUMNS
from app.nlp.demo import run_demo_pipeline

DATA = ROOT / "eval/sprint2"
MANIFEST = DATA / "manifest.json"


def source_hashes():
    paths = [*sorted((ROOT / "app").rglob("*.py")), *sorted((ROOT / "config").glob("*.yaml")),
             *sorted(DATA.glob("*.yaml")), *sorted((ROOT / "db").glob("demo*.sql")), Path(__file__)]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p.read_bytes()).hexdigest() for p in paths}


def freeze():
    if MANIFEST.exists():
        raise RuntimeError("Manifest already exists. Preserve it; use a new experiment version if inputs change.")
    manifest = {"frozen_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
                "source_sha256": source_hashes(), "configuration": configuration_status(),
                "prompt_sha256_for_placeholder": prompt_bundle("manifest placeholder")["prompt_sha256"],
                "dataset_note": "AI-authored exploratory evaluation, not an independent benchmark"}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Frozen source/prompt/model metadata in eval/sprint2/manifest.json (no API key)")


def check_manifest():
    if not MANIFEST.exists():
        raise RuntimeError("Run --freeze before evaluating")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = source_hashes()
    if current != manifest["source_sha256"]:
        changed = sorted(k for k in set(current) | set(manifest["source_sha256"])
                         if current.get(k) != manifest["source_sha256"].get(k))
        raise RuntimeError("Frozen sources changed: " + ", ".join(changed))
    conf = configuration_status()
    for key in ("provider", "requested_model", "temperature", "max_output_tokens", "base_url"):
        if conf.get(key) != manifest["configuration"].get(key):
            raise RuntimeError("Frozen model setting changed: " + key)
    return manifest


def canonical(query):
    try:
        return sqlglot.parse_one(query, read="postgres").sql(dialect="postgres", normalize=True)
    except (sqlglot.errors.SqlglotError, TypeError):
        return None


def evaluate_candidate(result, expected_rows, expected_columns, reference, ordered, expanded_sql=None):
    runnable = result["status"] == "ok"
    correct = runnable and resultsets_equal(result["rows"], expected_rows,
        actual_columns=len(result["columns"]), expected_columns=len(expected_columns), ordered=ordered)
    query = expanded_sql or result.get("generated_sql")
    exact = bool(runnable and query and canonical(query) == canonical(reference))
    return {"execution_correct": bool(correct), "sql_ran_successfully": runnable,
            "canonical_sql_exact_match": exact, "result": result}


def summarize(records, method):
    outcomes = [r[method] for r in records if method in r]
    latencies = [r["result"]["elapsed_ms"] for r in outcomes if r["result"].get("elapsed_ms") is not None]
    summary = {"total": len(outcomes), "execution_correct": sum(r["execution_correct"] for r in outcomes),
               "execution_accuracy": sum(r["execution_correct"] for r in outcomes) / len(outcomes),
               "sql_ran_successfully": sum(r["sql_ran_successfully"] for r in outcomes),
               "canonical_sql_exact_match": sum(r["canonical_sql_exact_match"] for r in outcomes),
               "mean_method_ms": round(statistics.mean(latencies), 3) if latencies else None,
               "median_method_ms": round(statistics.median(latencies), 3) if latencies else None}
    if method == "llm":
        usages = [r["result"].get("generation") or {} for r in outcomes]
        complete = all(isinstance(u.get("input_tokens"), int) and isinstance(u.get("output_tokens"), int) for u in usages)
        summary.update({"token_usage_complete": complete,
            "known_input_tokens": sum(u.get("input_tokens") or 0 for u in usages),
            "known_output_tokens": sum(u.get("output_tokens") or 0 for u in usages),
            "currency_cost": None, "currency_cost_per_300": None,
            "cost_note": "IntelSphere quota/billing rate unknown; do not treat unknown cost as zero"})
    return summary


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--method", choices=["rule", "both"], default="rule")
    args = parser.parse_args()
    if args.freeze:
        freeze()
        return 0
    manifest = check_manifest()
    dataset = yaml.safe_load((DATA / f"{args.split}.yaml").read_text(encoding="utf-8"))
    references = yaml.safe_load((DATA / "references.yaml").read_text(encoding="utf-8"))
    if args.method == "both" and not configuration_status()["configured"]:
        raise RuntimeError("IntelSphere key is not configured; no evaluation calls made")
    records, snapshot_rows = [], {}
    with psycopg.connect(database_url(), autocommit=True) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            for table in sorted(TABLE_COLUMNS):
                snapshot_rows[table] = conn.execute(sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(table))).fetchall()
            for case in dataset["cases"]:
                reference = references[case["reference"]]
                cur = conn.execute(reference)
                expected = cur.fetchall()
                cols = [c.name for c in cur.description]
                record = {**case, "reference_sql": reference, "expected_columns": cols, "expected_rows": expected}
                rule = asdict(run_demo_pipeline(case["question"], conn))
                expanded = None
                if rule.get("sql"):
                    with psycopg.ClientCursor(conn) as render:
                        expanded = render.mogrify(rule["sql"], rule["params"])
                record["rule"] = evaluate_candidate(rule, expected, cols, reference, case["ordered"], expanded)
                if args.method == "both":
                    llm = run_llm_pipeline(case["question"], conn)
                    record["llm"] = evaluate_candidate(llm, expected, cols, reference, case["ordered"])
                records.append(record)
                statuses = " ".join(f"{m}={'correct' if record[m]['execution_correct'] else record[m]['result']['status'] + '/wrong'}"
                                    for m in ("rule", "llm") if m in record)
                print(f"{case['id']}: {statuses} | {case['question']}", flush=True)
    timestamp = datetime.now(ZoneInfo("Asia/Bangkok"))
    report = {"evaluated_at": timestamp.isoformat(), "split": args.split, "method": args.method,
              "dataset_note": dataset["description"], "prompt_version": prompt_bundle("manifest placeholder")["version"],
              "configuration": configuration_status(), "manifest_sha256": sha256(MANIFEST.read_bytes()).hexdigest(),
              "data_snapshot_sha256": sha256(json.dumps(jsonable(snapshot_rows), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
              "snapshot_row_counts": {k: len(v) for k, v in snapshot_rows.items()},
              "summary": {"rule": summarize(records, "rule")}, "cases": records,
              "metric_notes": ["Execution accuracy uses ALL questions in the split, including rejected/failed queries.",
                  "Compare numeric values and duplicate rows; top-N order matters. Column aliases are not scored.",
                  "Canonical SQL match is syntax-only; equivalent SQL with different aliases/LIMIT may not match.",
                  "Method latency excludes DB connection startup; LLM includes generation, validation and execution.",
                  "No fallback, retries or automatic repair; one model call per question.",
                  "AI-authored synthetic data and questions do not establish real-world WMS validity."]}
    if args.method == "both":
        report["summary"]["llm"] = summarize(records, "llm")
    output = ROOT / "output/sprint2"
    output.mkdir(exist_ok=True)
    stem = f"{args.split}-{args.method}-{timestamp:%Y%m%d-%H%M%S}"
    encoded = json.dumps(jsonable(report), ensure_ascii=False, indent=2)
    (output / f"{stem}.json").write_text(encoded, encoding="utf-8")
    (output / f"latest-{args.split}-{args.method}.json").write_text(encoded, encoding="utf-8")
    lines = ["# Sprint 2 — Exploratory comparison", "", dataset["description"], "",
             "| Method | Execution correct | Mean method latency (ms) |", "|---|---:|---:|"]
    for method, summary in report["summary"].items():
        lines.append(f"| {method} | {summary['execution_correct']}/{summary['total']} | {summary['mean_method_ms']} |")
    lines.extend(["", "Currency cost remains unknown. This is not an independent benchmark.", "",
                  "## Per-question results", "", "| ID | Question | Rule | LLM |", "|---|---|---|---|"])
    for r in records:
        label = lambda m: ("correct" if r[m]["execution_correct"] else r[m]["result"]["status"] + "/wrong") if m in r else "not run"
        lines.append(f"| {r['id']} | {r['question']} | {label('rule')} | {label('llm')} |")
    (output / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / f"latest-{args.split}-{args.method}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("Report:", output / f"{stem}.json")
    return 0  # Incorrect predictions are research outcomes, not harness crashes.


if __name__ == "__main__":
    raise SystemExit(main())
