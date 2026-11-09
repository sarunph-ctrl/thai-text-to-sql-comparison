-- Seed data for the Thai NL -> SQL demo (v2).
--
-- * Orders 1-7 are your ORIGINAL v1 orders (same customers / items). Their totals are
--   now DERIVED from order_items, and the implied unit prices are stored on products
--   (e.g. order 1 = 3*15 + 2*35 = 115 -> pen 15, notebook 35).
-- * Orders 8+ are generated deterministically across the last 14 months so that
--   "this month / last month / this year / last year / top-N / by month" all have data.
-- * All dates are RELATIVE to CURRENT_DATE. seed_day() never returns a future date
--   (v1 used month_start + N days, which is in the future early in the month).

TRUNCATE order_items, orders, employees, branches, products, suppliers, categories, customers
    RESTART IDENTITY CASCADE;

-- Helper: day `d` (1-28) of the month `m` months from now, clipped to today.
CREATE OR REPLACE FUNCTION seed_day(m INT, d INT) RETURNS DATE AS $$
    SELECT LEAST(
        (DATE_TRUNC('month', CURRENT_DATE) + make_interval(months => m) + make_interval(days => d - 1))::DATE,
        CURRENT_DATE);
$$ LANGUAGE sql STABLE;

-- 1. Customers  (ids: 1=สมชาย 2=สมหญิง 3=John Smith 4=วิชัย 5=มานี 6=สุดา 7=Emily Chen 8=ธนากร)
INSERT INTO customers (name, province) VALUES
('สมชาย',      'กรุงเทพมหานคร'),
('สมหญิง',     'เชียงใหม่'),
('John Smith', 'ภูเก็ต'),
('วิชัย',      'ขอนแก่น'),
('มานี',       'กรุงเทพมหานคร'),
('สุดา',       'ชลบุรี'),
('Emily Chen', 'เชียงใหม่'),
('ธนากร',      'ขอนแก่น');          -- has NO orders (for "customers who never ordered")

-- 2. Categories / suppliers / branches / employees
INSERT INTO categories (name) VALUES
('เครื่องเขียน'), ('กระดาษและสมุด'), ('อุปกรณ์จัดเก็บเอกสาร'), ('อุปกรณ์สำนักงาน');

INSERT INTO suppliers (name) VALUES
('ไทยสเตชันเนอรี่'), ('ออฟฟิศเมท'), ('เปเปอร์แลนด์');

INSERT INTO branches (name, region) VALUES
('สาขากรุงเทพ',   'กลาง'),
('สาขาเชียงใหม่', 'เหนือ'),
('สาขาขอนแก่น',   'ตะวันออกเฉียงเหนือ');

INSERT INTO employees (name, branch_id) VALUES
('ณัฐพล',     1),
('พิมพ์ชนก',  1),
('อนุชา',     2),
('Kevin Lee', 3);

-- 3. Products (ids 1-7 = original v1 products, now with category / supplier / price)
INSERT INTO products (name, category_id, supplier_id, price, stock) VALUES
('ปากกาสีน้ำเงิน',   1, 1,  15,   3),
('สมุดโน้ต',         2, 3,  35,   8),
('ดินสอ 2B',         1, 1,   8,  50),
('ยางลบ',            1, 1,   5,   2),
('ไม้บรรทัด',        1, 2,  12, 100),
('กระดาษ A4',        2, 3, 120,   5),
('แฟ้มเอกสาร',       3, 2,  45,  25),
('เครื่องเย็บเล่ม',   4, 2,  89,  12),   -- never sold
('ปากกาไฮไลท์',      1, 1,  25,  40),   -- never sold
('สมุดปกแข็ง',       2, 3,  79,   0);   -- never sold, out of stock

-- 4. Original v1 orders (ids 1-7)
INSERT INTO orders (customer_id, employee_id, order_date, status, payment_method) VALUES
(1, 1, seed_day(0, 3),  'paid',    'cash'),        -- 1  สมชาย  this month
(1, 1, seed_day(0, 11), 'paid',    'transfer'),    -- 2  สมชาย  this month
(1, 2, CURRENT_DATE,    'pending', NULL),          -- 3  สมชาย  today
(1, 2, seed_day(-1, 6), 'paid',    'cash'),        -- 4  สมชาย  last month
(2, 3, seed_day(0, 4),  'paid',    'promptpay'),   -- 5  สมหญิง this month
(4, 4, CURRENT_DATE,    'paid',    'cash'),        -- 6  วิชัย   today
(3, 1, seed_day(0, 2),  'paid',    'credit_card'); -- 7  John    this month

INSERT INTO order_items (order_id, product_id, qty, unit_price)
SELECT v.o, v.p, v.q, pr.price
FROM (VALUES
    (1, 1, 3), (1, 2, 2),   -- order 1: ปากกา x3, สมุดโน้ต x2   = 115
    (2, 6, 1), (2, 7, 2),   -- order 2: กระดาษ A4 x1, แฟ้ม x2   = 210
    (3, 3, 5),              -- order 3: ดินสอ x5                =  40
    (4, 4, 4),              -- order 4: ยางลบ x4                =  20
    (5, 5, 6),              -- order 5: ไม้บรรทัด x6            =  72
    (6, 7, 1), (6, 2, 1),   -- order 6: แฟ้ม x1, สมุดโน้ต x1    =  80
    (7, 6, 2)               -- order 7: กระดาษ A4 x2            = 240
) AS v(o, p, q)
JOIN products pr ON pr.id = v.p;

-- 5. Generated orders (ids 8..77): deterministic, spread over the last 14 months
-- customer_id cycles 1..7 (customer 8 = ธนากร intentionally gets zero orders,
-- for testing "customers who never ordered"). NOTE: g*7 mod 7 is always 0 -
-- that was the original bug here; g mod 7 actually cycles.
INSERT INTO orders (customer_id, employee_id, order_date, status, payment_method)
SELECT 1 + (g % 7),
       1 + (g * 3) % 4,
       seed_day(-((g * 5) % 14), 1 + (g * 11) % 28),
       CASE WHEN g % 13 = 0 THEN 'cancelled' WHEN g % 9 = 0 THEN 'pending' ELSE 'paid' END,
       CASE WHEN g % 9 = 0 THEN NULL
            ELSE (ARRAY['cash', 'transfer', 'credit_card', 'promptpay'])[1 + g % 4] END
FROM generate_series(1, 70) AS g
ORDER BY g;

-- 1-3 distinct products per generated order
INSERT INTO order_items (order_id, product_id, qty, unit_price)
SELECT o.id,
       1 + ((o.id - 7) + k * 3) % 7,
       1 + ((o.id - 7) * k) % 5,
       pr.price
FROM orders o
CROSS JOIN LATERAL generate_series(1, 1 + (o.id - 7) % 3) AS k
JOIN products pr ON pr.id = 1 + ((o.id - 7) + k * 3) % 7
WHERE o.id >= 8
ORDER BY o.id, k;

-- 6. Derive order totals from their items (no more hard-coded totals)
UPDATE orders o
SET total = COALESCE((SELECT SUM(oi.qty * oi.unit_price) FROM order_items oi WHERE oi.order_id = o.id), 0);

DROP FUNCTION seed_day(INT, INT);
