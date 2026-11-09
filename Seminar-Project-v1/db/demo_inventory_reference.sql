-- Independently authored reference: opening+receipt-issue per product/warehouse.
-- Uses a correlated aggregate instead of the generated CTE + LEFT JOIN.
SELECT w.id, w.name, p.id, p.name,
       COALESCE((SELECT SUM(CASE m.movement_type WHEN 'issue' THEN -m.qty::bigint ELSE m.qty::bigint END)
                 FROM stock_movements m
                 WHERE m.warehouse_id = w.id AND m.product_id = p.id), 0)::bigint AS balance
FROM products p CROSS JOIN warehouses w ORDER BY w.id, p.id;

-- September outbound, all warehouses, includes zero-dispatch products.
SELECT p.id, p.name,
       COALESCE((SELECT SUM(m.qty) FROM stock_movements m
                 WHERE m.product_id = p.id AND m.movement_type = 'issue'
                   AND m.movement_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'), 0)::bigint AS issued
FROM products p ORDER BY p.id;
