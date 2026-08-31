"""Unit tests for section-aware chunking."""

from __future__ import annotations

from app.agent.chunker import chunk_sectioned_pages, count_tokens
from app.agent.types import SectionedPage


def test_chunk_sizes_and_overlap() -> None:
    words = "rent " * 1200
    page = SectionedPage(
        page=3,
        text=words,
        char_count=len(words),
        maybe_scanned=False,
        section_tags=["base_rent"],
    )
    drafts = chunk_sectioned_pages([page], target_tokens=200, overlap_tokens=50)
    assert len(drafts) > 1
    for draft in drafts:
        assert draft.page == 3
        assert draft.section_tag == "base_rent"
        assert count_tokens(draft.text) <= 200
        assert draft.text_sha256


def test_skips_scanned_pages() -> None:
    page = SectionedPage(page=1, text="", char_count=0, maybe_scanned=True, section_tags=[])
    assert chunk_sectioned_pages([page]) == []
