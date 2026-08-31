"""Output guard: pydantic schema validation (AGENTS.md §8)."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from app.agent.extractor import GROUP_MODELS
from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext


class SchemaGuard:
    def check(self, ctx: GuardContext) -> Result:
        if ctx.group_name is None or ctx.group_model is None:
            return Result(Verdict.PASS)

        model_cls = GROUP_MODELS.get(ctx.group_name)
        if model_cls is None:
            return Result(Verdict.FLAG, f"Unknown group for schema guard: {ctx.group_name}")

        try:
            model_cls.model_validate(ctx.group_model.model_dump())
        except ValidationError as error:
            return Result(Verdict.FLAG, f"Schema validation failed: {error}")

        return Result(Verdict.PASS)
