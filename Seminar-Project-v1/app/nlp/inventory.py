"""Rule-based stock profile, intentionally limited to two query shapes."""
from dataclasses import dataclass
import re

import yaml

from app.config_loader import CONFIG_DIR, load_time_words
from app.nlp.rule_utils import unconsumed_text
from app.nlp.time_parser import parse_time_range
from app.sql.builder import BuiltQuery, MAX_LIMIT
from app.sql.inventory import build_stock_balance, build_outbound_quantity

CONFIG = yaml.safe_load((CONFIG_DIR / "inventory.yaml").read_text(encoding="utf-8"))
MONTH_NAMES = [name for names in load_time_words()["months"].values() for name in names]


@dataclass
class InventoryPlan:
    query: BuiltQuery
    interpretation: dict
    rules: list[str]
    definition: str


def parse_inventory_question(text: str) -> InventoryPlan | None:
    balances = [p for p in CONFIG["balance_phrases"] if p in text]
    issues = [p for p in CONFIG["issue_phrases"] if p in text]
    if not balances and not issues:
        return None
    if balances and issues:
        raise ValueError("ถามคงเหลือหรือจ่ายออกครั้งละหนึ่งเรื่อง")
    phrases = balances + issues
    if balances:
        residual = unconsumed_text(text, phrases, CONFIG["fillers"])
        if residual:
            raise ValueError(f"คงเหลือรองรับยอดจากทุกรายการแยกตามคลัง ยังไม่รองรับส่วนนี้: {residual!r}")
        return InventoryPlan(
            build_stock_balance(),
            {"metric": "stock_balance", "dimensions": ["warehouse", "product"],
             "time_basis": "all_recorded_movements", "quantity_unit": "หน่วยตามสินค้า",
             "includes_zero_balances": True, "row_limit": MAX_LIMIT,
             "tables": ["warehouses", "products", "stock_movements"]},
            [f"metric=stock_balance (matched {max(balances, key=len)!r})",
             "warehouse × product with LEFT JOIN: include zero movement pairs",
             "opening + receipt - issue; no orders.status filter"],
            CONFIG["balance_definition"],
        )
    period = parse_time_range(text)
    if (not period or not re.search(r"\d{4}", period.matched_text or "")
            or not any(n in (period.matched_text or "") for n in MONTH_NAMES)
            or period.start.day != 1 or (period.end - period.start).days < 28):
        raise ValueError("ยอดจ่ายออกต้องระบุเดือนและปี เช่น 'เดือนกันยายน 2569 มีสินค้าจ่ายออกแต่ละชนิดกี่หน่วย'")
    phrases.append(period.matched_text)
    # Monthly outbound is grouped by product across ALL warehouses. Never
    # consume a warehouse-grouping phrase and silently return another grain.
    issue_fillers = [phrase for phrase in CONFIG["fillers"] if "คลัง" not in phrase]
    residual = unconsumed_text(text, phrases, issue_fillers)
    if residual:
        raise ValueError(f"ยอดจ่ายออกรองรับรวมทุกคลังแยกสินค้า ยังไม่รองรับส่วนนี้: {residual!r}")
    return InventoryPlan(
        build_outbound_quantity(period.start, period.end),
        {"metric": "outbound_quantity", "dimension": "product", "warehouse_scope": "all",
         "start_inclusive": period.start.isoformat(), "end_exclusive": period.end.isoformat(),
         "date_column": "stock_movements.movement_date", "movement_type": "issue",
         "quantity_unit": "หน่วยตามสินค้า", "row_limit": MAX_LIMIT,
         "tables": ["products", "stock_movements"]},
        [f"metric=outbound_quantity (matched {max(issues, key=len)!r})",
         f"movement_date={period.start}..{period.end}",
         "SUM(issue.qty); count actual dispatch, independently of payment"],
        CONFIG["issue_definition"],
    )
