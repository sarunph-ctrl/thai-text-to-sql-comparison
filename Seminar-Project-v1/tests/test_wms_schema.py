"""Integrity and baseline-result tests for the reproducible WMS MVP schema."""
from __future__ import annotations

import psycopg
import pytest

from tests.fixtures import fresh_wms_conn


EXPECTED_TABLES = {
    "part_master",
    "part_obj",
    "location",
    "current_stock",
    "inbound_order",
    "inbound_plan",
    "inbound_detail",
    "outbound_order",
    "outbound_plan",
    "outbound_detail",
}


@pytest.fixture
def db():
    conn = fresh_wms_conn()
    try:
        yield conn
    finally:
        conn.close()


def test_schema_contains_only_the_ten_mvp_tables(db):
    rows = db.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
    ).fetchall()
    assert {row[0] for row in rows} == EXPECTED_TABLES


def test_seed_counts_are_deterministic(db):
    counts = {
        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in EXPECTED_TABLES
    }
    assert counts == {
        "part_master": 4,
        "part_obj": 6,
        "location": 4,
        "current_stock": 6,
        "inbound_order": 3,
        "inbound_plan": 5,
        "inbound_detail": 6,
        "outbound_order": 2,
        "outbound_plan": 4,
        "outbound_detail": 2,
    }


def test_current_stock_summary_baseline(db):
    rows = db.execute(
        """
        SELECT p.part_id, cs.status, count(*) AS serial_count
        FROM current_stock cs
        JOIN part_obj po ON po.serial_no = cs.serial_no
        JOIN part_master p ON p.part_id = po.part_id
        GROUP BY p.part_id, cs.status
        ORDER BY p.part_id, cs.status
        """
    ).fetchall()
    assert rows == [
        ("PART-A", "Available", 2),
        ("PART-A", "In Transit", 1),
        ("PART-A", "Receiving", 1),
        ("PART-B", "In Transit", 1),
        ("PART-B", "Quarantine", 1),
    ]


def test_available_good_stock_baseline(db):
    count = db.execute(
        """
        SELECT count(DISTINCT cs.serial_no)
        FROM current_stock cs
        WHERE cs.status = 'Available' AND cs.condition = 'Good'
        """
    ).fetchone()[0]
    assert count == 2


def test_inbound_plan_vs_received_baseline(db):
    rows = db.execute(
        """
        SELECT ip.inbound_id, ip.part_id, ip.expected_qty,
               count(po.serial_no) AS received_qty
        FROM inbound_plan ip
        LEFT JOIN inbound_detail id ON id.inbound_id = ip.inbound_id
        LEFT JOIN part_obj po
          ON po.serial_no = id.serial_no AND po.part_id = ip.part_id
        GROUP BY ip.inbound_id, ip.part_id, ip.expected_qty
        ORDER BY ip.inbound_id, ip.part_id
        """
    ).fetchall()
    assert rows == [
        ("INB-001", "PART-A", 3, 3),
        ("INB-001", "PART-B", 2, 2),
        ("INB-002", "PART-A", 2, 1),
        ("INB-002", "PART-C", 1, 0),
        ("INB-003", "PART-D", 2, 0),
    ]


def test_outbound_plan_vs_picked_baseline(db):
    rows = db.execute(
        """
        SELECT op.outbound_id, op.part_id, op.expected_qty,
               count(po.serial_no) AS picked_qty
        FROM outbound_plan op
        LEFT JOIN outbound_detail od ON od.outbound_id = op.outbound_id
        LEFT JOIN part_obj po
          ON po.serial_no = od.serial_no AND po.part_id = op.part_id
        GROUP BY op.outbound_id, op.part_id, op.expected_qty
        ORDER BY op.outbound_id, op.part_id
        """
    ).fetchall()
    assert rows == [
        ("OUT-001", "PART-A", 1, 1),
        ("OUT-001", "PART-B", 1, 1),
        ("OUT-002", "PART-A", 1, 0),
        ("OUT-002", "PART-C", 1, 0),
    ]


def test_invalid_status_is_rejected(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "UPDATE current_stock SET status = 'Unknown' "
            "WHERE serial_no = 'SYN-A-001'"
        )


def test_orphan_plan_is_rejected(db):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute(
            "INSERT INTO outbound_plan (outbound_id, part_id, expected_qty) "
            "VALUES ('OUT-MISSING', 'PART-A', 1)"
        )
