"""Development smoke checks, NOT a held-out research benchmark.

Each successful query is compared to the full result of independently
authored SQL in db/demo_reference.sql on the same database snapshot.
"""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
import sys
from zoneinfo import ZoneInfo

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.demo_api import database_url, jsonable
from app.nlp.demo import run_demo_pipeline

CASES = [
    ("ยอดขายเดือนกันยายน 2569", 0),
    ("ยอดขายเดือนกันยายน 2569 เท่าไหร่", 0),
    ("ยอดขายเดือนกันยายน 2026", 0),
    ("ยอดขายเดือนกันยายน ๒๕๖๙", 0),
    ("ยอดขายเดือนกันยายน ปี 2569", 0),
    ("ยอดขายเดือนกันยายน 2569 แยกตามสินค้า", 1),
    ("เดือนกันยายน 2569 สินค้าแต่ละตัวขายได้เงินเท่าไหร่", 1),
    ("สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569", 2),
    ("เปรียบเทียบยอดขายเดือนนี้กับเดือนที่แล้ว", None),
    ("ยอดขายเดือนกันยายน 2569 ของลูกค้าสมชาย", None),
    ("ยอดขายเดือนกันยายน 2569 ที่มากกว่า 100 บาท", None),
    ("ยอดขายเดือนนี้", None),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    records = []
    with psycopg.connect(database_url(), autocommit=True) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            queries = [q for q in (ROOT / "db/demo_reference.sql").read_text(encoding="utf-8").split(";") if q.strip()]
            reference = [conn.execute(q).fetchall() for q in queries]
            # Pipeline uses a nested transaction here (a savepoint). The outer
            # read-only transaction pins both predictions and references.
            for question, ref_index in CASES:
                result = run_demo_pipeline(question, conn)
                expected = reference[ref_index] if ref_index is not None else None
                passed = ((result.status == "ok" and result.rows == expected) if expected is not None
                          else result.status == "unsupported" and result.sql is None)
                records.append({"question": question, "kind": "query" if expected is not None else "scope_rejection",
                                "passed": passed, "expected_rows": expected, "result": asdict(result)})
                print(f"{'PASS' if passed else 'FAIL'}  {question}")
    supported = [r for r in records if r["kind"] == "query"]
    rejection = [r for r in records if r["kind"] == "scope_rejection"]
    report = {"evaluated_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
              "dataset": "day1-development-smoke (not held-out)",
              "correct_queries": sum(r["passed"] for r in supported), "total_queries": len(supported),
              "correct_rejections": sum(r["passed"] for r in rejection), "total_rejections": len(rejection),
              "cases": records}
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    (out / "day1-report.json").write_text(json.dumps(jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nQueries matching full reference result: {report['correct_queries']}/{len(supported)}")
    print(f"Scope rejections: {report['correct_rejections']}/{len(rejection)} (reported separately)")
    print("Saved output/day1-report.json")
    return 0 if all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
