"""Output guard: snippet must appear on cited page (AGENTS.md §8)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from app.agent.schema import ExtractedValue
from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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
                flagged.append(f"{field_path}: page {extracted.page} not in source")
                ctx.needs_review_fields.add(field_path)
                ctx.field_confidence_overrides[field_path] = min(extracted.confidence, 0.3)
                continue

            normalized_snippet = _normalize_whitespace(extracted.snippet)
            normalized_page = _normalize_whitespace(page_text)
            if normalized_snippet and normalized_snippet not in normalized_page:
                flagged.append(f"{field_path}: snippet not found on page {extracted.page}")
                ctx.needs_review_fields.add(field_path)
                ctx.field_confidence_overrides[field_path] = min(extracted.confidence, 0.3)
                extracted.confidence = min(extracted.confidence, 0.3)

        if flagged:
            return Result(Verdict.FLAG, "; ".join(flagged))

        return Result(Verdict.PASS)
