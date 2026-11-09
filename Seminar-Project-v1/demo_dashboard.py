"""Presentation shell around the unchanged Sprint 2 API.

Run uvicorn demo_dashboard:app --host 127.0.0.1 --port 8000
"""
import psycopg
from psycopg import sql
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.demo_api import app, database_url, jsonable
from app.llm.client import configuration_status
from presentation_data import ROOT, REPORT, SCHEMA, recorded_report, schema_payload

app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="presentation-assets")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(ROOT / "web/index.html", headers={"Cache-Control": "no-store"})


@app.get("/demo/info", tags=["Presentation"])
def demo_info():
    return {"presentation_version": "1.0", "api_version": "0.3.0",
            "llm": configuration_status(), "recorded_results_available": REPORT.exists(),
            "schema": schema_payload()}


@app.get("/demo/recorded", tags=["Presentation"])
def recorded_results():
    """A previously saved experiment, never a fresh model call."""
    try:
        return recorded_report()
    except (OSError, ValueError, KeyError):
        raise HTTPException(404, "Recorded Sprint 2 experiment not available")


@app.get("/demo/offline", include_in_schema=False)
def offline_backup():
    path = ROOT / "output/presentation/offline-demo.html"
    if not path.exists():
        raise HTTPException(404, "Build the offline backup first")
    return FileResponse(path, media_type="text/html", headers={"Cache-Control": "no-store"})


@app.get("/demo/data", tags=["Presentation"])
def synthetic_data():
    """Read the five fixed synthetic tables for manual verification."""
    try:
        with psycopg.connect(database_url(), autocommit=True) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                conn.execute("SET LOCAL statement_timeout = '3000ms'")
                tables = {}
                for entry in SCHEMA:
                    name = entry["name"]
                    count = conn.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(name))).fetchone()[0]
                    cur = conn.execute(sql.SQL("SELECT * FROM {} ORDER BY id LIMIT 201").format(sql.Identifier(name)))
                    rows = cur.fetchall()
                    tables[name] = {"columns": [c.name for c in cur.description], "rows": rows[:200],
                                    "total_rows": count, "truncated": len(rows) > 200}
        return jsonable({"source": "current_database", "tables": tables})
    except psycopg.Error:
        raise HTTPException(503, "Demo database is unavailable; recorded results remain accessible")
