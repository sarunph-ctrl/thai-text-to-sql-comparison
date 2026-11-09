"""Development checks of the five-table demo, not a held-out benchmark."""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.demo_api import database_url, jsonable
from app.nlp.demo import run_demo_pipeline

CASES = [
    ("สินค้าคงเหลือแยกตามคลังมีเท่าไหร่", 0),
    ("แสดงสต็อกคงเหลือแยกตามคลังครับ", 0),
    ("สินค้าคงเหลือในแต่ละคลัง", 0),
    ("เดือนกันยายน 2569 มีสินค้าจ่ายออกแต่ละชนิดกี่หน่วย", 1),
    ("ยอดจ่ายออกสินค้าเดือนกันยายน 2569", 1),
    ("เดือนกันยายน ๒๕๖๙ สินค้าเบิกออกกี่ชิ้น", 1),
    ("สินค้าคงเหลือเดือนกันยายน 2569", None),
    ("สินค้าคงเหลือเฉพาะคลังหลัก", None),
    ("สินค้าจ่ายออกเดือนนี้", None),
    ("เดือนกันยายน 2569 สินค้าจ่ายออกที่ชำระแล้ว", None),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    records = []
    with psycopg.connect(database_url(), autocommit=True) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            queries = [q for q in (ROOT / "db/demo_inventory_reference.sql").read_text(encoding="utf-8").split(";") if q.strip()]
            references = [conn.execute(q).fetchall() for q in queries]
            for question, index in CASES:
                result = run_demo_pipeline(question, conn)
                expected = references[index] if index is not None else None
                passed = (result.status == "ok" and result.rows == expected) if index is not None else (
                    result.status == "unsupported" and result.sql is None)
                records.append({"question": question, "kind": "query" if index is not None else "scope_rejection",
                                "passed": passed, "expected_rows": expected, "result": asdict(result)})
                print(f"{'PASS' if passed else 'FAIL'}  {question}")
    queries = [r for r in records if r["kind"] == "query"]
    rejects = [r for r in records if r["kind"] == "scope_rejection"]
    report = {"evaluated_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
              "dataset": "inventory-development-smoke (not held-out)",
              "correct_queries": sum(r["passed"] for r in queries), "total_queries": len(queries),
              "correct_rejections": sum(r["passed"] for r in rejects), "total_rejections": len(rejects),
              "cases": records}
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    (output / "inventory-report.json").write_text(json.dumps(jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Full reference matches: {report['correct_queries']}/{len(queries)}")
    print(f"Scope rejections: {report['correct_rejections']}/{len(rejects)} (separate)")
    return 0 if all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
