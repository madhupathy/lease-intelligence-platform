"""Stage 2 — sectioner: regex/heading section tagging, no LLM (AGENTS.md §7)."""

from __future__ import annotations

import re

from app.agent.matrix import FieldMatrix, load_field_matrix
from app.agent.types import PageText, SectionedPage

# Built-in heading heuristics (pure functions, no LLM).
_ARTICLE_RE = re.compile(r"(?im)^\s*ARTICLE\s+[IVXLC\d]+")
_SECTION_RE = re.compile(r"(?im)^\s*Section\s+\d+[\.\:]?")
_NUMBERED_HEADING_RE = re.compile(r"(?im)^\s*\d+[\.\)]\s+[A-Z]")
_ALL_CAPS_LINE_RE = re.compile(r"^[A-Z][A-Z0-9\s,&'\-/]{8,}$")


def _is_all_caps_heading(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 8:
        return False
    return _ALL_CAPS_LINE_RE.match(stripped) is not None


def detect_builtin_headings(text: str) -> list[str]:
    """Detect structural headings in page text."""
    tags: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _ARTICLE_RE.match(stripped):
            tags.append("article")
        if _SECTION_RE.match(stripped):
            tags.append("section")
        if _NUMBERED_HEADING_RE.match(stripped):
            tags.append("numbered_heading")
        if _is_all_caps_heading(stripped):
            tags.append("all_caps_heading")
    return tags


def _compile_matrix_patterns(matrix: FieldMatrix) -> dict[str, list[re.Pattern[str]]]:
    compiled: dict[str, list[re.Pattern[str]]] = {}
    for group_name, routing in matrix.groups.items():
        compiled[group_name] = [re.compile(pattern) for pattern in routing.heading_signals]
    return compiled


def _matrix_tags_for_text(text: str, patterns: list[re.Pattern[str]], section_tags: list[str]) -> list[str]:
    tags: list[str] = []
    for pattern in patterns:
        if pattern.search(text):
            tags.extend(section_tags)
    return tags


def tag_sections(
    pages: list[PageText],
    matrix: FieldMatrix | None = None,
) -> list[SectionedPage]:
    """Tag each page with section signals from headings and field_matrix patterns."""
    field_matrix = matrix or load_field_matrix()
    compiled = _compile_matrix_patterns(field_matrix)

    sectioned: list[SectionedPage] = []
    for page in pages:
        tags: list[str] = []
        tags.extend(detect_builtin_headings(page.text))

        for group_name, routing in field_matrix.groups.items():
            tags.extend(
                _matrix_tags_for_text(page.text, compiled[group_name], routing.section_tags)
            )

        # Deduplicate while preserving order.
        unique_tags = list(dict.fromkeys(tags))

        sectioned.append(
            SectionedPage(
                page=page.page,
                text=page.text,
                char_count=page.char_count,
                maybe_scanned=page.maybe_scanned,
                section_tags=unique_tags,
            )
        )

    return sectioned
