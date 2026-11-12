"""AST allowlist for fixed, parameterized WMS Rule-based query templates."""
from __future__ import annotations

from dataclasses import dataclass
import re

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope


MAX_ROWS = 200
TABLE_COLUMNS = {
    "part_master": {"part_id", "part_name", "uom", "weight_kg", "created_at", "updated_at"},
    "part_obj": {"serial_no", "part_id", "created_at", "updated_at"},
    "location": {"location_id", "zone_type", "pick_sequence", "max_capacity", "created_at", "updated_at"},
    "current_stock": {"serial_no", "condition", "location_id", "status", "created_at", "updated_at"},
    "inbound_order": {"inbound_id", "invoice_no", "arrival_date", "status", "container_no", "created_at", "updated_at"},
    "inbound_plan": {"plan_id", "inbound_id", "part_id", "expected_qty", "created_at", "updated_at"},
    "inbound_detail": {"in_detail_id", "inbound_id", "serial_no", "condition", "damage_image_url", "time_received_by", "created_at", "updated_at"},
    "outbound_order": {"outbound_id", "order_date", "outstatus", "created_at", "updated_at"},
    "outbound_plan": {"plan_id", "outbound_id", "part_id", "expected_qty", "created_at", "updated_at"},
    "outbound_detail": {"out_detail_id", "outbound_id", "serial_no", "time_picked_by", "created_at", "updated_at"},
}
SAFE_FUNCTIONS = {"COUNT", "COALESCE", "CAST"}
SAFE_CASTS = {"BIGINT"}


class WMSQueryRejected(ValueError):
    pass


@dataclass(frozen=True)
class CheckedWMSTemplate:
    sql: str
    params_count: int
    tables: list[str]


def _parseable_sql(parameterized_sql: str) -> tuple[str, int]:
    if not isinstance(parameterized_sql, str) or not parameterized_sql.strip():
        raise WMSQueryRejected("SQL template is missing")
    # A single colon may introduce a named bind, but PostgreSQL's ``::type``
    # cast operator is part of the reviewed query templates and is safe here.
    if re.search(r"%\([^)]+\)s|\$\d+|(?<!:):[A-Za-z_]", parameterized_sql):
        raise WMSQueryRejected("Only positional %s bind placeholders are allowed")
    params_count = parameterized_sql.count("%s")
    return parameterized_sql.replace("%s", "NULL"), params_count


def check_wms_template(parameterized_sql: str, params: list) -> CheckedWMSTemplate:
    parseable, params_count = _parseable_sql(parameterized_sql)
    if params_count != len(params):
        raise WMSQueryRejected("Bind parameter count does not match the SQL template")
    try:
        statements = sqlglot.parse(parseable, read="postgres")
    except sqlglot.errors.SqlglotError as exc:
        raise WMSQueryRejected("SQL template cannot be parsed as PostgreSQL") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise WMSQueryRejected("Exactly one SELECT is allowed")
    tree = statements[0]

    blocked = (exp.DDL, exp.DML, exp.Command, exp.Into, exp.Lock, exp.Union,
               exp.Intersect, exp.Except, exp.Parameter, exp.Placeholder)
    for node in tree.walk():
        if isinstance(node, blocked):
            raise WMSQueryRejected(f"Unsupported SQL construct: {type(node).__name__}")
        if isinstance(node, exp.With) and node.args.get("recursive"):
            raise WMSQueryRejected("Recursive CTEs are not supported")
        # sqlglot models boolean connectors such as AND as Func subclasses;
        # they are operators, not callable SQL functions.
        if isinstance(node, exp.Func) and not isinstance(node, exp.Connector):
            if isinstance(node, exp.Anonymous) or node.sql_name() not in SAFE_FUNCTIONS:
                raise WMSQueryRejected("Function is outside the WMS allowlist")
        if isinstance(node, exp.Cast):
            target = node.args.get("to")
            kind = getattr(getattr(target, "this", None), "name", "")
            if kind not in SAFE_CASTS:
                raise WMSQueryRejected("Cast type is outside the WMS allowlist")
        if isinstance(node, exp.Identifier) and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", node.name):
            raise WMSQueryRejected("Identifiers must be simple schema identifiers")

    physical: set[str] = set()
    for scope in traverse_scope(tree):
        for source in scope.sources.values():
            if isinstance(source, Scope):
                continue
            if not isinstance(source, exp.Table) or source.catalog or source.db not in ("", "public"):
                raise WMSQueryRejected("Only allowlisted physical tables are supported")
            if source.name not in TABLE_COLUMNS:
                raise WMSQueryRejected("Table is outside the ten-table WMS schema")
            physical.add(source.name)
    if not physical:
        raise WMSQueryRejected("A query must read at least one WMS table")

    known_columns = set().union(*TABLE_COLUMNS.values())
    known_columns.update(alias.alias for alias in tree.find_all(exp.Alias))
    for cte in tree.find_all(exp.CTE):
        known_columns.update(cte.alias_column_names)
    for column in tree.find_all(exp.Column):
        if not column.is_star and column.name not in known_columns:
            raise WMSQueryRejected(f"Column is outside the WMS schema: {column.name}")

    limit = tree.args.get("limit")
    limit_value = limit.expression if limit else None
    if not isinstance(limit_value, exp.Literal) or not limit_value.is_int:
        raise WMSQueryRejected("Every WMS query must have an integer LIMIT")
    if not 0 <= int(limit_value.this) <= MAX_ROWS:
        raise WMSQueryRejected("LIMIT exceeds the WMS row cap")
    return CheckedWMSTemplate(parameterized_sql, params_count, sorted(physical))
