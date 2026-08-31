"""Stage 4 — budget: tiktoken token budgeting per call (AGENTS.md §7)."""

from __future__ import annotations

import tiktoken

from app.agent.types import BudgetResult, ContextBlock, PageText
from app.config import settings

_ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Approximate token count using cl100k_base."""
    return len(_ENCODER.encode(text))


def _format_block(block: ContextBlock) -> str:
    return f"[Page {block.page}]\n{block.text}"


def _assemble_blocks(blocks: list[ContextBlock], max_tokens: int) -> tuple[str, bool, int]:
    selected: list[ContextBlock] = []
    truncated = False

    for block in sorted(blocks, key=lambda item: (-item.score, item.page)):
        candidate = selected + [block]
        candidate_text = "\n\n".join(_format_block(item) for item in candidate)
        if count_tokens(candidate_text) <= max_tokens:
            selected = candidate
        else:
            truncated = True

    if not selected and blocks:
        # Drop lowest-score blocks until something fits, or take first page truncated.
        ordered = sorted(blocks, key=lambda item: (-item.score, item.page))
        truncated = True
        for end in range(1, len(ordered) + 1):
            candidate = ordered[:end]
            candidate_text = "\n\n".join(_format_block(item) for item in candidate)
            if count_tokens(candidate_text) <= max_tokens:
                selected = candidate
                break
        if not selected and ordered:
            first = ordered[0]
            selected = [ContextBlock(page=first.page, text=first.text[:2000], score=first.score)]

    context = "\n\n".join(_format_block(item) for item in sorted(selected, key=lambda item: item.page))
    token_count = count_tokens(context)
    if token_count > max_tokens:
        truncated = True
    return context, truncated, token_count


def enforce_budget(
    blocks: list[ContextBlock],
    max_tokens: int | None = None,
    all_pages: list[PageText] | None = None,
) -> BudgetResult:
    """Trim lowest-relevance sections to MAX_CONTEXT_TOKENS; set truncated flag."""
    limit = max_tokens if max_tokens is not None else settings.max_context_tokens

    if not blocks:
        if not all_pages:
            return BudgetResult(context="", truncated=True, token_count=0)

        fallback_blocks = [
            ContextBlock(page=page.page, text=page.text, score=0.0)
            for page in sorted(all_pages, key=lambda item: item.page)
            if not page.maybe_scanned
        ]
        context, truncated, token_count = _assemble_blocks(fallback_blocks, limit)
        return BudgetResult(context=context, truncated=True or truncated, token_count=token_count)

    context, truncated, token_count = _assemble_blocks(blocks, limit)
    return BudgetResult(context=context, truncated=truncated, token_count=token_count)
