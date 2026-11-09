"""Thin API layer over app.nlp.pipeline.

Run locally:
    export DATABASE_URL=postgresql://readonly:...@localhost:5432/shop
    uvicorn app.main:app --reload

POST /query  {"text": "ยอดขายเดือนนี้เท่าไหร่"}
  -> 200 {"status": "ok", "rows": [...], "columns": [...], "sql": "...", "rules": [...]}
  -> 200 {"status": "unmatched", "message": "..."}                (not a 4xx: the
        request itself was fine, the rules just didn't recognize it)
  -> 200 {"status": "ambiguous_entity", "message": "...", "candidates": [...]}
  -> 500 only for genuine infrastructure failure (DB unreachable, etc.)
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from decimal import Decimal

import psycopg
from fastapi import FastAPI
from pydantic import BaseModel

from app.nlp.pipeline import run_pipeline, PipelineStatus

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://readonly:readonly@localhost:5432/shop"
)


class QueryRequest(BaseModel):
    text: str


class QueryResponse(BaseModel):
    status: str
    rows: list | None = None
    columns: list[str] | None = None
    sql: str | None = None
    rules: list[str] = []
    message: str | None = None
    candidates: list | None = None


def _jsonable(rows: list | None) -> list | None:
    if rows is None:
        return None
    out = []
    for row in rows:
        out.append([float(v) if isinstance(v, Decimal) else str(v) if hasattr(v, "isoformat") else v for v in row])
    return out


_conn: psycopg.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    _conn = psycopg.connect(DATABASE_URL, autocommit=True)
    yield
    if _conn:
        _conn.close()


app = FastAPI(title="Thai NL -> SQL (rule-based)", lifespan=lifespan)


@app.get("/health")
def health():
    try:
        _conn.execute("SELECT 1")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    result = run_pipeline(req.text, _conn)
    return QueryResponse(
        status=result.status.value,
        rows=_jsonable(result.rows),
        columns=result.columns,
        sql=result.debug_sql,
        rules=result.matched_rules,
        message=result.message,
        candidates=result.candidates,
    )
