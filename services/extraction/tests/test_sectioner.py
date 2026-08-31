"""Unit tests for sectioner heading detection."""

from __future__ import annotations

from app.agent.matrix import FieldMatrix, FieldGroupRouting
from app.agent.sectioner import detect_builtin_headings, tag_sections
from app.agent.types import PageText


def test_detect_article_and_section_headings() -> None:
    text = "ARTICLE IV\nSection 12. Base Rent\nLEASE TERM AND COMMENCEMENT"
    tags = detect_builtin_headings(text)
    assert "article" in tags
    assert "section" in tags
    assert "all_caps_heading" in tags


def test_detect_numbered_heading() -> None:
    text = "1. Premises\nRegular paragraph text."
    tags = detect_builtin_headings(text)
    assert "numbered_heading" in tags


def test_tag_sections_applies_matrix_signals() -> None:
    matrix = FieldMatrix(
        groups={
            "financial": FieldGroupRouting(
                section_tags=["base_rent"],
                heading_signals=[r"(?i)base rent"],
                keywords=["minimum rent"],
                priority=30,
            )
        }
    )
    pages = [
        PageText(
            page=1,
            text="ARTICLE 3\nBASE RENT AND MINIMUM RENT\nTenant pays base rent monthly.",
            char_count=60,
            maybe_scanned=False,
        )
    ]
    sectioned = tag_sections(pages, matrix=matrix)
    assert "base_rent" in sectioned[0].section_tags
    assert "article" in sectioned[0].section_tags


def test_tag_sections_marks_scanned_pages() -> None:
    pages = [PageText(page=1, text="", char_count=0, maybe_scanned=True)]
    sectioned = tag_sections(pages)
    assert sectioned[0].maybe_scanned is True
