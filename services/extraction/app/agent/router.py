"""Stage 3 — router: field_matrix.yaml → pages/sections per group (AGENTS.md §7)."""

from __future__ import annotations

import re

from app.agent.matrix import FieldMatrix, load_field_matrix
from app.agent.types import ContextBlock, SectionedPage


def _keyword_match_count(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


def route(
    pages: list[SectionedPage],
    group_name: str,
    matrix: FieldMatrix | None = None,
) -> list[ContextBlock]:
    """Select pages for a field group; score = priority * match_count."""
    field_matrix = matrix or load_field_matrix()
    routing = field_matrix.groups[group_name]

    compiled_heading = [re.compile(pattern) for pattern in routing.heading_signals]
    blocks: list[ContextBlock] = []

    for page in pages:
        if page.maybe_scanned:
            continue

        tag_matches = sum(1 for tag in routing.section_tags if tag in page.section_tags)
        keyword_matches = _keyword_match_count(page.text, routing.keywords)
        heading_matches = sum(1 for pattern in compiled_heading if pattern.search(page.text))
        match_count = tag_matches + keyword_matches + heading_matches

        if match_count == 0:
            continue

        score = float(routing.priority * match_count)
        blocks.append(ContextBlock(page=page.page, text=page.text, score=score))

    blocks.sort(key=lambda block: (-block.score, block.page))
    return blocks
