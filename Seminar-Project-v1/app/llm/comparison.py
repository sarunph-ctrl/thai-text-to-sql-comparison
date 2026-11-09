"""Compare actual result sets, preserving duplicates and numeric types."""
from collections import Counter
from datetime import date, datetime
from decimal import Decimal


def _cell(value):
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float, Decimal)):
        return ("number", Decimal(str(value)))
    if isinstance(value, (date, datetime)):
        return ("date", value.isoformat())
    return ("text", str(value))


def resultsets_equal(actual: list, expected: list, *, actual_columns: int, expected_columns: int, ordered: bool) -> bool:
    if actual_columns != expected_columns:
        return False
    a = [tuple(_cell(v) for v in row) for row in actual]
    b = [tuple(_cell(v) for v in row) for row in expected]
    return a == b if ordered else Counter(a) == Counter(b)
