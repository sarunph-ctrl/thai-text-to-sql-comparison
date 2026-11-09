import pytest

from app.sql.schema import join_path
from app.sql.builder import build_query, Intent, Filter, MAX_LIMIT


def test_join_path_single_hop():
    assert join_path("orders", {"customers"}) == [("orders", "customer_id", "customers", "id")]


def test_join_path_two_hop():
    path = join_path("orders", {"order_items", "products"})
    assert path == [
        ("orders", "id", "order_items", "order_id"),
        ("order_items", "product_id", "products", "id"),
    ]


def test_join_path_three_hop_via_products():
    path = join_path("orders", {"order_items", "products", "categories"})
    tables_in_order = [e[2] for e in path]
    assert tables_in_order == ["order_items", "products", "categories"]


def test_join_path_no_targets_is_empty():
    assert join_path("orders", set()) == []


def test_join_path_unknown_table_raises():
    with pytest.raises(ValueError):
        join_path("orders", {"not_a_real_table"})


def test_build_query_only_ever_selects():
    bq = build_query(Intent(metric="revenue"))
    assert bq.debug_sql.strip().upper().startswith("SELECT")
    for banned in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", ";--"):
        assert banned not in bq.debug_sql.upper()


def test_build_query_always_has_limit():
    bq = build_query(Intent(metric="revenue", dimension="product"))
    assert "LIMIT" in bq.debug_sql
    assert bq.params[-1] <= MAX_LIMIT


def test_build_query_top_n_clamped_to_max():
    bq = build_query(Intent(metric="revenue", dimension="product", top_n=10_000))
    assert bq.params[-1] == MAX_LIMIT


def test_build_query_excludes_cancelled_by_default():
    bq = build_query(Intent(metric="revenue"))
    assert "orders.status <> %s" in bq.debug_sql
    assert "cancelled" in bq.params


def test_build_query_explicit_status_filter_skips_default_exclusion():
    bq = build_query(Intent(metric="order_count", filters=[Filter("status", "eq", "cancelled")]))
    # only one status predicate - the explicit one, not the default exclusion too
    assert bq.debug_sql.count('orders."status"') + bq.debug_sql.count("orders.status") == 1


def test_build_query_rejects_unknown_metric():
    with pytest.raises(ValueError):
        build_query(Intent(metric="not_a_real_metric"))
