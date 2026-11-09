"""Five-table sales and inventory API. POST /query; documentation at /docs.

The original broad prototype is preserved in app.main.
"""
from dataclasses import asdict
from decimal import Decimal
import logging
import os

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.nlp.demo import run_demo_pipeline
from app.llm.client import configuration_status
from app.llm.prompt import prompt_bundle
from app.llm.pipeline import run_llm_pipeline
from app.llm.comparison import resultsets_equal
from scripts.local_demo import connection_string

app = FastAPI(title="Thai Text-to-SQL · Rule-based vs IntelSphere", version="0.3.0")
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500,
                      examples=["ยอดขายเดือนกันยายน 2569", "สินค้าคงเหลือแยกตามคลังมีเท่าไหร่",
                                "เดือนกันยายน 2569 มีสินค้าจ่ายออกแต่ละชนิดกี่หน่วย"])


class ManualLLMRequest(QueryRequest):
    model_output: str = Field(min_length=1, max_length=24000,
        description='Paste the JSON returned by a model. This route does not call an API or claim API token/latency measurements.')


def database_url() -> str:
    return os.environ.get("DATABASE_URL") or connection_string()


def jsonable(value):
    # Money remains an exact decimal string. Never round-trip through float.
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


@app.get("/health")
def health():
    try:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            conn.execute("SELECT 1 FROM products LIMIT 1")
            conn.execute("SELECT 1 FROM stock_movements LIMIT 1")
            return {"ok": True, "profile": "sales-inventory", "version": "0.3.0",
                    "database": "PostgreSQL", "llm_configured": configuration_status()["configured"]}
    except (psycopg.Error, RuntimeError):
        raise HTTPException(503, "Start the demo database first")


@app.post("/query")
def query(req: QueryRequest):
    try:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            return jsonable(asdict(run_demo_pipeline(req.text, conn)))
    except (psycopg.Error, RuntimeError):
        logger.error("Demo database unavailable")
        raise HTTPException(503, "Demo database unavailable; run scripts.local_demo start")


@app.get("/llm/status")
def llm_status():
    """Configuration only. No API request and no API key is returned."""
    return configuration_status()


@app.post("/llm/prompt")
def llm_prompt(req: QueryRequest):
    """Inspect the exact zero-shot messages (schema + definitions + question)."""
    return prompt_bundle(req.text)


@app.post("/llm/query")
def llm_query(req: QueryRequest):
    """One real IntelSphere call, guarded SELECT, then DB rows and usage."""
    try:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            return jsonable(run_llm_pipeline(req.text, conn))
    except (psycopg.Error, RuntimeError):
        raise HTTPException(503, "Demo database unavailable")


@app.post("/llm/check")
def llm_check(req: ManualLLMRequest):
    """Validate an existing model JSON reply. Not a live API measurement."""
    try:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            return jsonable(run_llm_pipeline(req.text, conn, manual_output=req.model_output))
    except psycopg.Error:
        raise HTTPException(503, "Demo database unavailable")


@app.post("/compare")
def compare(req: QueryRequest):
    """Run both methods on one DB snapshot. Agreement is not ground-truth accuracy."""
    try:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                rule = run_demo_pipeline(req.text, conn)
                llm = run_llm_pipeline(req.text, conn)
                ordered = rule.interpretation.get("top_n") is not None
                same = None
                if rule.status == llm["status"] == "ok":
                    same = resultsets_equal(llm["rows"], rule.rows, actual_columns=len(llm["columns"]),
                                            expected_columns=len(rule.columns), ordered=ordered)
                return jsonable({"question": req.text, "rule_based": asdict(rule), "llm": llm,
                                 "same_rows_as_rule": same, "order_matters": ordered,
                                 "accuracy_note": "Agreement between methods is not proof of correctness; use the reference evaluation."})
    except psycopg.Error:
        raise HTTPException(503, "Demo database unavailable")
