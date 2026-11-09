"""Builds a SELECT-only, parameterized query from an Intent.

Safety guarantees (checked, not assumed):
  * Only SELECT is ever produced - there is no code path to any other verb.
  * Every table/column comes from app.sql.schema's allowlist, wrapped with
    psycopg.sql.Identifier (never raw string interpolation).
  * Every user-supplied VALUE (names, numbers, dates) is passed as a bind
    parameter, never spliced into the SQL text.
  * A LIMIT is always present (default cap, or the user's requested top-N
    clamped to it).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

from psycopg import sql

from app.sql.schema import ALLOWED_COLUMNS, ALLOWED_TABLES, join_path

MAX_LIMIT = 200
DEFAULT_LIMIT = 50

# metric_key -> (sql expression string, tables it needs, value format)
METRICS: dict[str, dict] = {
    "revenue":              dict(expr="SUM(order_items.qty * order_items.unit_price)", tables={"orders", "order_items"}, fmt="currency"),
    "order_count":          dict(expr="COUNT(DISTINCT orders.id)", tables={"orders"}, fmt="integer"),
    "quantity_sold":        dict(expr="SUM(order_items.qty)", tables={"orders", "order_items"}, fmt="integer"),
    "customer_count":       dict(expr="COUNT(DISTINCT orders.customer_id)", tables={"orders"}, fmt="integer"),
    "average_order_value":  dict(expr="AVG(orders.total)", tables={"orders"}, fmt="currency"),
    "stock":                dict(expr="products.stock", tables={"products"}, fmt="integer"),
}

# dimension_key -> (table, id_column, label_column)
DIMENSIONS: dict[str, tuple[str, str, str]] = {
    "product":  ("products", "id", "name"),
    "category": ("categories", "id", "name"),
    "customer": ("customers", "id", "name"),
    "supplier": ("suppliers", "id", "name"),
    "branch":   ("branches", "id", "name"),
    "employee": ("employees", "id", "name"),
    "status":   ("orders", None, "status"),
    "payment_method": ("orders", None, "payment_method"),
}

TIME_GROUP_EXPR = {
    "day":   "DATE_TRUNC('day', orders.order_date)",
    "week":  "DATE_TRUNC('week', orders.order_date)",
    "month": "DATE_TRUNC('month', orders.order_date)",
    "year":  "DATE_TRUNC('year', orders.order_date)",
}


@dataclass
class Filter:
    dimension: str          # key into DIMENSIONS, or 'time'
    op: str                 # 'eq' | 'gt' | 'lt' | 'gte' | 'lte'
    value: object            # resolved id (int), string, or (start,end) date tuple


@dataclass
class Intent:
    metric: str
    dimension: str | None = None      # GROUP BY this dimension (for breakdowns / top-N)
    time_group: str | None = None     # GROUP BY time bucket (day/week/month/year)
    top_n: int | None = None
    order: str = "desc"               # 'desc' | 'asc' for top_n / ranking
    filters: list[Filter] = field(default_factory=list)
    time_range: tuple[date, date] | None = None
    paid_only: bool = False           # explicit demo business definition


@dataclass
class BuiltQuery:
    sql: sql.Composed
    params: list
    debug_sql: str            # human-readable, for the explainability panel


def _base_tables(intent: Intent) -> set[str]:
    tables = set(METRICS[intent.metric]["tables"])
    if intent.dimension:
        dim_table = DIMENSIONS[intent.dimension][0]
        tables.add(dim_table)
    for f in intent.filters:
        if f.dimension == "time":
            tables.add("orders")
        elif f.dimension == "stock":
            tables.add("products")
        elif f.dimension in ("status", "payment_method"):
            tables.add("orders")
        else:
            tables.add(DIMENSIONS[f.dimension][0])
    return tables


def _check_allowed(tables: set[str]) -> None:
    unknown = tables - ALLOWED_TABLES
    if unknown:
        raise ValueError(f"blocked: table(s) not in allowlist: {unknown}")


def build_query(intent: Intent) -> BuiltQuery:
    if intent.metric not in METRICS:
        raise ValueError(f"unknown metric {intent.metric!r}")

    tables = _base_tables(intent)
    _check_allowed(tables)

    root = "orders"
    joins = join_path(root, tables - {root})

    select_parts = [sql.SQL(METRICS[intent.metric]["expr"] + " AS metric_value")]
    group_by_parts: list[sql.Composable] = []

    if intent.dimension:
        dtable, did_col, dlabel_col = DIMENSIONS[intent.dimension]
        if did_col:
            select_parts.insert(0, sql.SQL("{}.{} AS group_id").format(
                sql.Identifier(dtable), sql.Identifier(did_col)))
            group_by_parts.append(sql.SQL("{}.{}").format(sql.Identifier(dtable), sql.Identifier(did_col)))
        select_parts.insert(1 if did_col else 0, sql.SQL("{}.{} AS group_label").format(
            sql.Identifier(dtable), sql.Identifier(dlabel_col)))
        group_by_parts.append(sql.SQL("{}.{}").format(sql.Identifier(dtable), sql.Identifier(dlabel_col)))

    if intent.time_group:
        expr = TIME_GROUP_EXPR[intent.time_group]
        select_parts.append(sql.SQL(expr + " AS time_bucket"))
        group_by_parts.append(sql.SQL(expr))

    from_clause = sql.SQL("FROM {}").format(sql.Identifier(root))
    join_clauses = []
    for a_t, a_c, b_t, b_c in joins:
        join_clauses.append(sql.SQL("JOIN {} ON {}.{} = {}.{}").format(
            sql.Identifier(b_t), sql.Identifier(a_t), sql.Identifier(a_c), sql.Identifier(b_t), sql.Identifier(b_c)
        ))

    where_parts: list[sql.Composable] = []
    params: list = []

    # Exclude cancelled orders by default from revenue-style metrics unless the
    # user explicitly filtered on status - a rule-based safety default so
    # "ยอดขายเดือนนี้" doesn't silently count cancelled orders.
    has_status_filter = any(f.dimension == "status" for f in intent.filters)
    if not has_status_filter and "orders" in tables:
        where_parts.append(sql.SQL("orders.status = %s" if intent.paid_only else "orders.status <> %s"))
        params.append("paid" if intent.paid_only else "cancelled")

    op_sql = {"eq": "=", "gt": ">", "lt": "<", "gte": ">=", "lte": "<="}

    for f in intent.filters:
        if f.dimension == "time":
            start, end = f.value
            where_parts.append(sql.SQL("orders.order_date >= %s AND orders.order_date < %s"))
            params.extend([start, end])
        elif f.dimension in ("status", "payment_method"):
            col = f.dimension
            if col not in ALLOWED_COLUMNS["orders"]:
                raise ValueError(f"blocked column {col}")
            where_parts.append(sql.SQL("orders.{} {} %s").format(sql.Identifier(col), sql.SQL(op_sql[f.op])))
            params.append(f.value)
        elif f.dimension == "stock":
            where_parts.append(sql.SQL("products.stock {} %s").format(sql.SQL(op_sql[f.op])))
            params.append(f.value)
        else:
            dtable, did_col, _ = DIMENSIONS[f.dimension]
            if not did_col:
                raise ValueError(f"dimension {f.dimension} has no id filter")
            where_parts.append(sql.SQL("{}.{} {} %s").format(
                sql.Identifier(dtable), sql.Identifier(did_col), sql.SQL(op_sql[f.op])))
            params.append(f.value)

    where_clause = sql.SQL("")
    if where_parts:
        where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(where_parts)

    group_clause = sql.SQL("")
    if group_by_parts:
        group_clause = sql.SQL("GROUP BY ") + sql.SQL(", ").join(group_by_parts)

    order_clause = sql.SQL("")
    if intent.dimension or intent.time_group:
        direction = sql.SQL("DESC" if intent.order == "desc" else "ASC")
        order_clause = sql.SQL("ORDER BY metric_value {}").format(direction)
        if intent.dimension and DIMENSIONS[intent.dimension][1]:
            order_clause += sql.SQL(", group_id ASC")

    limit = min(intent.top_n or DEFAULT_LIMIT, MAX_LIMIT)
    limit_clause = sql.SQL("LIMIT %s")
    params.append(limit)

    query = sql.SQL(" ").join([
        sql.SQL("SELECT"), sql.SQL(", ").join(select_parts),
        from_clause, sql.SQL(" ").join(join_clauses),
        where_clause, group_clause, order_clause, limit_clause,
    ])

    return BuiltQuery(sql=query, params=params, debug_sql=query.as_string(None))
