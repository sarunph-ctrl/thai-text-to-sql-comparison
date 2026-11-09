"""Resolves a candidate name string (e.g. "สมชาย", "john") to a row id in the
target table.

Strategy, in order - stop at the first that produces a confident result:
  1. Exact, case-insensitive match.
  2. Prefix / substring match (handles "สมชาย" matching a stored "นายสมชาย ใจดี").
  3. Fuzzy match via Postgres pg_trgm similarity (handles typos / transliteration
     drift, e.g. "จอน" vs "จอห์น").

If step 1 or 2 yields more than one row, or step 3's best score is below the
threshold, the result is AMBIGUOUS or NOT_FOUND and the caller must ask the
user to disambiguate rather than silently pick one - this is a hard rule for
a rule-based system: never guess on entity identity.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

import psycopg


class ResolutionStatus(Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass
class ResolutionResult:
    status: ResolutionStatus
    id: int | None = None
    name: str | None = None
    candidates: list[tuple[int, str]] | None = None  # for AMBIGUOUS / NOT_FOUND(near-miss)


FUZZY_THRESHOLD = 0.35
MAX_CANDIDATES = 5

_ALLOWED_TABLES = {"customers", "products", "categories", "suppliers", "branches", "employees"}


def resolve_entity(conn: psycopg.Connection, table: str, name_column: str, query: str) -> ResolutionResult:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"table {table!r} is not resolvable")
    q = query.strip()
    if not q:
        return ResolutionResult(ResolutionStatus.NOT_FOUND, candidates=[])

    ident_table = psycopg.sql.Identifier(table)
    ident_col = psycopg.sql.Identifier(name_column)

    # 1. Exact (case-insensitive).
    sql = psycopg.sql.SQL("SELECT id, {col} FROM {tbl} WHERE lower({col}) = lower(%s)").format(
        col=ident_col, tbl=ident_table
    )
    rows = conn.execute(sql, (q,)).fetchall()
    if len(rows) == 1:
        return ResolutionResult(ResolutionStatus.RESOLVED, id=rows[0][0], name=rows[0][1])
    if len(rows) > 1:
        return ResolutionResult(ResolutionStatus.AMBIGUOUS, candidates=rows[:MAX_CANDIDATES])

    # 2. Substring, either direction (query is contained in name, or name in query).
    sql = psycopg.sql.SQL(
        "SELECT id, {col} FROM {tbl} WHERE {col} ILIKE '%%' || %s || '%%' LIMIT %s"
    ).format(col=ident_col, tbl=ident_table)
    rows = conn.execute(sql, (q, MAX_CANDIDATES + 1)).fetchall()
    if len(rows) == 1:
        return ResolutionResult(ResolutionStatus.RESOLVED, id=rows[0][0], name=rows[0][1])
    if len(rows) > 1:
        return ResolutionResult(ResolutionStatus.AMBIGUOUS, candidates=rows[:MAX_CANDIDATES])

    # 3. Fuzzy trigram similarity (requires pg_trgm extension).
    try:
        sql = psycopg.sql.SQL(
            "SELECT id, {col}, similarity({col}, %s) AS score FROM {tbl} "
            "ORDER BY score DESC LIMIT %s"
        ).format(col=ident_col, tbl=ident_table)
        rows = conn.execute(sql, (q, MAX_CANDIDATES)).fetchall()
    except psycopg.errors.UndefinedFunction:
        conn.rollback()
        return ResolutionResult(ResolutionStatus.NOT_FOUND, candidates=[])

    good = [(r[0], r[1]) for r in rows if r[2] is not None and r[2] >= FUZZY_THRESHOLD]
    if len(good) == 1:
        return ResolutionResult(ResolutionStatus.RESOLVED, id=good[0][0], name=good[0][1])
    if len(good) > 1:
        return ResolutionResult(ResolutionStatus.AMBIGUOUS, candidates=good)
    return ResolutionResult(ResolutionStatus.NOT_FOUND, candidates=[(r[0], r[1]) for r in rows[:3]])
