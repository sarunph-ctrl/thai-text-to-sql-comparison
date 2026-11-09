"""Rule-based intent + slot extraction.

Design: everything is substring/regex matching over `clean_text`, driven by
the lexicon - no ML, no LLM. This is deliberately simple so that every match
is traceable to a rule you can point at in config/lexicon.yaml.

Matching order matters and is documented inline:
  1. metric (which number does the user want?)                 - required
  2. dimension (broken down / top-N by what?)                   - optional
  3. top_n (how many rows / "top 5")                             - optional
  4. status / payment_method filters                             - optional
  5. numeric comparator filters ("สต็อกน้อยกว่า 10")              - optional
  6. entity name candidates (for the pipeline to resolve)         - optional
  7. time range (delegated to time_parser)                       - optional

If no metric phrase matches at all, `match_intent` returns None and the
pipeline reports "ไม่เข้าใจ" (unmatched) rather than guessing.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

from app.config_loader import load_lexicon
from app.nlp.time_parser import group_by_hint, parse_time_range

_LEX = load_lexicon()

_TOP_N_RE = re.compile(r"(?:top|อันดับแรก|อันดับที่|สูงสุด)\D{0,6}?(\d+)|(\d+)\D{0,10}?(?:อันดับแรก|อันดับ)")
_BOTTOM_HINT = ["น้อยที่สุด", "ต่ำสุด", "ต่ำที่สุด", "lowest", "least", "worst"]
_TOP_HINT = ["มากที่สุด", "สูงสุด", "ดีที่สุด", "highest", "most", "best", "top"]

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class RawSlots:
    metric: str | None = None
    dimension: str | None = None
    top_n: int | None = None
    order: str = "desc"
    status: str | None = None
    payment_method: str | None = None
    stock_filter: tuple[str, float] | None = None   # (op, value)
    entity_candidates: dict[str, str] = None         # dimension -> raw name text
    time_range: tuple | None = None
    time_group: str | None = None
    matched_rules: list[str] = None                  # for the explainability panel
    matched_phrases: list[str] = None                 # exact substrings consumed, for candidate-name extraction

    def __post_init__(self):
        if self.entity_candidates is None:
            self.entity_candidates = {}
        if self.matched_rules is None:
            self.matched_rules = []
        if self.matched_phrases is None:
            self.matched_phrases = []


def _find_phrase(clean_text: str, synonym_groups: dict[str, list[str]]) -> tuple[str, str] | None:
    """Returns (key, matched_phrase) for the LONGEST matching synonym across all
    groups, so "จำนวนออเดอร์" wins over a shorter unrelated substring."""
    best: tuple[str, str] | None = None
    for key, synonyms in synonym_groups.items():
        for phrase in synonyms:
            if phrase in clean_text:
                if best is None or len(phrase) > len(best[1]):
                    best = (key, phrase)
    return best


def match_intent(clean_text: str) -> RawSlots | None:
    slots = RawSlots()

    # 1. Metric (required to consider this a query at all).
    metric_groups = {k: v["synonyms"] for k, v in _LEX["metrics"].items()}
    m = _find_phrase(clean_text, metric_groups)
    if m is None:
        return None
    slots.metric, phrase = m
    slots.matched_rules.append(f"metric={slots.metric} (matched {phrase!r})")
    slots.matched_phrases.append(phrase)

    # 2. Dimension: which entity to group/rank by, EXCLUDING the entity that
    #    might actually be a named filter (handled in step 6). We detect a
    #    dimension when the query implies "by X" / "top X" / plural framing.
    entity_groups = {k: v["synonyms"] for k, v in _LEX["entities"].items() if k != "order"}
    dim_hit = _find_phrase(clean_text, entity_groups)
    if dim_hit:
        key, phrase = dim_hit
        if key in ("product", "category", "customer", "supplier", "branch", "employee"):
            slots.dimension = key
            slots.matched_rules.append(f"dimension={key} (matched {phrase!r})")
            slots.matched_phrases.append(phrase)

    # 3. Top-N / bottom-N.
    tn = _TOP_N_RE.search(clean_text)
    if tn:
        n = tn.group(1) or tn.group(2)
        slots.top_n = int(n)
        slots.matched_rules.append(f"top_n={slots.top_n}")
        slots.matched_phrases.append(tn.group(0))
    # Superlative hint phrases ("ที่สุด", "highest", ...) are always stripped
    # from the text once detected, even if top_n was already set by an
    # explicit number - otherwise a leftover fragment like "สุด" can survive
    # into name-candidate extraction and accidentally match an unrelated row
    # (e.g. a customer literally named "สุดา").
    bottom_hit = next((h for h in _BOTTOM_HINT if h in clean_text), None)
    top_hit = next((h for h in _TOP_HINT if h in clean_text), None)
    if bottom_hit:
        slots.order = "asc"
        slots.matched_rules.append("order=asc (bottom/lowest phrasing)")
        slots.matched_phrases.append(bottom_hit)
    elif top_hit:
        if slots.top_n is None:
            slots.top_n = 1
            slots.order = "desc"
            slots.matched_rules.append("top_n=1 (superlative phrasing, e.g. ขายดีที่สุด)")
        slots.matched_phrases.append(top_hit)

    # 4. Status / payment method filters.
    status_hit = _find_phrase(clean_text, _LEX["status_values"])
    if status_hit:
        slots.status = status_hit[0]
        slots.matched_rules.append(f"status={status_hit[0]} (matched {status_hit[1]!r})")
        slots.matched_phrases.append(status_hit[1])
    pay_hit = _find_phrase(clean_text, _LEX["payment_methods"])
    if pay_hit:
        slots.payment_method = pay_hit[0]
        slots.matched_rules.append(f"payment_method={pay_hit[0]} (matched {pay_hit[1]!r})")
        slots.matched_phrases.append(pay_hit[1])

    # 5. Numeric comparator filters, only meaningful for the 'stock' metric
    #    ("สต็อกน้อยกว่า 10", "stock under 10").
    if slots.metric == "stock":
        comp_hit = _find_phrase(clean_text, _LEX["comparators"])
        num = _NUMBER_RE.search(clean_text)
        if comp_hit and num:
            slots.stock_filter = (comp_hit[0], float(num.group(0)))
            slots.matched_rules.append(f"stock {comp_hit[0]} {num.group(0)}")
            slots.matched_phrases.extend([comp_hit[1], num.group(0)])

    # 6. Time range (delegated).
    tr = parse_time_range(clean_text)
    if tr:
        slots.time_range = (tr.start, tr.end)
        slots.matched_rules.append(f"time_range={tr.start}..{tr.end} (matched {tr.matched_text!r})")
        if tr.matched_text:
            slots.matched_phrases.append(tr.matched_text)
    gb = group_by_hint(clean_text)
    if gb:
        slots.time_group = gb
        slots.matched_rules.append(f"time_group={gb}")

    return slots
