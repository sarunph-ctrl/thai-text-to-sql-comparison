import json
from decimal import Decimal

import psycopg
import pytest

from app.llm.comparison import resultsets_equal
from app.llm.pipeline import run_llm_pipeline
from app.llm.prompt import prompt_bundle, TABLE_COLUMNS
from app.llm.sql_guard import check_sql, execute_checked, SQLRejected
from tests.fixtures import fresh_conn


@pytest.fixture
def conn():
    c = fresh_conn(demo=True)
    yield c
    c.close()


@pytest.mark.parametrize("query", [
    "SELECT COUNT(*) FROM orders",
    "SELECT SUM(qty * unit_price) FROM order_items",
    "WITH b AS (SELECT product_id, SUM(qty) AS balance FROM stock_movements GROUP BY product_id) SELECT * FROM b",
    "SELECT SUM(CASE WHEN movement_type = 'issue' THEN -qty::bigint ELSE qty::bigint END) FROM stock_movements",
    "SELECT * FROM public.products",
])
def test_aggregate_and_cte_queries_are_accepted(query):
    assert check_sql(query).tables


@pytest.mark.parametrize("query", [
    "DELETE FROM orders", "SELECT * FROM orders; DROP TABLE products",
    "WITH gone AS (DELETE FROM orders RETURNING *) SELECT * FROM gone",
    "SELECT * INTO stolen FROM products", "SELECT * FROM products FOR UPDATE",
    "SELECT * FROM pg_catalog.pg_authid", "SELECT * FROM information_schema.tables",
    "SELECT * FROM other.products", "SELECT * FROM pg_shadow",
    "SELECT pg_sleep(10) FROM products", "SELECT pg_read_file('/etc/passwd') FROM products",
    "SELECT pg_catalog.pg_sleep(10) FROM products", "SELECT set_config('search_path','pg_catalog',false) FROM products",
    "SELECT * FROM generate_series(1,1000000)", "SELECT 1",
    "WITH RECURSIVE b AS (SELECT * FROM products) SELECT * FROM b",
    "SELECT * FROM products UNION SELECT * FROM products",
    "SELECT id::regclass FROM products", "SELECT * FROM products LIMIT -1",
    "SELECT secret FROM products", "SELECT * FROM products WHERE id = $1",
    "WITH orders AS (SELECT * FROM pg_authid) SELECT * FROM orders",
])
def test_non_reading_or_unbounded_side_effect_shapes_blocked(query):
    with pytest.raises(SQLRejected):
        check_sql(query)


def test_actual_execution_returns_real_rows_and_closes_transaction(conn):
    result = execute_checked(conn, check_sql("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'"))
    assert result["rows"] == [(1,)]
    assert conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def test_actual_schema_matches_prompt_column_allowlist(conn):
    for table, columns in TABLE_COLUMNS.items():
        actual = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s", (table,)).fetchall()
        assert {c[0] for c in actual} == columns


def test_limit_is_capped_without_losing_order(conn):
    checked = check_sql("SELECT id FROM products ORDER BY id DESC LIMIT 999999")
    assert checked.row_cap_applied and "ORDER BY id DESC" in checked.executed_sql
    assert execute_checked(conn, checked)["rows"] == [(5,), (4,), (3,), (2,), (1,)]


def test_unknown_database_column_is_caught_without_poisoning_connection(conn):
    # Alias name is known syntactically, but PostgreSQL must still resolve it.
    r = run_llm_pipeline("ยอดขายเดือนกันยายน 2569", conn,
        manual_output=json.dumps({"status": "ok", "sql": "SELECT missing AS missing FROM products"}))
    assert r["status"] == "sql_error"
    assert conn.execute("SELECT count(*) FROM products").fetchone()[0] == 5


def test_manual_reply_executes_but_never_claims_real_api_usage(conn):
    r = run_llm_pipeline("ยอดขายเดือนกันยายน 2569", conn,
        manual_output=json.dumps({"status": "ok", "sql": "SELECT SUM(i.qty*i.unit_price) FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.status='paid' AND o.order_date >= DATE '2026-09-01' AND o.order_date < DATE '2026-10-01'"}))
    assert r["status"] == "ok", r
    assert r["rows"] == [(Decimal("1250"),)]
    assert r["mode"] == "manual_output" and r["generation"] is None


def test_invalid_reply_and_rejected_query_never_execute(conn):
    for raw in ["Not SQL", json.dumps({"status": "ok", "sql": "DELETE FROM products"})]:
        r = run_llm_pipeline("คำถาม", conn, manual_output=raw)
        assert r["status"] in ("blocked", "llm_error")
    assert conn.execute("SELECT count(*) FROM products").fetchone()[0] == 5


def test_result_comparison_preserves_duplicates_and_numeric_types():
    opts = dict(actual_columns=1, expected_columns=1, ordered=False)
    assert resultsets_equal([(Decimal("1.00"),)], [(1,)], **opts)
    assert not resultsets_equal([("1.00",)], [(1,)], **opts)
    assert not resultsets_equal([(1,), (1,)], [(1,)], **opts)
    assert resultsets_equal([(2,), (1,)], [(1,), (2,)], **opts)
    assert not resultsets_equal([(2,), (1,)], [(1,), (2,)], **{**opts, "ordered": True})


def test_prompt_does_not_include_seed_rows_or_reference_answers():
    bundle = prompt_bundle("ยอดขายเดือนกันยายน 2569")
    text = bundle["messages"][0]["content"]
    assert "CREATE TABLE" in text and "1250" not in text and "INSERT INTO" not in text
    assert len(bundle["prompt_sha256"]) == 64


def test_multiple_candidates_share_one_snapshot_without_losing_schema(conn):
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        for _ in range(2):
            result = execute_checked(conn, check_sql("SELECT COUNT(*) FROM orders"))
            assert result["rows"] == [(10,)]
