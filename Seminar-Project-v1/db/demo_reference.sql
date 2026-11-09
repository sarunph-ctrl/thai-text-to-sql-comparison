-- Ground truth authored separately from the rule-based query builder.
-- Total paid September revenue: 1250.00
SELECT SUM(i.qty * i.unit_price) AS revenue
FROM order_items AS i
INNER JOIN orders AS o ON o.id = i.order_id
WHERE o.status = 'paid'
  AND o.order_date >= DATE '2026-09-01'
  AND o.order_date < DATE '2026-10-01';

-- By product: (2,สมุด,420), (4,แฟ้ม,300), (1,ปากกา,285),
--             (3,ดินสอ,150), (5,ยางลบ,95).
SELECT p.id, p.name, SUM(i.qty * i.unit_price) AS revenue
FROM products AS p
INNER JOIN order_items AS i ON p.id = i.product_id
INNER JOIN orders AS o ON o.id = i.order_id
WHERE o.status = 'paid'
  AND o.order_date >= DATE '2026-09-01'
  AND o.order_date < DATE '2026-10-01'
GROUP BY p.id, p.name
ORDER BY revenue DESC, p.id ASC;

-- Top 3 by revenue: notebook 420, folder 300, pen 285.
SELECT p.id, p.name, SUM(i.qty * i.unit_price) AS revenue
FROM products AS p
INNER JOIN order_items AS i ON p.id = i.product_id
INNER JOIN orders AS o ON o.id = i.order_id
WHERE o.status = 'paid'
  AND o.order_date >= DATE '2026-09-01'
  AND o.order_date < DATE '2026-10-01'
GROUP BY p.id, p.name
ORDER BY revenue DESC, p.id ASC
LIMIT 3;
