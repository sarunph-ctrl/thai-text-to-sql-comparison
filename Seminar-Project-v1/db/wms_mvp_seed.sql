-- Deterministic synthetic WMS data. No values come from the original system.
-- Fixed IDs and timestamps make reference SQL results reproducible.

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
    ('INB-001', 'SYN-INV-001', DATE '2026-09-01', 'Completed', 'SYN-CONT-01'),
    ('INB-002', 'SYN-INV-002', DATE '2026-09-15', 'Draft Plan', 'SYN-CONT-02'),
    ('INB-003', 'SYN-INV-003', DATE '2026-10-01', 'Cancelled', NULL);

INSERT INTO inbound_plan (plan_id, inbound_id, part_id, expected_qty) VALUES
    ('00000000-0000-0000-0000-000000000101', 'INB-001', 'PART-A', 3),
    ('00000000-0000-0000-0000-000000000102', 'INB-001', 'PART-B', 2),
    ('00000000-0000-0000-0000-000000000103', 'INB-002', 'PART-A', 2),
    ('00000000-0000-0000-0000-000000000104', 'INB-002', 'PART-C', 1),
    ('00000000-0000-0000-0000-000000000105', 'INB-003', 'PART-D', 2);

INSERT INTO part_obj (serial_no, part_id, created_at, updated_at) VALUES
    ('SYN-A-001', 'PART-A', '2026-09-01 08:00:00+07', '2026-09-01 08:00:00+07'),
    ('SYN-A-002', 'PART-A', '2026-09-01 08:01:00+07', '2026-09-01 08:01:00+07'),
    ('SYN-A-003', 'PART-A', '2026-09-01 08:02:00+07', '2026-09-20 10:00:00+07'),
    ('SYN-A-004', 'PART-A', '2026-09-16 09:00:00+07', '2026-09-16 09:00:00+07'),
    ('SYN-B-001', 'PART-B', '2026-09-01 08:03:00+07', '2026-09-20 10:01:00+07'),
    ('SYN-B-002', 'PART-B', '2026-09-01 08:04:00+07', '2026-09-01 08:04:00+07');

INSERT INTO inbound_detail
    (in_detail_id, inbound_id, serial_no, condition, damage_image_url, time_received_by) VALUES
    ('00000000-0000-0000-0000-000000000201', 'INB-001', 'SYN-A-001', 'Good', NULL, '2026-09-01 08:00:00+07'),
    ('00000000-0000-0000-0000-000000000202', 'INB-001', 'SYN-A-002', 'Good', NULL, '2026-09-01 08:01:00+07'),
    ('00000000-0000-0000-0000-000000000203', 'INB-001', 'SYN-A-003', 'Good', NULL, '2026-09-01 08:02:00+07'),
    ('00000000-0000-0000-0000-000000000204', 'INB-001', 'SYN-B-001', 'Good', NULL, '2026-09-01 08:03:00+07'),
    ('00000000-0000-0000-0000-000000000205', 'INB-001', 'SYN-B-002', 'Damaged', 'synthetic://damage/B-002', '2026-09-01 08:04:00+07'),
    ('00000000-0000-0000-0000-000000000206', 'INB-002', 'SYN-A-004', 'Good', NULL, '2026-09-16 09:00:00+07');

INSERT INTO outbound_order (outbound_id, order_date, outstatus) VALUES
    ('OUT-001', DATE '2026-09-20', 'Picked'),
    ('OUT-002', DATE '2026-09-25', 'Pending');

INSERT INTO outbound_plan (plan_id, outbound_id, part_id, expected_qty) VALUES
    ('00000000-0000-0000-0000-000000000301', 'OUT-001', 'PART-A', 1),
    ('00000000-0000-0000-0000-000000000302', 'OUT-001', 'PART-B', 1),
    ('00000000-0000-0000-0000-000000000303', 'OUT-002', 'PART-A', 1),
    ('00000000-0000-0000-0000-000000000304', 'OUT-002', 'PART-C', 1);

INSERT INTO outbound_detail
    (out_detail_id, outbound_id, serial_no, time_picked_by) VALUES
    ('00000000-0000-0000-0000-000000000401', 'OUT-001', 'SYN-A-003', '2026-09-20 10:00:00+07'),
    ('00000000-0000-0000-0000-000000000402', 'OUT-001', 'SYN-B-001', '2026-09-20 10:01:00+07');

INSERT INTO current_stock
    (serial_no, condition, location_id, status, created_at, updated_at) VALUES
    ('SYN-A-001', 'Good', 'A-01', 'Available', '2026-09-01 08:00:00+07', '2026-09-01 12:00:00+07'),
    ('SYN-A-002', 'Good', 'A-01', 'Available', '2026-09-01 08:01:00+07', '2026-09-01 12:01:00+07'),
    ('SYN-A-003', 'Good', NULL, 'In Transit', '2026-09-01 08:02:00+07', '2026-09-20 10:00:00+07'),
    ('SYN-A-004', 'Good', 'REC-01', 'Receiving', '2026-09-16 09:00:00+07', '2026-09-16 09:00:00+07'),
    ('SYN-B-001', 'Good', NULL, 'In Transit', '2026-09-01 08:03:00+07', '2026-09-20 10:01:00+07'),
    ('SYN-B-002', 'Damaged', 'Q-01', 'Quarantine', '2026-09-01 08:04:00+07', '2026-09-01 12:04:00+07');
