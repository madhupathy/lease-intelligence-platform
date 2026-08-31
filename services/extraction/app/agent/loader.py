"""Stage 1 — loader: pdfplumber text per page (AGENTS.md §7)."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from app.agent.types import PageText

MIN_EXTRACTABLE_CHARS = 50


def load_pages(pdf_path: str | Path) -> list[PageText]:
    """Return extracted text per page; flag likely scanned pages (no OCR in scope)."""
    path = Path(pdf_path)
    pages: list[PageText] = []

    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            char_count = len(text.strip())
            maybe_scanned = char_count < MIN_EXTRACTABLE_CHARS
            pages.append(
                PageText(
                    page=index,
                    text=text,
                    char_count=char_count,
                    maybe_scanned=maybe_scanned,
                )
            )

    return pages
