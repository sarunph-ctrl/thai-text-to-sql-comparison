"""Bounded day-one profile, sharing normalization, intent rules and SQL builder.

Tokens are exposed for explanation. Slot matching uses substring/regex rules;
it does not use a trained NER/parser. Anything unconsumed is out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
import re

import psycopg
import yaml

from app.config_loader import CONFIG_DIR
from app.nlp.intents import match_intent
from app.nlp.normalize import normalize
from app.nlp.inventory import parse_inventory_question
from app.nlp.rule_utils import unconsumed_text
from app.sql.builder import Intent, MAX_LIMIT, build_query

CONFIG = yaml.safe_load((CONFIG_DIR / "demo.yaml").read_text(encoding="utf-8"))
SCOPE_MESSAGE = "เดโมรองรับยอดขายรวม / แยกสินค้า / Top-N พร้อมเดือนและปี, สินค้าคงเหลือแยกคลัง และยอดจ่ายออกแยกสินค้ารายเดือน"


@dataclass
class DemoResult:
    status: str = "unmatched"
    question: str = ""
    clean_text: str = ""
    tokens: list[str] = field(default_factory=list)
    interpretation: dict = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    sql: str | None = None
    params: list = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list = field(default_factory=list)
    message: str | None = None
    business_definition: str = CONFIG["business_definition"]
    elapsed_ms: float = 0


def _remaining(text: str, phrases: list[str]) -> str:
    return unconsumed_text(text, phrases, CONFIG["fillers"])


def run_demo_pipeline(raw_text: str, conn: psycopg.Connection) -> DemoResult:
    start = perf_counter()
    result = DemoResult(question=raw_text)

    def finish(status: str, message: str | None = None) -> DemoResult:
        result.status = status
        result.message = message
        result.elapsed_ms = round((perf_counter() - start) * 1000, 3)
        return result

    def execute(query) -> DemoResult:
        result.sql, result.params = query.debug_sql, query.params
        result.rules.append("unconsumed text check: passed")
        try:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SET LOCAL statement_timeout = '3000ms'")
                cur = conn.execute(query.sql, query.params)
                result.rows = cur.fetchall()
                result.columns = [d.name for d in cur.description]
        except psycopg.Error:
            return finish("blocked", "ฐานข้อมูลประมวลผลไม่สำเร็จ ตรวจ log และการเชื่อมต่อ")
        return finish("ok")

    if not raw_text.strip() or len(raw_text) > 500:
        return finish("unmatched", SCOPE_MESSAGE)
    norm = normalize(raw_text)
    result.clean_text, result.tokens = norm.clean_text, norm.tokens
    if any(phrase in norm.clean_text.casefold() for phrase in CONFIG["unsupported"]):
        return finish("unsupported", "คำถามมีเงื่อนไขหรือการทำงานนอกขอบเขต " + SCOPE_MESSAGE)
    try:
        inventory = parse_inventory_question(norm.clean_text)
        if inventory is not None:
            result.interpretation = inventory.interpretation
            result.rules = inventory.rules
            result.business_definition = inventory.definition
            return execute(inventory.query)
        slots = match_intent(norm.clean_text)
    except (ValueError, OverflowError) as exc:
        return finish("unsupported", str(exc) + " " + SCOPE_MESSAGE)
    if slots is None:
        return finish("unmatched", SCOPE_MESSAGE)
    result.rules = slots.matched_rules.copy()
    if (slots.metric != "revenue" or slots.dimension not in (None, "product")
            or slots.time_group or slots.status not in (None, "paid") or slots.payment_method):
        return finish("unsupported", SCOPE_MESSAGE)
    if slots.top_n is not None and (slots.dimension != "product" or not 1 <= slots.top_n <= MAX_LIMIT):
        return finish("unsupported", f"Top-N ต้องเป็นสินค้าจำนวน 1–{MAX_LIMIT} อันดับ")
    if not slots.time_range:
        return finish("unsupported", "กรุณาระบุเดือนพร้อมปีให้ชัดเจน " + SCOPE_MESSAGE)
    # Relative periods, single days and year-only questions are not this demo.
    month_names = yaml.safe_load((CONFIG_DIR / "time_words.yaml").read_text(encoding="utf-8"))["months"]
    matched = slots.matched_phrases
    if not any(re.search(r"\d{4}", p) and any(name in p for names in month_names.values() for name in names)
               for p in matched):
        return finish("unsupported", "รอบนี้ใช้เดือนที่ระบุปีแน่นอน เช่น กันยายน 2569")
    range_start, range_end = slots.time_range
    if range_start.day != 1 or (range_end - range_start).days < 28:
        return finish("unsupported", "เดโมนี้รับช่วงเต็มเดือนเท่านั้น")
    residual = _remaining(norm.clean_text, matched)
    if residual:
        return finish("unsupported", f"ยังไม่รองรับข้อความส่วนนี้: {residual!r} จึงไม่รัน SQL")

    intent = Intent(metric="revenue", dimension=slots.dimension, top_n=slots.top_n,
                    order=slots.order, paid_only=True)
    # Shared builder takes time filters as bind parameters.
    from app.sql.builder import Filter
    intent.filters.append(Filter("time", "gte", slots.time_range))
    query = build_query(intent)
    result.interpretation = {
        "metric": "revenue", "dimension": slots.dimension,
        "top_n": slots.top_n, "order": slots.order,
        "start_inclusive": range_start.isoformat(), "end_exclusive": range_end.isoformat(),
        "status": "paid", "ranking_unit": "THB",
        "tables": ["orders", "order_items"] + (["products"] if slots.dimension else []),
    }
    result.rules.append("business rule: paid only; revenue uses historical order_items.unit_price")
    return execute(query)
