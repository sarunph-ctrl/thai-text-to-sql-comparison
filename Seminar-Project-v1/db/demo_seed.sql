-- Fixed dates and fixed values. No dependence on CURRENT_DATE or random().
TRUNCATE stock_movements, warehouses, order_items, orders, products RESTART IDENTITY;
INSERT INTO products (id, name, price) VALUES
    (1, 'ปากกา', 18), -- current price differs from historical selling price 15
    (2, 'สมุด', 35), (3, 'ดินสอ', 10), (4, 'แฟ้ม', 50), (5, 'ยางลบ', 5);
INSERT INTO orders (id, order_date, status) VALUES
    (1, '2026-09-01', 'paid'),
    (2, '2026-09-05', 'paid'),
    (3, '2026-09-10', 'paid'),
    (4, '2026-09-15', 'paid'),
    (5, '2026-09-20', 'paid'),
    (6, '2026-09-30', 'paid'),
    (7, '2026-09-12', 'cancelled'),
    (8, '2026-09-18', 'pending'),
    (9, '2026-08-31', 'paid'),
    (10, '2026-10-01', 'paid');
INSERT INTO order_items (order_id, product_id, qty, unit_price) VALUES
    (1, 1, 10, 15), (1, 2, 2, 35),  -- 220
    (2, 3, 10, 10), (2, 4, 2, 50),  -- 200
    (3, 1, 4, 15),  (3, 2, 4, 35),  -- 200
    (4, 4, 4, 50),  (4, 5, 10, 5),  -- 250
    (5, 2, 6, 35),  (5, 3, 5, 10),  -- 260
    (6, 1, 5, 15),  (6, 5, 9, 5),   -- 120
    (7, 1, 100, 15), (7, 2, 10, 35), -- cancelled: 1850 excluded
    (8, 4, 10, 50), (8, 5, 20, 5),  -- pending: 600 excluded
    (9, 1, 2, 15), (9, 2, 2, 35),   -- August: 100 excluded
    (10, 4, 1, 50);                  -- October: 50 excluded
SELECT setval(pg_get_serial_sequence('products', 'id'), 5);
SELECT setval(pg_get_serial_sequence('orders', 'id'), 10);
-- September paid totals: notebook 420, folder 300, pen 285, pencil 150,
-- eraser 95. Sum = 1250. Top 3 by revenue: notebook, folder, pen.
