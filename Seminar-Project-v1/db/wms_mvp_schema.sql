-- WMS MVP schema for the Thai Text-to-SQL experiment.
--
-- Provenance: adapted from Succeed_BDMS/ALL_SQL.sql on branch develop,
-- inspected 2026-11-12. This file intentionally keeps only the ten tables
-- selected in SCOPE_WMS_MVP.md and can be run in an empty PostgreSQL schema.
-- Phase-2 dependencies (customer, shipment, provider, driver, app_user) and
-- write-side application triggers are intentionally excluded.

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE TABLE part_master (
    part_id VARCHAR PRIMARY KEY,
    part_name VARCHAR NOT NULL,
    uom VARCHAR NOT NULL,
    weight_kg NUMERIC(12,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT part_master_weight_nonnegative
        CHECK (weight_kg IS NULL OR weight_kg >= 0)
);

CREATE TABLE part_obj (
    serial_no VARCHAR PRIMARY KEY,
    part_id VARCHAR NOT NULL REFERENCES part_master(part_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE location (
    location_id VARCHAR PRIMARY KEY,
    zone_type VARCHAR NOT NULL,
    pick_sequence INTEGER,
    max_capacity INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT location_pick_sequence_positive
        CHECK (pick_sequence IS NULL OR pick_sequence > 0),
    CONSTRAINT location_capacity_positive
        CHECK (max_capacity IS NULL OR max_capacity > 0)
);

CREATE TABLE current_stock (
    serial_no VARCHAR PRIMARY KEY REFERENCES part_obj(serial_no),
    condition VARCHAR NOT NULL,
    location_id VARCHAR REFERENCES location(location_id),
    status VARCHAR NOT NULL DEFAULT 'Receiving',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT current_stock_condition_allowed
        CHECK (condition IN ('Good', 'Damaged')),
    CONSTRAINT current_stock_status_allowed
        CHECK (status IN ('Receiving', 'Available', 'In Transit', 'Quarantine'))
);

CREATE TABLE inbound_order (
    inbound_id VARCHAR PRIMARY KEY,
    invoice_no VARCHAR,
    arrival_date DATE,
    status VARCHAR NOT NULL,
    container_no VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT inbound_order_status_allowed
        CHECK (status IN ('Draft Plan', 'Received', 'Completed', 'Cancelled'))
);

CREATE TABLE inbound_plan (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inbound_id VARCHAR NOT NULL REFERENCES inbound_order(inbound_id),
    part_id VARCHAR NOT NULL REFERENCES part_master(part_id),
    expected_qty INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT inbound_plan_expected_qty_positive CHECK (expected_qty > 0),
    CONSTRAINT inbound_plan_order_part_unique UNIQUE (inbound_id, part_id)
);

CREATE TABLE inbound_detail (
    in_detail_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inbound_id VARCHAR NOT NULL REFERENCES inbound_order(inbound_id),
    serial_no VARCHAR NOT NULL REFERENCES part_obj(serial_no),
    condition VARCHAR NOT NULL,
    damage_image_url TEXT,
    time_received_by TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT inbound_detail_condition_allowed
        CHECK (condition IN ('Good', 'Damaged')),
    CONSTRAINT inbound_detail_order_serial_unique UNIQUE (inbound_id, serial_no)
);

CREATE TABLE outbound_order (
    outbound_id VARCHAR PRIMARY KEY,
    order_date DATE NOT NULL,
    outstatus VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT outbound_order_status_allowed
        CHECK (outstatus IN ('Pending', 'Picked'))
);

CREATE TABLE outbound_plan (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbound_id VARCHAR NOT NULL REFERENCES outbound_order(outbound_id),
    part_id VARCHAR NOT NULL REFERENCES part_master(part_id),
    expected_qty INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT outbound_plan_expected_qty_positive CHECK (expected_qty > 0),
    CONSTRAINT outbound_plan_order_part_unique UNIQUE (outbound_id, part_id)
);

CREATE TABLE outbound_detail (
    out_detail_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbound_id VARCHAR NOT NULL REFERENCES outbound_order(outbound_id),
    serial_no VARCHAR NOT NULL REFERENCES part_obj(serial_no),
    time_picked_by TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT outbound_detail_order_serial_unique UNIQUE (outbound_id, serial_no)
);

CREATE INDEX current_stock_location_status_idx
    ON current_stock(location_id, status);
CREATE INDEX part_obj_part_idx
    ON part_obj(part_id);
CREATE INDEX inbound_order_arrival_status_idx
    ON inbound_order(arrival_date, status);
CREATE INDEX inbound_plan_order_part_idx
    ON inbound_plan(inbound_id, part_id);
CREATE INDEX inbound_detail_order_idx
    ON inbound_detail(inbound_id);
CREATE INDEX outbound_order_date_status_idx
    ON outbound_order(order_date, outstatus);
CREATE INDEX outbound_plan_order_part_idx
    ON outbound_plan(outbound_id, part_id);
CREATE INDEX outbound_detail_order_idx
    ON outbound_detail(outbound_id);
