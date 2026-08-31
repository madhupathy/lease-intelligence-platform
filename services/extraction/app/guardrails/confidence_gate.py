"""Output guard: low-confidence fields need review (AGENTS.md §8)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agent.schema import ExtractedValue
from app.config import settings
from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext


def _walk_extracted(model: BaseModel, prefix: str = "") -> list[tuple[str, ExtractedValue[Any]]]:
    pairs: list[tuple[str, ExtractedValue[Any]]] = []
    for field_name in model.model_fields:
        field_path = f"{prefix}.{field_name}" if prefix else field_name
        attr = getattr(model, field_name)
        if isinstance(attr, ExtractedValue):
            pairs.append((field_path, attr))
        elif isinstance(attr, BaseModel):
            pairs.extend(_walk_extracted(attr, field_path))
        elif isinstance(attr, list):
            for index, item in enumerate(attr):
                if isinstance(item, BaseModel):
                    pairs.extend(_walk_extracted(item, f"{field_path}[{index}]"))
    return pairs


class ConfidenceGate:
    def check(self, ctx: GuardContext) -> Result:
        if ctx.group_model is None:
            return Result(Verdict.PASS)

        flagged: list[str] = []
        for field_path, extracted in _walk_extracted(ctx.group_model):
            override = ctx.field_confidence_overrides.get(field_path)
            confidence = override if override is not None else extracted.confidence
            if extracted.value is not None and confidence < settings.review_threshold:
                ctx.needs_review_fields.add(field_path)
                flagged.append(f"{field_path} confidence {confidence} < {settings.review_threshold}")

        if flagged:
            return Result(Verdict.FLAG, "; ".join(flagged))

        return Result(Verdict.PASS)
