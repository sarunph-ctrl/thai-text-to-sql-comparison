-- Deterministic inventory fixtures; this script never changes sales data.
-- Run on empty inventory tables only (upgrade or full demo reset).
INSERT INTO warehouses (id, name) VALUES (1, 'คลังหลัก'), (2, 'คลังสำรอง');

INSERT INTO stock_movements (product_id, warehouse_id, movement_date, movement_type, qty) VALUES
    (1, 1, '2026-08-01', 'opening', 100),
    (2, 1, '2026-08-01', 'opening', 60),
    (3, 1, '2026-08-01', 'opening', 80),
    (4, 1, '2026-08-01', 'opening', 30),
    (5, 1, '2026-08-01', 'opening', 100),
    (1, 2, '2026-08-01', 'opening', 40),
    (2, 2, '2026-08-01', 'opening', 20),
    (4, 2, '2026-08-01', 'opening', 10),
    (1, 1, '2026-09-02', 'receipt', 50),
    (2, 1, '2026-09-03', 'receipt', 20),
    (4, 1, '2026-09-04', 'receipt', 10),
    (3, 2, '2026-09-05', 'receipt', 30);

-- Explicit dispatch events for the six original paid September orders.
-- Paid status itself does NOT generate these automatically.
INSERT INTO stock_movements
    (product_id, warehouse_id, movement_date, movement_type, qty, order_item_id)
SELECT i.product_id, 1, o.order_date, 'issue', i.qty, i.id
FROM order_items i JOIN orders o ON o.id = i.order_id
WHERE o.id BETWEEN 1 AND 6;

-- Partial dispatch of an unpaid order: 3 folders of 10 ordered.
INSERT INTO stock_movements
    (product_id, warehouse_id, movement_date, movement_type, qty, order_item_id)
SELECT i.product_id, 2, DATE '2026-09-21', 'issue', 3, i.id
FROM order_items i WHERE i.order_id = 8 AND i.product_id = 4;

-- Boundary cases: August issues must not count as September outbound.
INSERT INTO stock_movements
    (product_id, warehouse_id, movement_date, movement_type, qty, order_item_id)
SELECT i.product_id, 2, DATE '2026-08-31', 'issue', i.qty, i.id
FROM order_items i WHERE i.order_id = 9;

-- October issue affects latest recorded stock, but not September outbound.
INSERT INTO stock_movements
    (product_id, warehouse_id, movement_date, movement_type, qty, order_item_id)
SELECT i.product_id, 1, DATE '2026-10-01', 'issue', i.qty, i.id
FROM order_items i WHERE i.order_id = 10;

-- A non-sales issue: stock can leave the warehouse for another purpose.
INSERT INTO stock_movements (product_id, warehouse_id, movement_date, movement_type, qty)
VALUES (1, 2, DATE '2026-09-23', 'issue', 3);

SELECT setval(pg_get_serial_sequence('warehouses', 'id'), 2);
-- Baseline balances, product ids 1..5:
-- main:    131, 68, 65, 33, 81
-- reserve:  35, 18, 30,  7,  0 (eraser has no movement, still shown)
-- September issued quantities, all warehouses: 22, 12, 15, 9, 19.
