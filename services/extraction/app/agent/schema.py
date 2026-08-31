"""Pydantic extraction contract — field groups from AGENTS.md §6.

Every leaf field is an ExtractedValue[T] carrying value, confidence, page, and snippet.
Missing fields use value=null and confidence=0.
"""

from __future__ import annotations

from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ExtractedValue(BaseModel, Generic[T]):
    """Single extracted field with provenance (AGENTS.md §6)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    value: T | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    page: int | None = None
    snippet: str | None = None


class PartiesPremises(BaseModel):
    """Group A — parties_premises."""

    model_config = ConfigDict(extra="forbid", strict=True)

    landlord: ExtractedValue[str]
    tenant: ExtractedValue[str]
    premises_address: ExtractedValue[str]
    rentable_sqft: ExtractedValue[int]


class Term(BaseModel):
    """Group B — term."""

    model_config = ConfigDict(extra="forbid", strict=True)

    commencement_date: ExtractedValue[date]
    expiration_date: ExtractedValue[date]
    initial_term_months: ExtractedValue[int]


class BaseRentPeriod(BaseModel):
    """One row in base_rent_schedule."""

    model_config = ConfigDict(extra="forbid", strict=True)

    period_start: ExtractedValue[date]
    period_end: ExtractedValue[date]
    annual_rent: ExtractedValue[float]
    monthly_rent: ExtractedValue[float]


EscalationType = Literal["fixed_pct", "cpi", "stepped", "none"]
CamStructure = Literal["net", "gross", "base_year", "stop"]


class Financial(BaseModel):
    """Group C — financial."""

    model_config = ConfigDict(extra="forbid", strict=True)

    base_rent_schedule: list[BaseRentPeriod]
    escalation_type: ExtractedValue[EscalationType]
    escalation_value: ExtractedValue[float]
    security_deposit: ExtractedValue[float]


class RenewalOption(BaseModel):
    """One renewal option entry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    term_months: ExtractedValue[int]
    notice_min_days: ExtractedValue[int]
    notice_max_days: ExtractedValue[int]
    rent_basis: ExtractedValue[str]


class TerminationOption(BaseModel):
    """Termination option sub-structure. Sub-fields may be partially present (D8)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    date: ExtractedValue[date]
    notice_days: ExtractedValue[int]
    fee: ExtractedValue[float]


class OptionsObligations(BaseModel):
    """Group D — options_obligations."""

    model_config = ConfigDict(extra="forbid", strict=True)

    renewal_options: list[RenewalOption]
    termination_option: TerminationOption | None = None
    holdover_rate_pct: ExtractedValue[float]


class Opex(BaseModel):
    """Group E — opex."""

    model_config = ConfigDict(extra="forbid", strict=True)

    cam_structure: ExtractedValue[CamStructure]
    base_year: ExtractedValue[int]
    cam_cap_pct: ExtractedValue[float]
    cam_cap_type: ExtractedValue[str]


class LeaseExtraction(BaseModel):
    """Aggregated extraction output across all five field groups."""

    model_config = ConfigDict(extra="forbid", strict=True)

    parties_premises: PartiesPremises
    term: Term
    financial: Financial
    options_obligations: OptionsObligations
    opex: Opex
