"""Two bounded inventory SELECT shapes; identifiers are internal constants."""
from psycopg import sql

from app.sql.builder import BuiltQuery, MAX_LIMIT


def build_stock_balance() -> BuiltQuery:
    query = sql.SQL("""
        WITH balances AS (
            SELECT warehouse_id, product_id,
                   SUM(CASE WHEN movement_type IN ('opening', 'receipt')
                            THEN qty::bigint ELSE -qty::bigint END) AS balance
            FROM stock_movements GROUP BY warehouse_id, product_id
        )
        SELECT w.id AS warehouse_id, w.name AS warehouse_name,
               p.id AS product_id, p.name AS product_name,
               COALESCE(b.balance, 0)::bigint AS quantity_remaining
        FROM warehouses w CROSS JOIN products p
        LEFT JOIN balances b ON b.warehouse_id = w.id AND b.product_id = p.id
        ORDER BY w.id, p.id LIMIT %s
    """)
    return BuiltQuery(query, [MAX_LIMIT], query.as_string(None))


def build_outbound_quantity(start, end) -> BuiltQuery:
    query = sql.SQL("""
        SELECT p.id AS product_id, p.name AS product_name,
               COALESCE(SUM(m.qty), 0)::bigint AS quantity_issued
        FROM products p
        LEFT JOIN stock_movements m ON m.product_id = p.id
          AND m.movement_type = %s
          AND m.movement_date >= %s AND m.movement_date < %s
        GROUP BY p.id, p.name ORDER BY p.id LIMIT %s
    """)
    return BuiltQuery(query, ["issue", start, end, MAX_LIMIT], query.as_string(None))
