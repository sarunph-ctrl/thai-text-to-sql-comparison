"""Thai WMS Rule-based pipeline: normalize -> parse -> build -> guard -> execute."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

import psycopg

from app.nlp.normalize import normalize
from app.wms.builder import MAX_ROWS, build_wms_query
from app.wms.guard import WMSQueryRejected, check_wms_template
from app.wms.parser import UnsupportedWMSQuestion, parse_wms_question


SCOPE_MESSAGE = "รองรับสต็อกปัจจุบัน, Serial ใน Quarantine, Inbound/Outbound progress และจำนวน Outbound แยกสถานะรายเดือน"


@dataclass
class WMSResult:
    status: str = "unsupported"
    question: str = ""
    clean_text: str = ""
    tokens: list[str] = field(default_factory=list)
    family: str | None = None
    interpretation: dict = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    sql: str | None = None
    params: list = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list = field(default_factory=list)
    ordered: bool = False
    message: str | None = None
    sql_valid: bool | None = None
    sql_executed: bool = False
    truncated: bool = False
    validation_ms: float | None = None
    database_ms: float | None = None
    elapsed_ms: float = 0


def run_wms_rule_pipeline(raw_text: str, conn: psycopg.Connection) -> WMSResult:
    start = perf_counter()
    result = WMSResult(question=raw_text)

    def finish(status: str, message: str | None = None) -> WMSResult:
        result.status = status
        result.message = message
        result.elapsed_ms = round((perf_counter() - start) * 1000, 3)
        return result

    if not isinstance(raw_text, str) or not raw_text.strip() or len(raw_text) > 500:
        return finish("unsupported", SCOPE_MESSAGE)

    normalized = normalize(raw_text)
    result.clean_text = normalized.clean_text
    result.tokens = normalized.tokens
    try:
        intent = parse_wms_question(normalized.clean_text)
    except UnsupportedWMSQuestion as exc:
        return finish("unsupported", f"นอกขอบเขต: {exc}. {SCOPE_MESSAGE}")

    result.family = intent.family
    result.interpretation = {"family": intent.family, **intent.filters}
    result.rules = intent.matched_rules
    result.business_rules = intent.business_rules
    query = build_wms_query(intent)
    result.sql = query.sql
    result.params = query.params
    result.ordered = query.ordered

    validation_start = perf_counter()
    try:
        checked = check_wms_template(query.sql, query.params)
    except WMSQueryRejected as exc:
        result.sql_valid = False
        result.validation_ms = round((perf_counter() - validation_start) * 1000, 3)
        return finish("blocked", f"SQL guard ปฏิเสธ: {exc}")
    result.sql_valid = True
    result.tables = checked.tables
    result.validation_ms = round((perf_counter() - validation_start) * 1000, 3)

    database_start = perf_counter()
    try:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '3000ms'")
            schemas = conn.execute("SELECT current_schemas(false)").fetchone()[0]
            schema = next((name for name in schemas if name not in ("pg_catalog", "information_schema")
                           and not name.startswith("pg_temp_")), None)
            if schema is None:
                raise WMSQueryRejected("No application schema is selected")
            conn.execute(psycopg.sql.SQL("SET LOCAL search_path TO pg_catalog, {}").format(
                psycopg.sql.Identifier(schema)))
            conn.execute("EXPLAIN (FORMAT JSON) " + query.sql, query.params)
            cursor = conn.execute(query.sql, query.params)
            rows = cursor.fetchmany(MAX_ROWS + 1)
            result.columns = [description.name for description in cursor.description]
            result.rows = rows[:MAX_ROWS]
            result.truncated = len(rows) > MAX_ROWS
            result.sql_executed = True
    except (psycopg.Error, WMSQueryRejected):
        result.database_ms = round((perf_counter() - database_start) * 1000, 3)
        return finish("blocked", "ฐานข้อมูลปฏิเสธ Query หรือประมวลผลไม่สำเร็จ")
    result.database_ms = round((perf_counter() - database_start) * 1000, 3)
    if result.truncated:
        return finish("blocked", "ผลลัพธ์เกิน Row limit")
    return finish("ok")
