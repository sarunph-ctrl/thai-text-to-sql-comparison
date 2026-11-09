"""Parses a Thai/English time expression out of the CLEANED query text and
returns a half-open [start, end) date range plus a `group_by` hint (day/week/
month/year) when the phrase implies a breakdown ("แยกรายเดือน").

This module never guesses: if nothing matches, it returns None and the
caller treats the query as "all time".
"""
from __future__ import annotations
import re
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from app.config_loader import load_time_words

_TW = load_time_words()
_MONTH_NAME_TO_NUM = {name: num for num, names in _TW["months"].items() for name in names}
_BE_OFFSET = _TW["buddhist_era_offset"]

_TRAILING_RE = re.compile(
    r"(\d+)\s*(" + "|".join(sorted(_TW["trailing_units"], key=len, reverse=True)) + r")\s*(?:ที่ผ่านมา|ที่แล้ว|past|last)?",
)
# "15 มี.ค. 69" / "15 march 2026" / "15/3/2569"
_MONTH_NAMES_PATTERN = "|".join(sorted(_MONTH_NAME_TO_NUM, key=len, reverse=True))
_ABS_DATE_RE = re.compile(
    rf"(\d{{1,2}})\s*(?:{_MONTH_NAMES_PATTERN})\s*(\d{{2,4}})?"
)
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_YEAR_ONLY_RE = re.compile(r"ปี\s*(?:พ\.?ศ\.?\s*)?(\d{4})\b")


@dataclass
class TimeRange:
    start: date            # inclusive
    end: date              # exclusive
    group_by: str | None = None   # 'day' | 'week' | 'month' | 'year' | None
    matched_text: str | None = None


def _to_ce_year(y: int) -> int:
    """Heuristic: a 4-digit year >= 2400 is Buddhist Era; a 2-digit year is BE
    shorthand (common in Thai casual writing, e.g. '69' = 2569 BE = 2026 CE)."""
    if y >= 2400:
        return y - _BE_OFFSET
    if y < 100:
        return 2500 + y - _BE_OFFSET
    return y


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    days = calendar.monthrange(year, month)[1]
    return start, start + timedelta(days=days)


def _shift_month(d: date, months: int) -> date:
    m0 = d.month - 1 + months
    year = d.year + m0 // 12
    month = m0 % 12 + 1
    return date(year, month, 1)


def _quarter_range(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    end = _shift_month(start, 3)
    return start, end


def parse_time_range(clean_text: str, today: date | None = None) -> TimeRange | None:
    today = today or date.today()

    # Whole named month with an explicit year. Consume the complete expression
    # before the more general year-only rule ("กันยายน ปี 2569").
    for name, num in sorted(_MONTH_NAME_TO_NUM.items(), key=lambda kv: -len(kv[0])):
        pat = re.compile(
            rf"(?<!\d)(?:เดือน\s*)?{re.escape(name)}\s*(?:ปี\s*)?(?:พ\.?ศ\.?\s*)?(\d{{4}})(?!\d)"
        )
        m = pat.search(clean_text)
        if m:
            # A preceding day means this is a daily date, handled below.
            if re.search(r"\d\s*$", clean_text[:m.start()]):
                continue
            year = _to_ce_year(int(m.group(1)))
            start, end = _month_range(year, num)
            return TimeRange(start, end, matched_text=m.group(0))

    # 1. Explicit "N units ago" ("7 วันที่ผ่านมา", "last 30 days").
    m = _TRAILING_RE.search(clean_text)
    if m and (m.group(2) in _TW["trailing_units"]):
        n = int(m.group(1))
        unit = _TW["trailing_units"][m.group(2)]
        end = today + timedelta(days=1)
        if unit == "day":
            start = today - timedelta(days=n - 1)
        elif unit == "week":
            start = today - timedelta(weeks=n)
        elif unit == "month":
            start = _shift_month(today, -n)
        else:  # year
            start = today.replace(year=today.year - n)
        return TimeRange(start, end, matched_text=m.group(0))

    # 2. Fixed relative points ("วันนี้", "เมื่อวาน") - single day.
    for phrase, spec in sorted(_TW["relative_points"].items(), key=lambda kv: -len(kv[0])):
        if phrase in clean_text:
            d = today + timedelta(days=spec["offset"])
            return TimeRange(d, d + timedelta(days=1), matched_text=phrase)

    # 3. Fixed relative periods ("เดือนนี้", "ปีที่แล้ว", "ไตรมาสนี้").
    for phrase, spec in sorted(_TW["relative_periods"].items(), key=lambda kv: -len(kv[0])):
        if phrase in clean_text:
            unit, offset = spec["unit"], spec["offset"]
            if unit == "month":
                start = _shift_month(today, offset)
                end = _shift_month(start, 1)
            elif unit == "week":
                monday = today - timedelta(days=today.weekday())
                start = monday + timedelta(weeks=offset)
                end = start + timedelta(weeks=1)
            elif unit == "year":
                start = date(today.year + offset, 1, 1)
                end = date(today.year + offset + 1, 1, 1)
            else:  # quarter
                q = (today.month - 1) // 3 + 1 + offset
                year = today.year + (q - 1) // 4
                q = (q - 1) % 4 + 1
                start, end = _quarter_range(year, q)
            group_by = {"month": "day", "year": "month", "quarter": "month", "week": "day"}[unit]
            return TimeRange(start, end, group_by=None, matched_text=phrase)

    # 4. Explicit year: "ปี 2569" / "ปี 2026".
    m = _YEAR_ONLY_RE.search(clean_text)
    if m:
        year = _to_ce_year(int(m.group(1)))
        return TimeRange(date(year, 1, 1), date(year + 1, 1, 1), matched_text=m.group(0))

    # 5. Absolute "D Month [Y]" (Thai month name or English, BE or CE).
    for name, num in sorted(_MONTH_NAME_TO_NUM.items(), key=lambda kv: -len(kv[0])):
        pat = re.compile(rf"(\d{{1,2}})\s*{re.escape(name)}\s*(\d{{2,4}})?")
        m = pat.search(clean_text)
        if m:
            day = int(m.group(1))
            year = _to_ce_year(int(m.group(2))) if m.group(2) else today.year
            d = date(year, num, day)
            return TimeRange(d, d + timedelta(days=1), matched_text=m.group(0))

    # 6. Slash/dash dates: D/M/Y.
    m = _SLASH_DATE_RE.search(clean_text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), _to_ce_year(int(m.group(3)))
        d = date(year, month, day)
        return TimeRange(d, d + timedelta(days=1), matched_text=m.group(0))

    return None


def group_by_hint(clean_text: str) -> str | None:
    """Detects an explicit breakdown request: 'แยกรายเดือน', 'by month', etc."""
    checks = [
        (["แยกรายวัน", "by day", "รายวัน"], "day"),
        (["แยกรายสัปดาห์", "by week", "รายสัปดาห์"], "week"),
        (["แยกรายเดือน", "by month", "รายเดือน"], "month"),
        (["แยกรายปี", "by year", "รายปี"], "year"),
    ]
    for phrases, unit in checks:
        if any(p in clean_text for p in phrases):
            return unit
    return None
