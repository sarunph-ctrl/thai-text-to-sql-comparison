"""Fixed-shape, parameterized SQL builders for reviewed WMS query families."""
from __future__ import annotations

from dataclasses import dataclass

from app.wms.parser import WMSIntent


MAX_ROWS = 200


@dataclass(frozen=True)
class WMSQuery:
    sql: str
    params: list
    ordered: bool


STOCK_SUMMARY = """
SELECT
    pm.part_id,
    pm.part_name,
    cs.status,
    COUNT(DISTINCT cs.serial_no)::bigint AS serial_count
FROM current_stock AS cs
JOIN part_obj AS po ON po.serial_no = cs.serial_no
JOIN part_master AS pm ON pm.part_id = po.part_id
GROUP BY pm.part_id, pm.part_name, cs.status
ORDER BY pm.part_id, cs.status
LIMIT 200
""".strip()

STOCK_DETAIL = """
SELECT
    cs.serial_no,
    pm.part_id,
    pm.part_name,
    cs.location_id,
    cs.condition,
    cs.status
FROM current_stock AS cs
JOIN part_obj AS po ON po.serial_no = cs.serial_no
JOIN part_master AS pm ON pm.part_id = po.part_id
WHERE cs.status = %s
ORDER BY cs.serial_no
LIMIT 200
""".strip()

INBOUND_PROGRESS = """
WITH received AS (
    SELECT
        id.inbound_id,
        po.part_id,
        COUNT(DISTINCT id.serial_no)::bigint AS received_qty
    FROM inbound_detail AS id
    JOIN part_obj AS po ON po.serial_no = id.serial_no
    GROUP BY id.inbound_id, po.part_id
)
SELECT
    io.inbound_id,
    io.status,
    pm.part_id,
    pm.part_name,
    ip.expected_qty,
    COALESCE(r.received_qty, 0)::bigint AS received_qty,
    (ip.expected_qty - COALESCE(r.received_qty, 0))::bigint AS remaining_qty
FROM inbound_plan AS ip
JOIN inbound_order AS io ON io.inbound_id = ip.inbound_id
JOIN part_master AS pm ON pm.part_id = ip.part_id
LEFT JOIN received AS r
  ON r.inbound_id = ip.inbound_id AND r.part_id = ip.part_id
ORDER BY io.inbound_id, pm.part_id
LIMIT 200
""".strip()

OUTBOUND_PROGRESS = """
WITH picked AS (
    SELECT
        od.outbound_id,
        po.part_id,
        COUNT(DISTINCT od.serial_no)::bigint AS picked_qty
    FROM outbound_detail AS od
    JOIN part_obj AS po ON po.serial_no = od.serial_no
    GROUP BY od.outbound_id, po.part_id
)
SELECT
    oo.outbound_id,
    oo.outstatus,
    pm.part_id,
    pm.part_name,
    op.expected_qty,
    COALESCE(p.picked_qty, 0)::bigint AS picked_qty,
    (op.expected_qty - COALESCE(p.picked_qty, 0))::bigint AS remaining_qty
FROM outbound_plan AS op
JOIN outbound_order AS oo ON oo.outbound_id = op.outbound_id
JOIN part_master AS pm ON pm.part_id = op.part_id
LEFT JOIN picked AS p
  ON p.outbound_id = op.outbound_id AND p.part_id = op.part_id
ORDER BY oo.outbound_id, pm.part_id
LIMIT 200
""".strip()

ORDER_STATUS = """
SELECT
    oo.outstatus,
    COUNT(*)::bigint AS order_count
FROM outbound_order AS oo
WHERE oo.order_date >= %s
  AND oo.order_date < %s
GROUP BY oo.outstatus
ORDER BY oo.outstatus
LIMIT 200
""".strip()


def build_wms_query(intent: WMSIntent) -> WMSQuery:
    if intent.family == "current_stock_summary":
        return WMSQuery(STOCK_SUMMARY, [], False)
    if intent.family == "current_stock_detail":
        return WMSQuery(STOCK_DETAIL, [intent.filters["status"]], True)
    if intent.family == "inbound_progress":
        return WMSQuery(INBOUND_PROGRESS, [], False)
    if intent.family == "outbound_progress":
        return WMSQuery(OUTBOUND_PROGRESS, [], False)
    if intent.family == "operational_order_status":
        return WMSQuery(
            ORDER_STATUS,
            [intent.filters["start_date"], intent.filters["end_date"]],
            False,
        )
    raise ValueError(f"unknown WMS family: {intent.family}")
