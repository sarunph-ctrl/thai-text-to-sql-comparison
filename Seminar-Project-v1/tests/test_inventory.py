"""Inventory correctness and integrity tests on real PostgreSQL fixtures."""
import psycopg
import pytest

from app.nlp.demo import run_demo_pipeline
from tests.fixtures import fresh_conn

BALANCE_QUESTION = "สินค้าคงเหลือแยกตามคลังมีเท่าไหร่"
ISSUE_QUESTION = "เดือนกันยายน 2569 มีสินค้าจ่ายออกแต่ละชนิดกี่หน่วย"
NAMES = ["ปากกา", "สมุด", "ดินสอ", "แฟ้ม", "ยางลบ"]
BALANCES = [
    *[(1, "คลังหลัก", i, name, qty) for i, name, qty in zip(range(1, 6), NAMES, [131, 68, 65, 33, 81])],
    *[(2, "คลังสำรอง", i, name, qty) for i, name, qty in zip(range(1, 6), NAMES, [35, 18, 30, 7, 0])],
]
ISSUED = [(i, name, qty) for i, name, qty in zip(range(1, 6), NAMES, [22, 12, 15, 9, 19])]


@pytest.fixture
def conn():
    c = fresh_conn(demo=True)
    yield c
    c.close()


@pytest.mark.parametrize("question", [
    BALANCE_QUESTION, "แสดงสต็อกคงเหลือแยกตามคลังครับ", "สินค้าคงเหลือในแต่ละคลัง",
])
def test_balances_match_full_hand_calculated_matrix(conn, question):
    r = run_demo_pipeline(question, conn)
    assert r.status == "ok", r.message
    assert r.rows == BALANCES
    assert r.interpretation["metric"] == "stock_balance"
    assert "paid" not in r.params
    assert "opening + receipt - issue" in r.business_definition


@pytest.mark.parametrize("question", [
    ISSUE_QUESTION, "ยอดจ่ายออกสินค้าเดือนกันยายน 2569", "เดือนกันยายน ๒๕๖๙ สินค้าเบิกออกกี่ชิ้น",
])
def test_outbound_uses_dispatch_date_not_order_date_or_payment(conn, question):
    r = run_demo_pipeline(question, conn)
    assert r.status == "ok", r.message
    assert r.rows == ISSUED
    # 6 paid folder units + 3 dispatched units from a pending order.
    assert r.rows[3][2] == 9
    # 19 sold pen units + 3 manual non-sales issue units.
    assert r.rows[0][2] == 22


def test_missing_movement_pair_and_empty_warehouse_are_zero(conn):
    conn.execute("INSERT INTO warehouses(id, name) VALUES (3, 'คลังว่าง')")
    r = run_demo_pipeline(BALANCE_QUESTION, conn)
    assert r.rows[:10] == BALANCES
    assert r.rows[10:] == [(3, "คลังว่าง", i, name, 0) for i, name in enumerate(NAMES, 1)]


def test_new_receipt_changes_one_balance_but_not_sales_or_outbound(conn):
    conn.execute("INSERT INTO stock_movements(product_id, warehouse_id, movement_date, movement_type, qty) "
                 "VALUES (5, 2, '2026-10-02', 'receipt', 7)")
    balance = run_demo_pipeline(BALANCE_QUESTION, conn)
    assert balance.rows[:-1] == BALANCES[:-1]
    assert balance.rows[-1] == (2, "คลังสำรอง", 5, "ยางลบ", 7)
    assert run_demo_pipeline(ISSUE_QUESTION, conn).rows == ISSUED
    assert str(run_demo_pipeline("ยอดขายเดือนกันยายน 2569", conn).rows[0][0]) == "1250.00"


def test_payment_status_does_not_change_recorded_dispatch(conn):
    conn.execute("UPDATE orders SET status = 'pending' WHERE id BETWEEN 1 AND 6")
    assert run_demo_pipeline(ISSUE_QUESTION, conn).rows == ISSUED
    assert run_demo_pipeline(BALANCE_QUESTION, conn).rows == BALANCES


