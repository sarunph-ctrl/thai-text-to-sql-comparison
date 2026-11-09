"""Bounded SELECT validation using a PostgreSQL AST, not string prefixes.

This is a local demo allowlist, not a general-purpose sandbox. Execution also
requires a SELECT-only database role, a read-only transaction and a timeout.
"""
from dataclasses import dataclass
import re

import psycopg
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from app.llm.prompt import TABLE_COLUMNS

MAX_ROWS = 200
MAX_SQL_LENGTH = 20000
SAFE_FUNCTIONS = {"SUM", "COUNT", "AVG", "MIN", "MAX", "COALESCE", "ABS", "ROUND", "CAST", "CASE", "IF", "AND", "OR", "NOT"}
SAFE_CASTS = {"INT", "BIGINT", "SMALLINT", "DECIMAL", "DOUBLE", "FLOAT", "DATE", "TIMESTAMP", "TIMESTAMPTZ"}


class SQLRejected(ValueError):
    pass


@dataclass
class CheckedSQL:
    generated_sql: str
    executed_sql: str
    tables: list[str]
    row_cap_applied: bool


def check_sql(raw: str) -> CheckedSQL:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_SQL_LENGTH:
        raise SQLRejected("SQL missing or exceeds length limit")
    try:
        statements = sqlglot.parse(raw, read="postgres")
    except sqlglot.errors.SqlglotError as exc:
        raise SQLRejected("SQL cannot be parsed as PostgreSQL") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise SQLRejected("Exactly one SELECT is allowed")
    tree = statements[0]
    blocked = (exp.DDL, exp.DML, exp.Command, exp.Into, exp.Lock, exp.Union,
               exp.Intersect, exp.Except, exp.Parameter, exp.Placeholder)
    for node in tree.walk():
        if isinstance(node, blocked):
            raise SQLRejected(f"Unsupported SQL construct: {type(node).__name__}")
        if isinstance(node, exp.With) and node.args.get("recursive"):
            raise SQLRejected("Recursive CTEs are not supported")
        if isinstance(node, exp.Func):
            if isinstance(node, exp.Anonymous) or node.sql_name() not in SAFE_FUNCTIONS:
                raise SQLRejected("Function is outside the aggregate allowlist")
        if isinstance(node, exp.Cast):
            target = node.args.get("to")
            kind = getattr(getattr(target, "this", None), "name", "")
            if kind not in SAFE_CASTS:
                raise SQLRejected("Cast type is outside the numeric/date allowlist")
        if isinstance(node, exp.Dot):
            raise SQLRejected("Qualified function/composite access is unsupported")
        if isinstance(node, exp.Identifier) and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", node.name):
            raise SQLRejected("Identifiers must be simple schema identifiers")
    physical = set()
    try:
        for scope in traverse_scope(tree):
            for source in scope.sources.values():
                if isinstance(source, Scope):
                    continue
                if not isinstance(source, exp.Table) or not isinstance(source.this, exp.Identifier):
                    raise SQLRejected("Table functions are not supported")
                if source.catalog or source.db not in ("", "public") or source.name not in TABLE_COLUMNS:
                    raise SQLRejected("Table is outside the five-table demo schema")
                physical.add(source.name)
    except sqlglot.errors.SqlglotError as exc:
        raise SQLRejected("SQL table scope could not be validated") from exc
    if not physical:
        raise SQLRejected("A query must read at least one demo table")
    known_columns = set().union(*TABLE_COLUMNS.values())
    known_columns.update(alias.alias for alias in tree.find_all(exp.Alias))
    for cte in tree.find_all(exp.CTE):
        known_columns.update(cte.alias_column_names)
    for column in tree.find_all(exp.Column):
        if not column.is_star and column.name not in known_columns:
            raise SQLRejected("Column is outside the schema/derived-output names")
    # Render the parsed tree rather than running the unparsed original text.
    # Keep ORDER BY at the root; a wrapper SELECT could discard output ordering.
    limit = tree.args.get("limit")
    limit_value = limit.expression if limit else None
    capped = False
    if limit_value is None:
        tree = tree.limit(MAX_ROWS + 1)
        capped = True
    elif not isinstance(limit_value, exp.Literal) or not limit_value.is_int:
        raise SQLRejected("LIMIT must be a non-negative integer literal")
    elif int(limit_value.this) < 0:
        raise SQLRejected("Negative LIMIT is unsupported")
    elif int(limit_value.this) > MAX_ROWS + 1:
        tree = tree.limit(MAX_ROWS + 1)
        capped = True
    return CheckedSQL(raw, tree.sql(dialect="postgres"), sorted(physical), capped)


def execute_checked(conn: psycopg.Connection, checked: CheckedSQL) -> dict:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '3000ms'")
        # Resolve builtins before application functions. Preserve the trusted
        # connection's current schema (public in the app, isolated in tests).
        schemas = conn.execute("SELECT current_schemas(false)").fetchone()[0]
        schema = next((s for s in schemas if s not in ("pg_catalog", "information_schema")
                       and not s.startswith("pg_temp_")), None)
        if schema is None:
            raise SQLRejected("No application schema is selected")
        conn.execute(psycopg.sql.SQL("SET LOCAL search_path TO pg_catalog, {}").format(psycopg.sql.Identifier(schema)))
        conn.execute("EXPLAIN (FORMAT JSON) " + checked.executed_sql)
        cursor = conn.execute(checked.executed_sql)
        rows = cursor.fetchmany(MAX_ROWS + 1)
        return {"columns": [d.name for d in cursor.description], "rows": rows[:MAX_ROWS],
                "truncated": len(rows) > MAX_ROWS}
