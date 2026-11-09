"""Ask a question and print the actual reasoning trace, SQL and DB result."""
from dataclasses import asdict
import argparse
import json
import sys

import psycopg

from app.demo_api import database_url, jsonable
from app.nlp.demo import run_demo_pipeline


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="?", default="ยอดขายเดือนกันยายน 2569")
    args = parser.parse_args()
    with psycopg.connect(database_url(), autocommit=True) as conn:
        result = run_demo_pipeline(args.text, conn)
    print(json.dumps(jsonable(asdict(result)), ensure_ascii=False, indent=2))
    return 0 if result.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
