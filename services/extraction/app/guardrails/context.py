"""Guardrail execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agent.types import PageText


@dataclass
class GuardContext:
    file_path: Path | None = None
    pages: list[PageText] | None = None
    group_name: str | None = None
    group_model: BaseModel | None = None
    page_texts: dict[int, str] | None = None
    flags: list[str] = field(default_factory=list)
    needs_review_fields: set[str] = field(default_factory=set)
    field_confidence_overrides: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
