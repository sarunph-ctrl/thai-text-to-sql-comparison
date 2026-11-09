"""Orchestrates the full rule-based flow:

  raw text
    -> normalize (app.nlp.normalize)
    -> match_intent (app.nlp.intents)              - metric, dimension, filters, time
    -> extract leftover proper-name candidates
    -> resolve_entity against DB for each candidate (app.nlp.entity_resolver)
    -> build_query (app.sql.builder)
    -> execute (read-only) with LIMIT + timeout
    -> PipelineResult with the answer, the SQL, and the trace of matched rules

Every step that can fail returns a typed status instead of raising into a
generic 500, so the caller (API layer) can show the user something useful:
UNMATCHED, AMBIGUOUS_ENTITY, ENTITY_NOT_FOUND, or OK.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum

import psycopg

from app.config_loader import load_lexicon
from app.nlp.entity_resolver import ResolutionStatus, resolve_entity
from app.nlp.intents import match_intent
from app.nlp.normalize import normalize
from app.sql.builder import Filter, Intent, build_query

STATEMENT_TIMEOUT_MS = 3000
_LEX = load_lexicon()
_CONNECTOR_WORDS = sorted(set(_LEX.get("connector_words", [])) | set(_LEX.get("stopwords", [])), key=len, reverse=True)


class PipelineStatus(Enum):
    OK = "ok"
    UNMATCHED = "unmatched"
    AMBIGUOUS_ENTITY = "ambiguous_entity"
    ENTITY_NOT_FOUND = "entity_not_found"
    BLOCKED = "blocked"


@dataclass
class PipelineResult:
    status: PipelineStatus
    rows: list | None = None
    columns: list[str] | None = None
    debug_sql: str | None = None
    matched_rules: list[str] = field(default_factory=list)
    message: str | None = None          # human-readable note (unmatched / ambiguous / error)
    candidates: list[tuple[int, str]] | None = None


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _extract_name_candidate(clean_text: str, matched_phrases: list[str]) -> str | None:
    """Strips every phrase the intent matcher already consumed (metric,
    dimension, status, time, etc.), then strips connector/stopwords, then
    digits and punctuation. Whatever contiguous text survives is treated as
    a candidate proper name to resolve against the DB (customer or product).

    Operating on the raw clean_text (substring removal) rather than on
    tokens sidesteps a real limitation of unsupervised Thai tokenization:
    an unknown proper name next to a verb (e.g. "สมชายซื้อ") often comes out
    of the tokenizer as one merged token, which would break token-based
    extraction. Substring removal doesn't care about token boundaries.
    """
    text = clean_text
    for phrase in sorted(matched_phrases, key=len, reverse=True):
        if phrase:
            text = text.replace(phrase, " ")
    for word in _CONNECTOR_WORDS:
        if word:
            text = text.replace(word, " ")
    text = _NUMBER_RE.sub(" ", text)
    text = re.sub(r"[^\w\u0e00-\u0e7f]", " ", text)
    text = " ".join(text.split()).strip()
    if len(text) < 2:
        return None
    return text or None


def run_pipeline(raw_text: str, conn: psycopg.Connection) -> PipelineResult:
    norm = normalize(raw_text)
    slots = match_intent(norm.clean_text)

    if slots is None:
        return PipelineResult(
            status=PipelineStatus.UNMATCHED,
            message="ไม่เข้าใจคำถามนี้ ลองระบุสิ่งที่ต้องการทราบ เช่น 'ยอดขาย', 'จำนวนออเดอร์', หรือ 'สต็อก' ร่วมกับช่วงเวลา",
        )

    filters: list[Filter] = []
    matched_rules = list(slots.matched_rules)

    if slots.time_range:
        filters.append(Filter("time", "gte", slots.time_range))
    if slots.status:
        filters.append(Filter("status", "eq", slots.status))
    if slots.payment_method:
        filters.append(Filter("payment_method", "eq", slots.payment_method))
    if slots.stock_filter:
        op, val = slots.stock_filter
        filters.append(Filter("stock", op, val))

    # Try to resolve a leftover proper name as an entity filter (e.g. a
    # customer name mentioned without the word "ลูกค้า"). Only attempted when
    # no dimension/breakdown was already requested for that same entity type,
    # to avoid "top 5 customers สมชาย" nonsense.
    candidate = _extract_name_candidate(norm.clean_text, slots.matched_phrases)
    if candidate:
        for dim_key in ("customer", "product"):
            if slots.dimension == dim_key:
                continue
            lex_entity = _LEX["entities"][dim_key]
            res = resolve_entity(conn, lex_entity["table"], lex_entity["name_column"], candidate)
            if res.status == ResolutionStatus.RESOLVED:
                filters.append(Filter(dim_key, "eq", res.id))
                matched_rules.append(f"{dim_key} filter resolved: {candidate!r} -> id={res.id} ({res.name})")
                break
            if res.status == ResolutionStatus.AMBIGUOUS:
                return PipelineResult(
                    status=PipelineStatus.AMBIGUOUS_ENTITY,
                    matched_rules=matched_rules,
                    message=f"พบหลายรายการที่ตรงกับ '{candidate}' กรุณาระบุให้ชัดเจนขึ้น",
                    candidates=res.candidates,
                )
        # NOT_FOUND is not an error by itself - the candidate might just be
        # filler our stopword list missed. We proceed without that filter.

    intent = Intent(
        metric=slots.metric,
        dimension=slots.dimension,
        time_group=slots.time_group,
        top_n=slots.top_n,
        order=slots.order,
        filters=filters,
    )

    try:
        bq = build_query(intent)
    except ValueError as e:
        return PipelineResult(status=PipelineStatus.BLOCKED, matched_rules=matched_rules, message=str(e))

    try:
        # SET LOCAL does not accept bind parameters in Postgres; the value here
        # is a fixed internal constant, never user input, so a literal is safe.
        conn.execute(f"SET LOCAL statement_timeout = {int(STATEMENT_TIMEOUT_MS)}")
        cur = conn.execute(bq.sql, bq.params)
        rows = cur.fetchall()
        columns = [d.name for d in cur.description]
    except psycopg.Error as e:  # defensive: should be unreachable given the builder's allowlist
        return PipelineResult(status=PipelineStatus.BLOCKED, matched_rules=matched_rules, message=str(e))

    return PipelineResult(
        status=PipelineStatus.OK,
        rows=rows,
        columns=columns,
        debug_sql=bq.debug_sql,
        matched_rules=matched_rules,
    )
