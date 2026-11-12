"""Conservative phrase/regex parser for the five WMS MVP query families."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import calendar
import re

import yaml

from app.config_loader import CONFIG_DIR


CONFIG = yaml.safe_load((CONFIG_DIR / "wms_rules.yaml").read_text(encoding="utf-8"))
KEYWORDS = CONFIG["keywords"]

MONTHS = {
    "มกราคม": 1, "ม.ค.": 1, "jan": 1, "january": 1,
    "กุมภาพันธ์": 2, "ก.พ.": 2, "feb": 2, "february": 2,
    "มีนาคม": 3, "มี.ค.": 3, "mar": 3, "march": 3,
    "เมษายน": 4, "เม.ย.": 4, "apr": 4, "april": 4,
    "พฤษภาคม": 5, "พ.ค.": 5, "may": 5,
    "มิถุนายน": 6, "มิ.ย.": 6, "jun": 6, "june": 6,
    "กรกฎาคม": 7, "ก.ค.": 7, "jul": 7, "july": 7,
    "สิงหาคม": 8, "ส.ค.": 8, "aug": 8, "august": 8,
    "กันยายน": 9, "ก.ย.": 9, "sep": 9, "sept": 9, "september": 9,
    "ตุลาคม": 10, "ต.ค.": 10, "oct": 10, "october": 10,
    "พฤศจิกายน": 11, "พ.ย.": 11, "nov": 11, "november": 11,
    "ธันวาคม": 12, "ธ.ค.": 12, "dec": 12, "december": 12,
}


class UnsupportedWMSQuestion(ValueError):
    pass


@dataclass
class WMSIntent:
    family: str
    filters: dict[str, object] = field(default_factory=dict)
    matched_rules: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)


def _contains(text: str, phrases: list[str]) -> bool:
    folded = text.casefold()
    return any(phrase.casefold() in folded for phrase in phrases)


def _unsupported_reason(text: str) -> str | None:
    folded = f" {text.casefold()} "
    for reason, phrases in CONFIG["unsupported"].items():
        # Phrases such as "สิ้นเดือน" are valid boundaries for order-flow
        # questions. They indicate unsupported history only in stock context.
        if reason == "historical_stock" and not (
            _contains(text, KEYWORDS["stock"])
            or _contains(text, KEYWORDS["part"])
            or "คงเหลือ" in text
        ):
            continue
        if any(phrase.casefold() in folded for phrase in phrases):
            return reason
    return None


def _month_range(text: str) -> tuple[date, date] | None:
    folded = text.casefold()
    years = [int(value) for value in re.findall(r"(?<!\d)(\d{4})(?!\d)", folded)]
    if len(set(years)) != 1:
        return None
    year = years[0]
    if year >= 2400:
        year -= 543
    if not 1900 <= year <= 2200:
        return None

    found_months = {number for name, number in MONTHS.items() if name in folded}
    for value in re.findall(r"เดือน\s*(1[0-2]|0?[1-9])(?!\d)", folded):
        found_months.add(int(value))
    if len(found_months) != 1:
        return None
    month = found_months.pop()
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return start, end


def parse_wms_question(clean_text: str) -> WMSIntent:
    text = clean_text.strip()
    if not text:
        raise UnsupportedWMSQuestion("empty_question")
    reason = _unsupported_reason(text)
    if reason:
        raise UnsupportedWMSQuestion(reason)

    # Explicit identifiers are intentionally deferred until the reviewed rules
    # define which filters are supported. Reject rather than silently ignore.
    if re.search(r"\b(?:part|inb|out)-[a-z0-9-]+\b", text, re.IGNORECASE):
        raise UnsupportedWMSQuestion("explicit_identifier_filter_not_supported_in_draft")

    has_outbound = _contains(text, KEYWORDS["outbound"])
    has_status = _contains(text, KEYWORDS["status"])
    month_range = _month_range(text)
    if has_outbound and has_status and month_range:
        return WMSIntent(
            family="operational_order_status",
            filters={"start_date": month_range[0], "end_date": month_range[1]},
            matched_rules=["family=operational_order_status", "time=explicit_month"],
            business_rules=["OUT-04", "OUT-05", "TIME-01"],
        )

    if _contains(text, KEYWORDS["quarantine"]) and _contains(text, KEYWORDS["serial"]):
        return WMSIntent(
            family="current_stock_detail",
            filters={"status": "Quarantine"},
            matched_rules=["family=current_stock_detail", "status=Quarantine"],
            business_rules=["STOCK-02", "STOCK-04", "STOCK-05", "RESULT-02"],
        )

    has_inbound = _contains(text, KEYWORDS["inbound"])
    has_plan = _contains(text, KEYWORDS["plan"])
    if has_inbound and has_plan and _contains(text, KEYWORDS["actual_inbound"]):
        return WMSIntent(
            family="inbound_progress",
            matched_rules=["family=inbound_progress", "compare=plan_vs_received"],
            business_rules=["IN-01", "IN-02", "IN-03", "IN-04", "RESULT-01"],
        )

    if has_outbound and has_plan and _contains(text, KEYWORDS["actual_outbound"]):
        return WMSIntent(
            family="outbound_progress",
            matched_rules=["family=outbound_progress", "compare=plan_vs_picked"],
            business_rules=["OUT-01", "OUT-02", "OUT-03", "RESULT-01"],
        )

    if (_contains(text, KEYWORDS["stock"])
            and _contains(text, KEYWORDS["part"])
            and has_status):
        if month_range:
            raise UnsupportedWMSQuestion("historical_stock_not_supported")
        return WMSIntent(
            family="current_stock_summary",
            matched_rules=["family=current_stock_summary", "group_by=part,status"],
            business_rules=["STOCK-01", "STOCK-02", "STOCK-04", "STOCK-06"],
        )

    raise UnsupportedWMSQuestion("outside_five_query_families")
