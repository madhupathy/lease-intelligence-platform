"""Level 1 — extraction accuracy vs gold (offline, DB effective fields)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, ExtractedField, ExtractionRun, Lease
from app.field_groups import FIELD_GROUPS, FIELD_TO_GROUP
from evals.compare import values_match
from evals.gold_io import load_gold


CONFIDENCE_BUCKETS: list[tuple[str, float, float]] = [
    ("0.0–0.5", 0.0, 0.5),
    ("0.5–0.7", 0.5, 0.7),
    ("0.7–0.9", 0.7, 0.9),
    ("0.9–1.0", 0.9, 1.0001),
]


@dataclass
class FieldResult:
    field_key: str
    group: str
    passed: bool
    gold_value: Any
    extracted_value: Any
    gold_page: int | None
    extracted_page: int | None
    page_match: bool | None
    confidence: float | None
    reason: str = ""


@dataclass
class LeaseEvalResult:
    lease_id: str
    lease_name: str
    pdf_stem: str
    gold_path: str
    field_results: list[FieldResult] = field(default_factory=list)
    model: str | None = None
    prompt_version: str | None = None

    @property
    def overall_accuracy(self) -> float:
        if not self.field_results:
            return 0.0
        return sum(1 for r in self.field_results if r.passed) / len(self.field_results)

    @property
    def page_citation_accuracy(self) -> float | None:
        scored = [r for r in self.field_results if r.page_match is not None]
        if not scored:
            return None
        return sum(1 for r in scored if r.page_match) / len(scored)

    def group_accuracy(self) -> dict[str, float]:
        by_group: dict[str, list[FieldResult]] = {g: [] for g in FIELD_GROUPS}
        for result in self.field_results:
            by_group.setdefault(result.group, []).append(result)
        out: dict[str, float] = {}
        for group, rows in by_group.items():
            if not rows:
                out[group] = 0.0
            else:
                out[group] = sum(1 for r in rows if r.passed) / len(rows)
        return out

    def failures(self) -> list[FieldResult]:
        return [r for r in self.field_results if not r.passed]


@dataclass
class CalibrationBucket:
    label: str
    count: int
    correct: int

    @property
    def accuracy(self) -> float | None:
        if self.count == 0:
            return None
        return self.correct / self.count


def _extracted_value_and_page(field: ExtractedField) -> tuple[Any, int | None]:
    raw = field.value_json
    if isinstance(raw, dict) and "value" in raw:
        return raw.get("value"), field.page if field.page is not None else raw.get("page")
    return raw, field.page


def load_effective_extraction(
    session: Session,
    lease_id: uuid.UUID,
) -> tuple[dict[str, ExtractedField], str | None, str | None, str | None]:
    """Return effective fields by key plus model/prompt metadata from latest run."""
    fields = session.scalars(
        select(ExtractedField).where(
            ExtractedField.lease_id == lease_id,
            ExtractedField.effective.is_(True),
        )
    ).all()
    by_key = {f.field_key: f for f in fields}

    model = None
    prompt_version = None
    if fields:
        run = session.get(ExtractionRun, fields[0].run_id)
        if run is not None:
            model = run.model
            prompt_version = run.prompt_version

    lease = session.get(Lease, lease_id)
    lease_name = lease.name if lease else None
    return by_key, model, prompt_version, lease_name


def resolve_lease_for_gold(
    session: Session,
    gold: dict[str, Any],
) -> uuid.UUID | None:
    if gold.get("lease_id"):
        return uuid.UUID(str(gold["lease_id"]))

    stem = gold.get("pdf_stem")
    if not stem:
        return None

    docs = session.scalars(select(Document)).all()
    for doc in docs:
        name = Path(doc.filename).stem
        if name == stem or stem in name or name in stem:
            return doc.lease_id

    if gold.get("lease_name"):
        lease = session.scalar(select(Lease).where(Lease.name == gold["lease_name"]))
        if lease is not None:
            return lease.id
    return None


def evaluate_lease(
    session: Session,
    gold_path: Path,
    lease_id: uuid.UUID | None = None,
) -> LeaseEvalResult:
    gold = load_gold(gold_path)
    resolved = lease_id or resolve_lease_for_gold(session, gold)
    if resolved is None:
        raise ValueError(f"Could not resolve lease for gold file {gold_path.name}")

    by_key, model, prompt_version, lease_name = load_effective_extraction(session, resolved)
    results: list[FieldResult] = []

    for field_key, gold_entry in gold["fields"].items():
        group = FIELD_TO_GROUP.get(field_key, "unknown")
        gold_value = gold_entry.get("value")
        gold_page = gold_entry.get("page")
        row = by_key.get(field_key)

        if row is None:
            results.append(
                FieldResult(
                    field_key=field_key,
                    group=group,
                    passed=gold_value in (None, [], {}),
                    gold_value=gold_value,
                    extracted_value=None,
                    gold_page=gold_page,
                    extracted_page=None,
                    page_match=None if gold_page is None else False,
                    confidence=None,
                    reason="missing effective field" if gold_value not in (None, [], {}) else "both null",
                )
            )
            continue

        extracted_value, extracted_page = _extracted_value_and_page(row)
        passed = values_match(field_key, gold_value, extracted_value)
        page_match: bool | None
        if gold_page is None:
            page_match = None
        else:
            page_match = extracted_page == gold_page

        conf = float(row.confidence) if row.confidence is not None else None
        results.append(
            FieldResult(
                field_key=field_key,
                group=group,
                passed=passed,
                gold_value=gold_value,
                extracted_value=extracted_value,
                gold_page=gold_page,
                extracted_page=extracted_page,
                page_match=page_match,
                confidence=conf,
                reason="ok" if passed else "value mismatch",
            )
        )

    return LeaseEvalResult(
        lease_id=str(resolved),
        lease_name=lease_name or gold.get("lease_name") or "",
        pdf_stem=gold["pdf_stem"],
        gold_path=str(gold_path),
        field_results=results,
        model=model,
        prompt_version=prompt_version,
    )


def confidence_calibration(results: list[LeaseEvalResult]) -> list[CalibrationBucket]:
    buckets = [CalibrationBucket(label=label, count=0, correct=0) for label, _, _ in CONFIDENCE_BUCKETS]
    for lease in results:
        for field in lease.field_results:
            if field.confidence is None:
                continue
            for index, (_, lo, hi) in enumerate(CONFIDENCE_BUCKETS):
                if lo <= field.confidence < hi:
                    buckets[index].count += 1
                    if field.passed:
                        buckets[index].correct += 1
                    break
    return buckets


def aggregate_group_accuracy(results: list[LeaseEvalResult]) -> dict[str, float]:
    totals: dict[str, list[bool]] = {g: [] for g in FIELD_GROUPS}
    for lease in results:
        for field in lease.field_results:
            totals.setdefault(field.group, []).append(field.passed)
    return {
        group: (sum(1 for p in passes if p) / len(passes) if passes else 0.0)
        for group, passes in totals.items()
    }
