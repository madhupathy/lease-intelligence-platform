"""Shared pipeline datatypes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    char_count: int
    maybe_scanned: bool


@dataclass
class SectionedPage:
    page: int
    text: str
    char_count: int
    maybe_scanned: bool
    section_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContextBlock:
    page: int
    text: str
    score: float


@dataclass(frozen=True)
class BudgetResult:
    context: str
    truncated: bool
    token_count: int


@dataclass
class ExtractGroupResult:
    group_name: str
    model: object
    tokens_in: int
    tokens_out: int
    degraded: bool = False
