-- PostgreSQL schema for the Thai NL -> SQL seminar demo (v2: business domain).
--
-- Changes from v1
--   * products.price and order_items.unit_price (price AT TIME OF SALE) so revenue can
--     be computed per product / category, not just from a hard-coded orders.total.
--   * orders.status + orders.payment_method  (paid / pending / cancelled ...).
--   * New dimension tables: categories, suppliers, branches, employees.
--   * customers.province.
--
-- Indexes mirror the JOIN_GRAPH in app/sql/schema.py + the time axis, so every
-- generated query runs on the minimal plan.
--
-- NOTE: Docker only runs this on a FRESH volume. If you already started v1, run
--   docker compose down -v && docker compose up -d
-- to rebuild with the new schema.

-- Enables fuzzy name matching in app/nlp/entity_resolver.py (similarity()).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS customers (
    id       SERIAL PRIMARY KEY,
    name     TEXT NOT NULL,
    province TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS suppliers (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS branches (
    id     SERIAL PRIMARY KEY,
    name   TEXT NOT NULL UNIQUE,
    region TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    branch_id INTEGER NOT NULL REFERENCES branches(id)
);

CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    price       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    stock       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id             SERIAL PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers(id),
    employee_id    INTEGER REFERENCES employees(id),
    order_date     DATE NOT NULL,
    status         TEXT NOT NULL DEFAULT 'paid'
                   CHECK (status IN ('pending', 'paid', 'cancelled')),
    payment_method TEXT
                   CHECK (payment_method IN ('cash', 'transfer', 'credit_card', 'promptpay')),
    total          NUMERIC(12, 2) NOT NULL DEFAULT 0   -- = SUM(order_items.qty * unit_price)
);

CREATE TABLE IF NOT EXISTS order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0
);

-- Covering indexes for the join graph + time filters.
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_employee_id ON orders(employee_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date  ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status      ON orders(status);
CREATE INDEX IF NOT EXISTS idx_items_order_id     ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product_id   ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_products_category  ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_supplier  ON products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_products_stock     ON products(stock);
CREATE INDEX IF NOT EXISTS idx_employees_branch   ON employees(branch_id);

-- A read-only role the app should connect as (run once as the DB owner):
--   CREATE ROLE readonly LOGIN PASSWORD 'change-me';
--   GRANT CONNECT ON DATABASE shop TO readonly;
--   GRANT USAGE ON SCHEMA public TO readonly;
--   GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;
