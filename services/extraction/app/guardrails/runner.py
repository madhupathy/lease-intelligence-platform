"""Guardrail chain runner."""

from __future__ import annotations

from typing import Protocol

from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext


class Guardrail(Protocol):
    def check(self, ctx: GuardContext) -> Result: ...


def run_guardrails(guardrails: list[Guardrail], ctx: GuardContext) -> Result:
    """Run ordered guardrails; first BLOCK stops the chain."""
    for guard in guardrails:
        result = guard.check(ctx)
        if result.verdict == Verdict.FLAG and result.reason:
            ctx.flags.append(result.reason)
        if result.verdict == Verdict.BLOCK:
            return result
    return Result(Verdict.PASS)
