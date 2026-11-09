"""Runs eval/test_set.yaml against the live pipeline and prints a coverage /
accuracy report. This is the loop you run after every lexicon change:

    python3 eval/run_eval.py

Coverage  = share of questions that got a non-UNMATCHED status (the rules
            recognized *something*, even if the checked result is wrong).
Accuracy  = share of questions whose result matched the declared `check`,
            among those that reached OK / the expected status.

Any FAIL is either a real bug (fix the code) or a documented gap (mark it
`note:` in test_set.yaml, like the two "Known gaps" entries) - never both.
"""
from __future__ import annotations
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.nlp.pipeline import run_pipeline, PipelineStatus  # noqa: E402
from tests.fixtures import fresh_conn  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent


def _check_passes(rows, check) -> bool:
    ops = {"eq": lambda a, b: a == b, "lte": lambda a, b: a <= b,
           "gte": lambda a, b: a >= b, "lt": lambda a, b: a < b, "gt": lambda a, b: a > b}
    t = check["type"]
    if t == "row_count":
        return ops[check["op"]](len(rows), check["value"])
    if t == "cell_equals":
        return rows[check["row"]][check["col"]] == check["value"]
    if t == "all_rows_satisfy":
        return all(ops[check["op"]](row[check["column"]], check["value"]) for row in rows)
    raise ValueError(f"unknown check type {t!r}")


def main() -> int:
    cases = yaml.safe_load((ROOT / "test_set.yaml").read_text(encoding="utf-8"))["cases"]
    conn = fresh_conn()

    total = len(cases)
    matched = 0     # non-UNMATCHED
    correct = 0     # status + check both right
    failures = []

    for case in cases:
        q = case["question"]
        expected_status = case["expect_status"]
        result = run_pipeline(q, conn)
        got_status = result.status.value

        if got_status != "unmatched":
            matched += 1

        ok = got_status == expected_status
        if ok and expected_status == "ok" and "check" in case:
            ok = _check_passes(result.rows, case["check"])

        if ok:
            correct += 1
        else:
            failures.append((q, expected_status, got_status, case.get("note"), result.message))

    print(f"Total cases:  {total}")
    print(f"Coverage:     {matched}/{total} ({100*matched/total:.0f}%) - matched *some* rule")
    print(f"Accuracy:     {correct}/{total} ({100*correct/total:.0f}%) - matched AND correct")
    print()

    if failures:
        print("--- Failures / documented gaps ---")
        for q, exp, got, note, msg in failures:
            tag = "GAP (documented)" if note else "FAIL"
            print(f"[{tag}] {q!r}")
            print(f"    expected={exp}  got={got}" + (f"  ({msg})" if msg else ""))
            if note:
                print(f"    note: {note}")
        print()

    undocumented_fails = [f for f in failures if not f[3]]
    if undocumented_fails:
        print(f"{len(undocumented_fails)} UNDOCUMENTED failure(s) - these are real bugs, not known gaps.")
        return 1

    print("All non-gap cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
