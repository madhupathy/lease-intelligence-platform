"""Gold-label I/O and key normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.field_groups import FIELD_GROUPS, FIELD_TO_GROUP

EVALS_DIR = Path(__file__).resolve().parent
GOLD_DIR = EVALS_DIR / "gold"

# Money / percentage numeric fields (compare within ±1%).
MONEY_KEYS = frozenset(
    {
        "security_deposit",
        "escalation_value",
        "holdover_rate_pct",
        "cam_cap_pct",
        "annual_rent",
        "monthly_rent",
        "fee",
    }
)

DATE_KEYS = frozenset(
    {
        "commencement_date",
        "expiration_date",
        "period_start",
        "period_end",
        "date",
    }
)

LIST_KEYS = frozenset({"base_rent_schedule", "renewal_options"})


def normalize_field_key(key: str) -> str:
    """Accept DB keys or group-prefixed aliases (financial.security_deposit → security_deposit)."""
    if key in FIELD_TO_GROUP:
        return key
    if "." in key:
        group, _, leaf = key.partition(".")
        if group in FIELD_GROUPS and leaf in FIELD_TO_GROUP:
            return leaf
    return key


def all_schema_keys() -> list[str]:
    return [key for keys in FIELD_GROUPS.values() for key in keys]


def load_gold(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_fields = payload.get("fields") or {}
    fields: dict[str, dict[str, Any]] = {}
    for key, entry in raw_fields.items():
        if key.startswith("_"):
            continue
        norm = normalize_field_key(key)
        if not isinstance(entry, dict):
            entry = {"value": entry, "page": None, "_verified": False}
        fields[norm] = {
            "value": entry.get("value"),
            "page": entry.get("page"),
            "_verified": bool(entry.get("_verified", False)),
        }
    return {
        "pdf_stem": payload.get("pdf_stem") or path.stem,
        "lease_id": payload.get("lease_id"),
        "lease_name": payload.get("lease_name"),
        "fields": fields,
        "path": path,
    }


def list_gold_files() -> list[Path]:
    return sorted(p for p in GOLD_DIR.glob("*.json") if p.name != "TEMPLATE.json")


def write_gold(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
