#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /project-db/demo_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /project-db/demo_seed.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /project-db/demo_inventory_seed.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /project-db/wms_mvp_schema.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /project-db/wms_mvp_seed.sql

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=reader_password="$DEMO_READER_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE seminar_reader LOGIN PASSWORD %L', :'reader_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seminar_reader')
\gexec

ALTER ROLE seminar_reader SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE seminar_demo TO seminar_reader;
GRANT USAGE ON SCHEMA public TO seminar_reader;
GRANT SELECT ON
  products, orders, order_items, warehouses, stock_movements,
  part_master, part_obj, location, current_stock,
  inbound_order, inbound_plan, inbound_detail,
  outbound_order, outbound_plan, outbound_detail
TO seminar_reader;
SQL