def test_paid_sale_without_dispatch_does_not_reduce_stock(conn):
    conn.execute("INSERT INTO orders (id, order_date, status) VALUES (11, '2026-09-25', 'paid')")
    conn.execute("INSERT INTO order_items(order_id, product_id, qty, unit_price) VALUES (11, 1, 20, 15)")
    assert run_demo_pipeline(BALANCE_QUESTION, conn).rows == BALANCES
    assert str(run_demo_pipeline("ยอดขายเดือนกันยายน 2569", conn).rows[0][0]) == "1550.00"


def test_october_issue_is_in_balance_but_not_september_dispatch(conn):
    october = run_demo_pipeline("เดือนตุลาคม 2569 สินค้าจ่ายออกกี่หน่วย", conn)
    assert october.rows == [(i, name, 1 if i == 4 else 0) for i, name in enumerate(NAMES, 1)]
    assert run_demo_pipeline(ISSUE_QUESTION, conn).rows == ISSUED
    assert run_demo_pipeline(BALANCE_QUESTION, conn).rows[3][-1] == 33


@pytest.mark.parametrize("question", [
    "สินค้าคงเหลือเดือนกันยายน 2569", "สินค้าคงเหลือเฉพาะคลังหลัก",
    "สินค้าคงเหลือแยกตามคลังที่มากกว่า 10", "สินค้าคงเหลือแยกตามคลังและยอดขาย",
    "เดือนกันยายน 2569 สินค้าจ่ายออกเฉพาะคลังหลัก", "เดือนกันยายน 2569 สินค้าจ่ายออกที่ชำระแล้ว",
    "สินค้าจ่ายออกเดือนนี้", "สินค้าจ่ายออก 1 กันยายน 2569",
    "สินค้าจ่ายออกกันยายน 2569 และตุลาคม 2569", "สินค้าคงเหลือและจ่ายออก",
    "สินค้าคงเหลือเรียงมากไปน้อย", "สินค้าจ่ายออกกันยายน 2569 ไม่รวมปากกา",
    "ยอดจ่ายออกสินค้าเดือนกันยายน 2569 แยกตามคลัง",
    "เดือนกันยายน 2569 สินค้าจ่ายออกในแต่ละคลัง",
    "เดือนกันยายน 2569 สินค้าจ่ายออกแยกรายคลัง",
])
def test_unimplemented_stock_conditions_are_rejected_before_sql(conn, question):
    r = run_demo_pipeline(question, conn)
    assert r.status == "unsupported", r
    assert r.sql is None


@pytest.mark.parametrize("kind,qty", [("receipt", 0), ("issue", -1), ("transfer", 1)])
def test_invalid_movement_rejected(conn, kind, qty):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO stock_movements(product_id, warehouse_id, movement_date, movement_type, qty) "
                     "VALUES (1, 1, '2026-09-01', %s, %s)", (kind, qty))


def test_issue_cannot_reference_a_sales_line_for_another_product(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute("INSERT INTO stock_movements(product_id, warehouse_id, movement_date, movement_type, qty, order_item_id) "
                     "VALUES (2, 1, '2026-09-01', 'issue', 1, 1)")


def test_receipt_cannot_reference_a_sales_line(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO stock_movements(product_id, warehouse_id, movement_date, movement_type, qty, order_item_id) "
                     "VALUES (1, 1, '2026-09-01', 'receipt', 1, 1)")


def test_duplicate_opening_for_same_product_and_warehouse_rejected(conn):
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute("INSERT INTO stock_movements(product_id, warehouse_id, movement_date, movement_type, qty) "
                     "VALUES (1, 1, '2026-08-02', 'opening', 100)")


def test_unknown_warehouse_rejected(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute("INSERT INTO stock_movements(product_id, warehouse_id, movement_date, movement_type, qty) "
                     "VALUES (1, 999, '2026-09-01', 'receipt', 1)")
