"""AST allowlist and read-only executor for model-generated WMS SQL."""
from dataclasses import dataclass
import re

import psycopg
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from app.wms.guard import TABLE_COLUMNS


MAX_ROWS = 200
MAX_SQL_LENGTH = 20000
SAFE_FUNCTIONS = {"COUNT", "COALESCE", "CAST"}
SAFE_CASTS = {"INT", "BIGINT", "SMALLINT", "DECIMAL", "DOUBLE", "FLOAT", "DATE", "TIMESTAMP", "TIMESTAMPTZ"}


class WMSSQLRejected(ValueError):
    pass


@dataclass(frozen=True)
class CheckedWMSSQL:
    generated_sql: str
    executed_sql: str
    tables: list[str]
    row_cap_applied: bool


def check_wms_sql(raw: str) -> CheckedWMSSQL:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_SQL_LENGTH:
        raise WMSSQLRejected("SQL missing or exceeds length limit")
    try:
        statements = sqlglot.parse(raw, read="postgres")
    except sqlglot.errors.SqlglotError as exc:
        raise WMSSQLRejected("SQL cannot be parsed as PostgreSQL") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise WMSSQLRejected("Exactly one SELECT is allowed")
    tree = statements[0]
    blocked = (exp.DDL, exp.DML, exp.Command, exp.Into, exp.Lock, exp.Union,
               exp.Intersect, exp.Except, exp.Parameter, exp.Placeholder)
    for node in tree.walk():
        if isinstance(node, blocked):
            raise WMSSQLRejected(f"Unsupported SQL construct: {type(node).__name__}")
        if isinstance(node, exp.With) and node.args.get("recursive"):
            raise WMSSQLRejected("Recursive CTEs are not supported")
        if isinstance(node, exp.Func) and not isinstance(node, exp.Connector):
            if isinstance(node, exp.Anonymous) or node.sql_name() not in SAFE_FUNCTIONS:
                raise WMSSQLRejected("Function is outside the WMS allowlist")
        if isinstance(node, exp.Cast):
            target = node.args.get("to")
            kind = getattr(getattr(target, "this", None), "name", "")
            if kind not in SAFE_CASTS:
                raise WMSSQLRejected("Cast type is outside the WMS allowlist")
        if isinstance(node, exp.Dot):
            raise WMSSQLRejected("Qualified function/composite access is unsupported")
        if isinstance(node, exp.Identifier) and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", node.name):
            raise WMSSQLRejected("Identifiers must be simple schema identifiers")

    physical: set[str] = set()
    try:
        for scope in traverse_scope(tree):
            for source in scope.sources.values():
                if isinstance(source, Scope):
                    continue
                if not isinstance(source, exp.Table) or not isinstance(source.this, exp.Identifier):
                    raise WMSSQLRejected("Table functions are not supported")
                if source.catalog or source.db not in ("", "public") or source.name not in TABLE_COLUMNS:
                    raise WMSSQLRejected("Table is outside the ten-table WMS schema")
                physical.add(source.name)
    except sqlglot.errors.SqlglotError as exc:
        raise WMSSQLRejected("SQL table scope could not be validated") from exc
    if not physical:
        raise WMSSQLRejected("A query must read at least one WMS table")

    known_columns = set().union(*TABLE_COLUMNS.values())
    known_columns.update(alias.alias for alias in tree.find_all(exp.Alias))
    for cte in tree.find_all(exp.CTE):
        known_columns.update(cte.alias_column_names)
    for column in tree.find_all(exp.Column):
        if not column.is_star and column.name not in known_columns:
            raise WMSSQLRejected(f"Column is outside the WMS schema: {column.name}")

    limit = tree.args.get("limit")
    limit_value = limit.expression if limit else None
    capped = False
    if limit_value is None:
        tree = tree.limit(MAX_ROWS + 1)
        capped = True
    elif not isinstance(limit_value, exp.Literal) or not limit_value.is_int:
        raise WMSSQLRejected("LIMIT must be a non-negative integer literal")
    elif int(limit_value.this) < 0:
        raise WMSSQLRejected("Negative LIMIT is unsupported")
    elif int(limit_value.this) > MAX_ROWS + 1:
        tree = tree.limit(MAX_ROWS + 1)
        capped = True
    return CheckedWMSSQL(raw, tree.sql(dialect="postgres"), sorted(physical), capped)


def execute_wms_checked(conn: psycopg.Connection, checked: CheckedWMSSQL) -> dict:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '3000ms'")
        schemas = conn.execute("SELECT current_schemas(false)").fetchone()[0]
        schema = next((name for name in schemas if name not in ("pg_catalog", "information_schema")
                       and not name.startswith("pg_temp_")), None)
        if schema is None:
            raise WMSSQLRejected("No application schema is selected")
        conn.execute(psycopg.sql.SQL("SET LOCAL search_path TO pg_catalog, {}").format(
            psycopg.sql.Identifier(schema)))
        conn.execute("EXPLAIN (FORMAT JSON) " + checked.executed_sql)
        cursor = conn.execute(checked.executed_sql)
        rows = cursor.fetchmany(MAX_ROWS + 1)
        return {"columns": [description.name for description in cursor.description],
                "rows": rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS}
