"""Serialize / deserialize LeaseExtraction for persistence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agent.schema import (
    NULL_LEAF,
    ExtractedValue,
    Financial,
    LeaseExtraction,
    Opex,
    OptionsObligations,
    PartiesPremises,
    Term,
)
from app.field_groups import FIELD_GROUPS

LIST_FIELD_KEYS = frozenset({"base_rent_schedule", "renewal_options"})
NULLABLE_OBJECT_KEYS = frozenset({"termination_option"})


def _extracted_to_dict(value: ExtractedValue[Any]) -> dict[str, Any]:
    return value.model_dump(mode="json")


def _flatten_model(model: BaseModel, prefix: str = "") -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for field_name in model.model_fields:
        field_path = f"{prefix}.{field_name}" if prefix else field_name
        attr = getattr(model, field_name)
        if isinstance(attr, ExtractedValue):
            rows[field_path] = _extracted_to_dict(attr)
        elif isinstance(attr, BaseModel):
            if field_name == "termination_option":
                rows[field_path] = attr.model_dump(mode="json")
            else:
                rows.update(_flatten_model(attr, field_path))
        elif isinstance(attr, list):
            rows[field_path] = [item.model_dump(mode="json") for item in attr]
        elif attr is None and field_name == "termination_option":
            rows[field_path] = None
    return rows


def flatten_lease_extraction(extraction: LeaseExtraction) -> dict[str, Any]:
    """Flatten group models to field_key → JSON-ready values.

    Always emits one entry per schema field in FIELD_GROUPS (null leaf / empty list
    when the model omits the value).
    """
    rows: dict[str, Any] = {}
    rows.update(_flatten_model(extraction.parties_premises))
    rows.update(_flatten_model(extraction.term))
    rows.update(_flatten_model(extraction.financial))
    rows.update(_flatten_model(extraction.options_obligations))
    rows.update(_flatten_model(extraction.opex))

    for keys in FIELD_GROUPS.values():
        for key in keys:
            if key in rows:
                continue
            if key in LIST_FIELD_KEYS:
                rows[key] = []
            elif key in NULLABLE_OBJECT_KEYS:
                rows[key] = None
            else:
                rows[key] = dict(NULL_LEAF)
    return rows


def count_group_leaves(group_model: BaseModel) -> tuple[int, int]:
    """Return (total_leaf_count, non_null_value_count) for a group model."""
    total = 0
    non_null = 0
    for field_name in group_model.model_fields:
        attr = getattr(group_model, field_name)
        if isinstance(attr, ExtractedValue):
            total += 1
            if attr.value is not None:
                non_null += 1
        elif isinstance(attr, BaseModel):
            nested_total, nested_non_null = count_group_leaves(attr)
            total += nested_total
            non_null += nested_non_null
        elif isinstance(attr, list):
            total += 1
            if len(attr) > 0:
                non_null += 1
                for item in attr:
                    if isinstance(item, BaseModel):
                        item_total, item_non_null = count_group_leaves(item)
                        total += item_total
                        non_null += item_non_null
        elif field_name == "termination_option" and attr is None:
            total += 1
    return total, non_null


def lease_extraction_from_groups(
    parties_premises: PartiesPremises,
    term: Term,
    financial: Financial,
    options_obligations: OptionsObligations,
    opex: Opex,
) -> LeaseExtraction:
    return LeaseExtraction(
        parties_premises=parties_premises,
        term=term,
        financial=financial,
        options_obligations=options_obligations,
        opex=opex,
    )


def lease_extraction_from_field_rows(rows: dict[str, Any]) -> LeaseExtraction:
    """Rebuild LeaseExtraction from persisted field_key rows."""
    return LeaseExtraction(
        parties_premises=PartiesPremises.model_validate(
            {
                "landlord": rows.get("landlord", {"value": None, "confidence": 0}),
                "tenant": rows.get("tenant", {"value": None, "confidence": 0}),
                "premises_address": rows.get("premises_address", {"value": None, "confidence": 0}),
                "rentable_sqft": rows.get("rentable_sqft", {"value": None, "confidence": 0}),
            }
        ),
        term=Term.model_validate(
            {
                "commencement_date": rows.get("commencement_date", {"value": None, "confidence": 0}),
                "expiration_date": rows.get("expiration_date", {"value": None, "confidence": 0}),
                "initial_term_months": rows.get("initial_term_months", {"value": None, "confidence": 0}),
            }
        ),
        financial=Financial.model_validate(
            {
                "base_rent_schedule": rows.get("base_rent_schedule", []),
                "escalation_type": rows.get("escalation_type", {"value": None, "confidence": 0}),
                "escalation_value": rows.get("escalation_value", {"value": None, "confidence": 0}),
                "security_deposit": rows.get("security_deposit", {"value": None, "confidence": 0}),
            }
        ),
        options_obligations=OptionsObligations.model_validate(
            {
                "renewal_options": rows.get("renewal_options", []),
                "termination_option": rows.get("termination_option"),
                "holdover_rate_pct": rows.get("holdover_rate_pct", {"value": None, "confidence": 0}),
            }
        ),
        opex=Opex.model_validate(
            {
                "cam_structure": rows.get("cam_structure", {"value": None, "confidence": 0}),
                "base_year": rows.get("base_year", {"value": None, "confidence": 0}),
                "cam_cap_pct": rows.get("cam_cap_pct", {"value": None, "confidence": 0}),
                "cam_cap_type": rows.get("cam_cap_type", {"value": None, "confidence": 0}),
            }
        ),
    )
