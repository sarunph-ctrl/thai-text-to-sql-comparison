"""Day-one correctness checks against a real PostgreSQL, not mocked SQL."""
from decimal import Decimal

import psycopg
import pytest

from app.nlp.demo import run_demo_pipeline
from tests.fixtures import fresh_conn


@pytest.fixture
def conn():
    c = fresh_conn(demo=True)
    yield c
    c.close()


PRODUCT_TOTALS = [
    (2, "สมุด", Decimal("420")), (4, "แฟ้ม", Decimal("300")),
    (1, "ปากกา", Decimal("285")), (3, "ดินสอ", Decimal("150")),
    (5, "ยางลบ", Decimal("95")),
]


def test_total_excludes_pending_cancelled_and_adjacent_months(conn):
    r = run_demo_pipeline("ยอดขายเดือนกันยายน 2569", conn)
    assert r.status == "ok"
    assert r.rows == [(Decimal("1250"),)]
    assert r.interpretation["start_inclusive"] == "2026-09-01"
    assert r.interpretation["end_exclusive"] == "2026-10-01"


@pytest.mark.parametrize("question", [
    "ยอดขายเดือนกันยายน 2569 แยกตามสินค้า",
    "เดือนกันยายน 2569 สินค้าแต่ละตัวขายได้เงินเท่าไหร่",
    "ขอดูยอดขายแยกตามสินค้าในเดือนกันยายน 2569 ครับ",
])
def test_paraphrases_produce_complete_correct_product_results(conn, question):
    r = run_demo_pipeline(question, conn)
    assert r.status == "ok", r.message
    assert r.rows == PRODUCT_TOTALS


def test_top3_ranked_by_money_not_quantity(conn):
    r = run_demo_pipeline("สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569", conn)
    assert r.status == "ok", r.message
    assert r.rows == PRODUCT_TOTALS[:3]


def test_current_price_change_does_not_rewrite_historical_revenue(conn):
    conn.execute("UPDATE products SET price = 9999 WHERE id = 1")
    r = run_demo_pipeline("ยอดขายเดือนกันยายน 2569", conn)
    assert r.rows == [(Decimal("1250"),)]


def test_new_sale_changes_total_and_ranking(conn):
    conn.execute("INSERT INTO orders (id, order_date, status) VALUES (11, '2026-09-25', 'paid')")
    conn.execute("INSERT INTO order_items (order_id, product_id, qty, unit_price) VALUES (11, 1, 20, 15)")
    r = run_demo_pipeline("ยอดขายเดือนกันยายน 2569", conn)
    assert r.rows == [(Decimal("1550"),)]
    ranked = run_demo_pipeline("สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569", conn)
    assert ranked.rows == [(1, "ปากกา", Decimal("585")), *PRODUCT_TOTALS[:2]]


@pytest.mark.parametrize("question", [
    "เปรียบเทียบยอดขายเดือนนี้กับเดือนที่แล้ว",
    "ยอดขายเดือนกันยายน 2569 ของลูกค้าสมชาย",
    "ยอดขายเดือนกันยายน 2569 ที่มากกว่า 100 บาท",
    "ยอดขายเดือนกันยายน 2569 และเดือนตุลาคม 2569",
    "ยอดขายเดือนกันยายน", "ยอดขายเดือนนี้", "ยอดขายทั้งหมด",
    "ยอดขายวันที่ 1 กันยายน 2569",
    "ยอดขายเดือนกันยายน 2569 ที่ยกเลิก",
    "สินค้าขายดีที่สุด 0 อันดับ เดือนกันยายน 2569",
    "สินค้าขายดีที่สุด 201 อันดับ เดือนกันยายน 2569",
    "ลบยอดขายเดือนกันยายน 2569",
    "ยอดขายเดือนกันยายน 2569; DROP TABLE orders",
])
def test_unsupported_meaning_is_never_silently_discarded(conn, question):
    r = run_demo_pipeline(question, conn)
    assert r.status == "unsupported", r
    assert r.sql is None
    assert r.rows == []


def test_thai_digits_and_ce_year(conn):
    th = run_demo_pipeline("ยอดขายเดือนกันยายน ๒๕๖๙", conn)
    ce = run_demo_pipeline("ยอดขายเดือนกันยายน 2026", conn)
    assert th.status == ce.status == "ok"
    assert th.rows == ce.rows == [(Decimal("1250"),)]


def test_query_runs_read_only_and_transaction_is_closed(conn):
    r = run_demo_pipeline("ยอดขายเดือนกันยายน 2569", conn)
    assert r.status == "ok"
    assert conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def test_rank_ties_have_stable_product_id_order(conn):
    conn.execute("UPDATE order_items SET unit_price = 0")
    r = run_demo_pipeline("สินค้าขายดีที่สุด 3 อันดับ เดือนกันยายน 2569", conn)
    assert [row[0] for row in r.rows] == [1, 2, 3]
