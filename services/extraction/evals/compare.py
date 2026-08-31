"""Value comparison rules for Level 1 extraction eval (AGENTS.md §9)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from rapidfuzz import fuzz

from evals.gold_io import DATE_KEYS, MONEY_KEYS


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _leaf_value(node: Any) -> Any:
    """Unwrap ExtractedValue-shaped dicts to their .value."""
    if isinstance(node, dict) and "value" in node and (
        "confidence" in node or "snippet" in node or "page" in node
    ):
        return node.get("value")
    return node


def _normalize_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"_raw": row}
    out: dict[str, Any] = {}
    for key, val in row.items():
        out[key] = _leaf_value(val)
    return out


def values_match(field_key: str, gold: Any, extracted: Any) -> bool:
    """Return True when extracted matches gold under AGENTS.md §9 Level 1 rules."""
    if gold is None and extracted is None:
        return True
    if gold is None or extracted is None:
        # Both-null already handled; one-sided null is a miss unless both empty lists.
        if gold in ([],) and extracted in ([], None):
            return True
        if extracted in ([],) and gold in ([], None):
            return True
        return False

    leaf = field_key.split(".")[-1] if "." in field_key else field_key

    if leaf in DATE_KEYS or field_key in DATE_KEYS:
        return _as_date(gold) == _as_date(extracted)

    if leaf in MONEY_KEYS or field_key in MONEY_KEYS:
        g = _as_float(gold)
        e = _as_float(extracted)
        if g is None or e is None:
            return False
        if g == 0:
            return e == 0
        return abs(e - g) / abs(g) <= 0.01

    g_num = _as_float(gold)
    e_num = _as_float(extracted)
    if isinstance(gold, (int, float)) and not isinstance(gold, bool) and g_num is not None and e_num is not None:
        # Non-money numerics: exact (ints) or exact float equality after cast.
        if float(g_num).is_integer() and float(e_num).is_integer():
            return int(g_num) == int(e_num)
        return g_num == e_num

    if isinstance(gold, list) or isinstance(extracted, list):
        return lists_match(field_key, gold if isinstance(gold, list) else [], extracted if isinstance(extracted, list) else [])

    if isinstance(gold, dict) or isinstance(extracted, dict):
        return _dicts_match(gold if isinstance(gold, dict) else {}, extracted if isinstance(extracted, dict) else {})

    g_text = str(gold).strip()
    e_text = str(extracted).strip()
    if not g_text and not e_text:
        return True
    return fuzz.ratio(g_text.lower(), e_text.lower()) >= 85


def _dicts_match(gold: dict[str, Any], extracted: dict[str, Any]) -> bool:
    gold_n = _normalize_row(gold)
    ext_n = _normalize_row(extracted)
    keys = set(gold_n) | set(ext_n)
    if not keys:
        return True
    return all(values_match(key, gold_n.get(key), ext_n.get(key)) for key in keys)


def lists_match(field_key: str, gold: list[Any], extracted: list[Any]) -> bool:
    """Order-insensitive greedy matching of list rows."""
    if len(gold) != len(extracted):
        # Allow empty/null equivalence already handled upstream; unequal length = fail.
        if not gold and not extracted:
            return True
        return False
    if not gold:
        return True

    remaining = list(range(len(extracted)))
    for g_row in gold:
        matched_idx: int | None = None
        for idx in remaining:
            if values_match(field_key, g_row, extracted[idx]):
                matched_idx = idx
                break
            # Row dicts: compare normalized leaves
            if isinstance(g_row, dict) and isinstance(extracted[idx], dict):
                if _dicts_match(g_row, extracted[idx]):
                    matched_idx = idx
                    break
        if matched_idx is None:
            return False
        remaining.remove(matched_idx)
    return True
