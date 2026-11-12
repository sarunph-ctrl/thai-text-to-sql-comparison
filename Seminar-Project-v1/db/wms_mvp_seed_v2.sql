-- Deterministic robustness snapshot for the WMS MVP.
-- Same schema and business rules as v1, but different quantities, statuses,
-- dates, serials, and zero-result combinations. No real data is used.

INSERT INTO part_master (part_id, part_name, uom, weight_kg) VALUES
    ('PART-A', 'อะไหล่ A', 'ชิ้น', 1.250),
    ('PART-B', 'อะไหล่ B', 'ชิ้น', 0.500),
    ('PART-C', 'อะไหล่ C', 'ชิ้น', NULL),
    ('PART-D', 'อะไหล่ D', 'ชุด', 2.000);

INSERT INTO location (location_id, zone_type, pick_sequence, max_capacity) VALUES
    ('REC-01', 'Receiving', 1, 20),
    ('A-01', 'Storage', 10, 100),
    ('A-02', 'Storage', 20, 100),
    ('Q-01', 'Quarantine', 99, 20);

INSERT INTO inbound_order
    (inbound_id, invoice_no, arrival_date, status, container_no) VALUES
    ('INB-001', 'SYN2-INV-001', DATE '2026-09-01', 'Completed', 'SYN2-CONT-01'),
    ('INB-002', 'SYN2-INV-002', DATE '2026-09-30', 'Received', 'SYN2-CONT-02'),
    ('INB-003', 'SYN2-INV-003', DATE '2026-10-01', 'Cancelled', NULL);

INSERT INTO inbound_plan (plan_id, inbound_id, part_id, expected_qty) VALUES
    ('10000000-0000-0000-0000-000000000101', 'INB-001', 'PART-A', 2),
    ('10000000-0000-0000-0000-000000000102', 'INB-001', 'PART-B', 1),
    ('10000000-0000-0000-0000-000000000103', 'INB-002', 'PART-A', 1),
    ('10000000-0000-0000-0000-000000000104', 'INB-002', 'PART-C', 2),
    ('10000000-0000-0000-0000-000000000105', 'INB-003', 'PART-D', 1);

INSERT INTO part_obj (serial_no, part_id, created_at, updated_at) VALUES
    ('SYN2-A-101', 'PART-A', '2026-09-01 08:00:00+07', '2026-09-01 12:00:00+07'),
    ('SYN2-A-102', 'PART-A', '2026-09-01 08:01:00+07', '2026-09-30 17:00:00+07'),
    ('SYN2-A-103', 'PART-A', '2026-09-30 09:00:00+07', '2026-09-30 12:00:00+07'),
    ('SYN2-B-101', 'PART-B', '2026-09-01 08:02:00+07', '2026-09-01 12:02:00+07'),
    ('SYN2-C-101', 'PART-C', '2026-09-30 09:01:00+07', '2026-09-30 09:01:00+07');

INSERT INTO inbound_detail
    (in_detail_id, inbound_id, serial_no, condition, damage_image_url, time_received_by) VALUES
    ('10000000-0000-0000-0000-000000000201', 'INB-001', 'SYN2-A-101', 'Good', NULL, '2026-09-01 08:00:00+07'),
    ('10000000-0000-0000-0000-000000000202', 'INB-001', 'SYN2-A-102', 'Good', NULL, '2026-09-01 08:01:00+07'),
    ('10000000-0000-0000-0000-000000000203', 'INB-001', 'SYN2-B-101', 'Damaged', 'synthetic://damage-v2/B-101', '2026-09-01 08:02:00+07'),
    ('10000000-0000-0000-0000-000000000204', 'INB-002', 'SYN2-A-103', 'Good', NULL, '2026-09-30 09:00:00+07'),
    ('10000000-0000-0000-0000-000000000205', 'INB-002', 'SYN2-C-101', 'Good', NULL, '2026-09-30 09:01:00+07');

INSERT INTO outbound_order (outbound_id, order_date, outstatus) VALUES
    ('OUT-001', DATE '2026-09-30', 'Picked'),
    ('OUT-002', DATE '2026-10-01', 'Pending');

INSERT INTO outbound_plan (plan_id, outbound_id, part_id, expected_qty) VALUES
    ('10000000-0000-0000-0000-000000000301', 'OUT-001', 'PART-A', 1),
    ('10000000-0000-0000-0000-000000000302', 'OUT-002', 'PART-C', 1);

INSERT INTO outbound_detail
    (out_detail_id, outbound_id, serial_no, time_picked_by) VALUES
    ('10000000-0000-0000-0000-000000000401', 'OUT-001', 'SYN2-A-102', '2026-09-30 17:00:00+07');

INSERT INTO current_stock
    (serial_no, condition, location_id, status, created_at, updated_at) VALUES
    ('SYN2-A-101', 'Good', 'A-01', 'Available', '2026-09-01 08:00:00+07', '2026-09-01 12:00:00+07'),
    ('SYN2-A-102', 'Good', NULL, 'In Transit', '2026-09-01 08:01:00+07', '2026-09-30 17:00:00+07'),
    ('SYN2-A-103', 'Good', 'A-02', 'Available', '2026-09-30 09:00:00+07', '2026-09-30 12:00:00+07'),
    ('SYN2-B-101', 'Damaged', 'Q-01', 'Quarantine', '2026-09-01 08:02:00+07', '2026-09-01 12:02:00+07'),
    ('SYN2-C-101', 'Good', 'REC-01', 'Receiving', '2026-09-30 09:01:00+07', '2026-09-30 09:01:00+07');
