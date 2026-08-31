"""Unit tests for output guardrails."""

from __future__ import annotations

from datetime import date

from app.agent.schema import ExtractedValue, OptionsObligations, Term, TerminationOption
from app.guardrails.citation_guard import CitationGuard
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
