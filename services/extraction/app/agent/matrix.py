"""Field-matrix loader — validates field_matrix.yaml (AGENTS.md §6, §7)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

_EXTRACTION_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MATRIX_PATH = _EXTRACTION_ROOT / "field_matrix.yaml"


class FieldGroupRouting(BaseModel):
    """Routing signals for one extraction field group."""

    model_config = ConfigDict(extra="forbid", strict=True)

    section_tags: list[str] = Field(min_length=1)
    heading_signals: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    priority: int


class FieldMatrix(BaseModel):
    """Top-level field_matrix.yaml structure."""

    model_config = ConfigDict(extra="forbid", strict=True)

    groups: dict[str, FieldGroupRouting] = Field(min_length=1)


def load_field_matrix(path: Path | None = None) -> FieldMatrix:
    """Load and validate field_matrix.yaml from disk."""
    matrix_path = path or DEFAULT_MATRIX_PATH
    raw = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    return FieldMatrix.model_validate(raw)
