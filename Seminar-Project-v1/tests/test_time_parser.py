from datetime import date

from app.nlp.time_parser import parse_time_range, group_by_hint

TODAY = date(2026, 9, 22)


def test_this_month():
    r = parse_time_range("เดือนนี้", today=TODAY)
    assert (r.start, r.end) == (date(2026, 9, 1), date(2026, 10, 1))


def test_last_month():
    r = parse_time_range("เดือนที่แล้ว", today=TODAY)
    assert (r.start, r.end) == (date(2026, 8, 1), date(2026, 9, 1))


def test_last_month_crosses_year_boundary():
    r = parse_time_range("เดือนที่แล้ว", today=date(2026, 1, 15))
    assert (r.start, r.end) == (date(2025, 12, 1), date(2026, 1, 1))


def test_trailing_days():
    r = parse_time_range("7 วันที่ผ่านมา", today=TODAY)
    assert (r.start, r.end) == (date(2026, 9, 16), date(2026, 9, 23))


def test_this_year():
    r = parse_time_range("ปีนี้", today=TODAY)
    assert (r.start, r.end) == (date(2026, 1, 1), date(2027, 1, 1))


def test_last_quarter():
    r = parse_time_range("ไตรมาสที่แล้ว", today=TODAY)
    assert (r.start, r.end) == (date(2026, 4, 1), date(2026, 7, 1))


def test_buddhist_era_two_digit_year():
    r = parse_time_range("15 มี.ค. 69", today=TODAY)
    assert (r.start, r.end) == (date(2026, 3, 15), date(2026, 3, 16))


def test_buddhist_era_four_digit_year():
    r = parse_time_range("ปี 2568", today=TODAY)
    assert (r.start, r.end) == (date(2025, 1, 1), date(2026, 1, 1))


def test_ce_four_digit_year_explicit():
    r = parse_time_range("ปี 2026", today=TODAY)
    assert (r.start, r.end) == (date(2026, 1, 1), date(2027, 1, 1))


def test_slash_date():
    r = parse_time_range("15/3/2026", today=TODAY)
    assert (r.start, r.end) == (date(2026, 3, 15), date(2026, 3, 16))


def test_no_time_phrase_returns_none():
    assert parse_time_range("สินค้าขายดีที่สุด", today=TODAY) is None


def test_group_by_month_hint():
    assert group_by_hint("ยอดขายปีนี้ แยกรายเดือน") == "month"


def test_group_by_hint_absent():
    assert group_by_hint("ยอดขายเดือนนี้") is None


def test_named_month_with_buddhist_year():
    r = parse_time_range("ยอดขายเดือนกันยายน 2569", today=TODAY)
    assert (r.start, r.end) == (date(2026, 9, 1), date(2026, 10, 1))


def test_named_month_before_explicit_year_rule():
    r = parse_time_range("ยอดขายเดือนกันยายน ปี 2569", today=TODAY)
    assert (r.start, r.end) == (date(2026, 9, 1), date(2026, 10, 1))


def test_named_december_rolls_into_next_year():
    r = parse_time_range("ยอดขายธันวาคม 2569", today=TODAY)
    assert (r.start, r.end) == (date(2026, 12, 1), date(2027, 1, 1))


def test_explicit_daily_date_is_not_promoted_to_whole_month():
    r = parse_time_range("1 กันยายน 2569", today=TODAY)
    assert (r.start, r.end) == (date(2026, 9, 1), date(2026, 9, 2))
