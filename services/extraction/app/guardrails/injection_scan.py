"""Injection heuristic scan — flag, never block (AGENTS.md §8)."""

from __future__ import annotations

import re

from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext

_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+previous"),
    re.compile(r"(?i)system\s+prompt"),
    re.compile(r"(?i)you\s+are\s+now"),
    re.compile(r"(?i)disregard"),
]


class InjectionScan:
    def check(self, ctx: GuardContext) -> Result:
        if not ctx.pages:
            return Result(Verdict.PASS)

        for page in ctx.pages:
            for pattern in _INJECTION_PATTERNS:
                if pattern.search(page.text):
                    return Result(
                        Verdict.FLAG,
                        f"Possible prompt injection detected on page {page.page}",
                    )

        return Result(Verdict.PASS)
