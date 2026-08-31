"""Output guard: snippet must appear on cited page (AGENTS.md §8)."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel

from app.agent.schema import ExtractedValue
from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext

logger = logging.getLogger(__name__)


def normalize_citation_text(text: str) -> str:
    """Lowercase and collapse all whitespace/newlines for substring matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _walk_model(model: BaseModel, prefix: str = "") -> list[tuple[str, ExtractedValue[Any]]]:
    pairs: list[tuple[str, ExtractedValue[Any]]] = []
    for field_name in model.model_fields:
        field_path = f"{prefix}.{field_name}" if prefix else field_name
        attr = getattr(model, field_name)
        if isinstance(attr, ExtractedValue):
            pairs.append((field_path, attr))
        elif isinstance(attr, BaseModel):
            pairs.extend(_walk_model(attr, field_path))
        elif isinstance(attr, list):
            for index, item in enumerate(attr):
                if isinstance(item, BaseModel):
                    pairs.extend(_walk_model(item, f"{field_path}[{index}]"))
    return pairs


def _penalize(ctx: GuardContext, field_path: str, extracted: ExtractedValue[Any], reason: str) -> None:
    logger.info(
        "CitationGuard penalize field_key=%s reason=%s page=%s snippet=%r",
        field_path,
        reason,
        extracted.page,
        (extracted.snippet or "")[:120],
    )
    ctx.needs_review_fields.add(field_path)
    ctx.field_confidence_overrides[field_path] = min(extracted.confidence, 0.3)
    extracted.confidence = min(extracted.confidence, 0.3)


class CitationGuard:
    def check(self, ctx: GuardContext) -> Result:
        if ctx.group_model is None or ctx.page_texts is None:
            return Result(Verdict.PASS)

        flagged: list[str] = []
        for field_path, extracted in _walk_model(ctx.group_model):
            if extracted.value is None or not extracted.snippet or extracted.page is None:
                continue

            page_text = ctx.page_texts.get(extracted.page)
            if page_text is None:
                reason = f"page {extracted.page} not in source"
                flagged.append(f"{field_path}: {reason}")
                _penalize(ctx, field_path, extracted, reason)
                continue

            normalized_snippet = normalize_citation_text(extracted.snippet)
            normalized_page = normalize_citation_text(page_text)
            if normalized_snippet and normalized_snippet not in normalized_page:
                reason = f"snippet not found on page {extracted.page}"
                flagged.append(f"{field_path}: {reason}")
                _penalize(ctx, field_path, extracted, reason)

        if flagged:
            return Result(Verdict.FLAG, "; ".join(flagged))

        return Result(Verdict.PASS)
