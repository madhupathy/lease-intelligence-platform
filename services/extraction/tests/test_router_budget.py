"""Unit tests for router and budget stages."""

from __future__ import annotations

from app.agent.budget import count_tokens, enforce_budget
from app.agent.matrix import FieldMatrix, FieldGroupRouting
from app.agent.router import route
from app.agent.types import ContextBlock, PageText, SectionedPage


def _financial_matrix() -> FieldMatrix:
    return FieldMatrix(
        groups={
            "financial": FieldGroupRouting(
                section_tags=["base_rent"],
                heading_signals=[r"(?i)base rent"],
                keywords=["minimum rent", "fixed rent"],
                priority=10,
            )
        }
    )


def test_router_scores_matching_pages() -> None:
    pages = [
        SectionedPage(
            page=1,
            text="Parties only",
            char_count=20,
            maybe_scanned=False,
            section_tags=["parties"],
        ),
        SectionedPage(
            page=2,
            text="BASE RENT schedule with minimum rent",
            char_count=40,
            maybe_scanned=False,
            section_tags=["base_rent"],
        ),
    ]
    blocks = route(pages, "financial", matrix=_financial_matrix())
    assert len(blocks) == 1
    assert blocks[0].page == 2
    assert blocks[0].score > 0


def test_router_skips_scanned_pages() -> None:
    pages = [
        SectionedPage(
            page=1,
            text="BASE RENT",
            char_count=0,
            maybe_scanned=True,
            section_tags=["base_rent"],
        )
    ]
    blocks = route(pages, "financial", matrix=_financial_matrix())
    assert blocks == []


def test_budget_honors_token_cap() -> None:
    long_text = "rent " * 5000
    blocks = [
        ContextBlock(page=1, text=long_text, score=10.0),
        ContextBlock(page=2, text=long_text, score=5.0),
    ]
    result = enforce_budget(blocks, max_tokens=500)
    assert result.token_count <= 500
    assert result.truncated is True


def test_budget_zero_match_fallback_from_page_one() -> None:
    pages = [
        PageText(page=1, text="Page one intro", char_count=20, maybe_scanned=False),
        PageText(page=2, text="Page two body", char_count=20, maybe_scanned=False),
    ]
    result = enforce_budget([], max_tokens=count_tokens("Page one intro") + 5, all_pages=pages)
    assert result.truncated is True
    assert "Page one intro" in result.context
