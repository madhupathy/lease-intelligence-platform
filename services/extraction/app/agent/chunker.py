"""Section-aware text chunking for lease Q&A (AGENTS.md §5, §9)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import tiktoken

from app.agent.types import SectionedPage
from app.config import settings

_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page: int
    section_tag: str | None
    text_sha256: str


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _split_with_overlap(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = _ENCODER.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        piece = _ENCODER.decode(tokens[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= len(tokens):
            break
        start = max(end - overlap_tokens, 0)
        if start >= len(tokens):
            break
    return chunks


def _primary_section_tag(section_tags: list[str]) -> str | None:
    return section_tags[0] if section_tags else None


def chunk_sectioned_pages(
    sectioned_pages: list[SectionedPage],
    target_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[ChunkDraft]:
    """Produce section-aware chunks (~800 tokens, 100 overlap by default)."""
    max_tokens = target_tokens if target_tokens is not None else settings.chunk_target_tokens
    overlap = overlap_tokens if overlap_tokens is not None else settings.chunk_overlap_tokens

    drafts: list[ChunkDraft] = []
    for page in sectioned_pages:
        if page.maybe_scanned or not page.text.strip():
            continue

        section_tag = _primary_section_tag(page.section_tags)
        for piece in _split_with_overlap(page.text, max_tokens, overlap):
            drafts.append(
                ChunkDraft(
                    text=piece,
                    page=page.page,
                    section_tag=section_tag,
                    text_sha256=text_sha256(piece),
                )
            )
    return drafts
