"""Pydantic extraction contract — field groups from AGENTS.md §6.

Every leaf field is an ExtractedValue[T] carrying value, confidence, page, and snippet.
Missing / null fields coerce to value=null and confidence=0 (never hard-required).
"""

from __future__ import annotations

from datetime import date as DateType
from typing import Any, Generic, Literal, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")

NULL_LEAF: dict[str, Any] = {
    "value": None,
    "confidence": 0.0,
    "page": None,
    "snippet": None,
}


class ExtractedValue(BaseModel, Generic[T]):
    """Single extracted field with provenance (AGENTS.md §6)."""

    # strict=False so LLM JSON date/number strings coerce into typed values.
    model_config = ConfigDict(extra="forbid", strict=False)

    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page: int | None = None
    snippet: str | None = None


def null_extracted() -> ExtractedValue[Any]:
    """Empty leaf used when the model omits a field."""
    return ExtractedValue(value=None, confidence=0.0, page=None, snippet=None)


def _is_extracted_value_annotation(annotation: Any) -> bool:
    """True for ExtractedValue[...] or ExtractedValue[...] | None."""
    if annotation is None:
        return False
    origin = get_origin(annotation)
    if origin is ExtractedValue:
        return True
    if isinstance(annotation, type) and issubclass(annotation, ExtractedValue):
        return True
    # Union / Optional — ExtractedValue[T] becomes a concrete subclass under Pydantic.
    for arg in get_args(annotation):
        if arg is type(None):
            continue
        if get_origin(arg) is ExtractedValue:
            return True
        if isinstance(arg, type) and issubclass(arg, ExtractedValue):
            return True
    return False


def _is_list_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is list:
        return True
    if isinstance(annotation, type) and annotation is list:
        return True
    for arg in get_args(annotation):
        if get_origin(arg) is list:
            return True
    return False


class _CoerceNullLeavesMixin(BaseModel):
    """Missing / null ExtractedValue fields → null leaves; null lists → []."""

    model_config = ConfigDict(extra="forbid", strict=False)

    @model_validator(mode="before")
    @classmethod
    def coerce_missing_and_null_leaves(cls, data: Any) -> Any:
        if data is None:
            data = {}
        elif isinstance(data, BaseModel):
            data = data.model_dump(mode="python")
        if not isinstance(data, dict):
            return data

        out = dict(data)
        for name, field_info in cls.model_fields.items():
            annotation = field_info.annotation
            if _is_extracted_value_annotation(annotation):
                if name not in out or out[name] is None:
                    out[name] = dict(NULL_LEAF)
            elif _is_list_annotation(annotation):
                if name not in out or out[name] is None:
                    out[name] = []
        return out


class PartiesPremises(_CoerceNullLeavesMixin):
    """Group A — parties_premises."""

    landlord: ExtractedValue[str] | None = None
    tenant: ExtractedValue[str] | None = None
    premises_address: ExtractedValue[str] | None = None
    rentable_sqft: ExtractedValue[int] | None = None


class Term(_CoerceNullLeavesMixin):
    """Group B — term."""

    commencement_date: ExtractedValue[DateType] | None = None
    expiration_date: ExtractedValue[DateType] | None = None
    initial_term_months: ExtractedValue[int] | None = None


class BaseRentPeriod(_CoerceNullLeavesMixin):
    """One row in base_rent_schedule."""

    period_start: ExtractedValue[DateType] | None = None
    period_end: ExtractedValue[DateType] | None = None
    annual_rent: ExtractedValue[float] | None = None
    monthly_rent: ExtractedValue[float] | None = None


EscalationType = Literal["fixed_pct", "cpi", "stepped", "none"]
CamStructure = Literal["net", "gross", "base_year", "stop"]


class Financial(_CoerceNullLeavesMixin):
    """Group C — financial."""

    base_rent_schedule: list[BaseRentPeriod] | None = None
    escalation_type: ExtractedValue[EscalationType] | None = None
    escalation_value: ExtractedValue[float] | None = None
    security_deposit: ExtractedValue[float] | None = None


class RenewalOption(_CoerceNullLeavesMixin):
    """One renewal option entry."""

    term_months: ExtractedValue[int] | None = None
    notice_min_days: ExtractedValue[int] | None = None
    notice_max_days: ExtractedValue[int] | None = None
    rent_basis: ExtractedValue[str] | None = None


class TerminationOption(_CoerceNullLeavesMixin):
    """Termination option sub-structure. Sub-fields may be partially present (D8).

    Field is named `date`; annotation uses DateType so it does not shadow datetime.date.
    """

    date: ExtractedValue[DateType] | None = None
    notice_days: ExtractedValue[int] | None = None
    fee: ExtractedValue[float] | None = None


class OptionsObligations(_CoerceNullLeavesMixin):
    """Group D — options_obligations."""

    renewal_options: list[RenewalOption] | None = None
    termination_option: TerminationOption | None = None
    holdover_rate_pct: ExtractedValue[float] | None = None


class Opex(_CoerceNullLeavesMixin):
    """Group E — opex."""

    cam_structure: ExtractedValue[CamStructure] | None = None
    base_year: ExtractedValue[int] | None = None
    cam_cap_pct: ExtractedValue[float] | None = None
    cam_cap_type: ExtractedValue[str] | None = None


class LeaseExtraction(BaseModel):
    """Aggregated extraction output across all five field groups."""

    model_config = ConfigDict(extra="forbid", strict=False)

    parties_premises: PartiesPremises
    term: Term
    financial: Financial
    options_obligations: OptionsObligations
    opex: Opex


def empty_group(model_cls: type[BaseModel]) -> BaseModel:
    """Build a group with all null leaves (confidence 0)."""
    return model_cls.model_validate({})
