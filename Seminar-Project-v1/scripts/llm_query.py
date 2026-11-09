"""Run one IntelSphere question, or export the exact zero-shot prompt."""
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import sys

import psycopg

from app.demo_api import database_url, jsonable
from app.llm.client import generate
from app.llm.pipeline import run_llm_pipeline
from app.llm.prompt import prompt_bundle


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default="ยอดขายเดือนกันยายน 2569")
    parser.add_argument("--prompt-only", action="store_true")
    parser.add_argument("--generate-only", action="store_true", help="Call model, do not execute SQL")
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    if args.prompt_only:
        result = prompt_bundle(args.question)
    elif args.generate_only:
        bundle = prompt_bundle(args.question)
        result = {"mode": "generation_only", "prompt_sha256": bundle["prompt_sha256"], **generate(bundle)}
    else:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            result = run_llm_pipeline(args.question, conn)
    output = json.dumps(jsonable(result), ensure_ascii=False, indent=2)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(output, encoding="utf-8")
    print(output)
    return 0 if args.prompt_only or args.generate_only or result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
