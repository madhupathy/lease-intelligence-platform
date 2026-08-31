"""Unit tests for output guardrails."""

from __future__ import annotations

from datetime import date

from app.agent.schema import ExtractedValue, PartiesPremises, Term
from app.guardrails.citation_guard import CitationGuard, normalize_citation_text
from app.guardrails.context import GuardContext


def test_citation_guard_flags_missing_snippet_on_page() -> None:
    term = Term(
        commencement_date=ExtractedValue(value=date(2024, 1, 1), confidence=0.9, page=1, snippet="Wrong text"),
        expiration_date=ExtractedValue(value=None, confidence=0.0, page=None, snippet=None),
        initial_term_months=ExtractedValue(value=None, confidence=0.0, page=None, snippet=None),
    )
    ctx = GuardContext(
        group_name="term",
        group_model=term,
        page_texts={1: "Commencement Date: January 1, 2024"},
    )
    result = CitationGuard().check(ctx)
    assert result.verdict.value == "flag"
    assert "commencement_date" in ctx.needs_review_fields
    assert term.commencement_date.confidence <= 0.3


def test_citation_guard_passes_matching_snippet() -> None:
    term = Term(
        commencement_date=ExtractedValue(
            value=date(2024, 1, 1),
            confidence=0.9,
            page=1,
            snippet="Commencement Date: January 1, 2024",
        ),
        expiration_date=ExtractedValue(value=None, confidence=0.0, page=None, snippet=None),
        initial_term_months=ExtractedValue(value=None, confidence=0.0, page=None, snippet=None),
    )
    ctx = GuardContext(
        group_name="term",
        group_model=term,
        page_texts={1: "Commencement Date: January 1, 2024"},
    )
    result = CitationGuard().check(ctx)
    assert result.verdict.value == "pass_"
    assert term.commencement_date.confidence == 0.9


def test_citation_guard_passes_whitespace_and_case_differing_snippet() -> None:
    """Snippets with newlines / multi-spaces / case diffs must not be penalized."""
    parties = PartiesPremises(
        landlord=ExtractedValue(
            value="EQC CAPITOL TOWER PROPERTY LLC",
            confidence=0.95,
            page=1,
            snippet="EQC  CAPITOL\nTOWER PROPERTY   LLC",
        ),
        tenant=ExtractedValue(
            value="CrowdStrike, Inc.",
            confidence=0.92,
            page=1,
            snippet="CrowdStrike,\nInc.",
        ),
        premises_address=ExtractedValue(value=None, confidence=0.0, page=None, snippet=None),
        rentable_sqft=ExtractedValue(value=None, confidence=0.0, page=None, snippet=None),
    )
    page = "Landlord: eqc capitol tower property llc\nTenant: CROWDSTRIKE, INC. Suite 100"
    ctx = GuardContext(group_name="parties_premises", group_model=parties, page_texts={1: page})

    assert normalize_citation_text(parties.landlord.snippet) in normalize_citation_text(page)

    result = CitationGuard().check(ctx)
    assert result.verdict.value == "pass_"
    assert parties.landlord.confidence == 0.95
    assert parties.tenant.confidence == 0.92
    assert "landlord" not in ctx.needs_review_fields
    assert "tenant" not in ctx.needs_review_fields
