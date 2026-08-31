"""Pluggable guardrails (AGENTS.md §8)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Verdict(str, Enum):
    PASS = "pass_"
    FLAG = "flag"
    BLOCK = "block"


@dataclass
class Result:
    verdict: Verdict
    reason: str = ""


class Guardrail(Protocol):
    def check(self, ctx: object) -> Result: ...
