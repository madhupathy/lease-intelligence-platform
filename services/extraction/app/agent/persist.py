"""Stage 7 — persist: runs, fields, obligations, events (AGENTS.md §7)."""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agent.consolidator import consolidate
from app.agent.extractor import PROMPT_VERSION
from app.agent.schema import LeaseExtraction
from app.agent.serialization import flatten_lease_extraction, lease_extraction_from_field_rows
from app.config import settings
from app.db.models import ExtractedField, ExtractionRun, Obligation
from app.events import EventPublisher, PostgresEventPublisher

logger = logging.getLogger(__name__)

SUCCESS_STATUS = "completed"


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_cached_extraction(session: Session, document_id: uuid.UUID) -> LeaseExtraction | None:
    """Return cached extraction if a successful run exists; idempotency short-circuit."""
    cached = load_cached_run(session, document_id)
    if cached is None:
        return None
    return cached.extraction


def load_cached_run(session: Session, document_id: uuid.UUID) -> tuple[ExtractionRun, LeaseExtraction] | None:
    """Return cached run + extraction for idempotency short-circuit."""
    run = session.scalar(
        select(ExtractionRun).where(
            ExtractionRun.document_id == document_id,
            ExtractionRun.prompt_version == PROMPT_VERSION,
            ExtractionRun.model == settings.extraction_model,
            ExtractionRun.status == SUCCESS_STATUS,
        )
    )
    if run is None:
        return None

    logger.info(
        "cache hit for document_id=%s prompt_version=%s model=%s",
        document_id,
        PROMPT_VERSION,
        settings.extraction_model,
    )
    rows = {field.field_key: field.value_json for field in run.extracted_fields}
    return run, lease_extraction_from_field_rows(rows)


def _confidence_for_value(raw: Any) -> float:
    if isinstance(raw, dict) and "confidence" in raw:
        return float(raw.get("confidence", 0))
    return 0.0


def _page_for_value(raw: Any) -> int | None:
    if isinstance(raw, dict):
        page = raw.get("page")
        return int(page) if page is not None else None
    return None


def _snippet_for_value(raw: Any) -> str | None:
    if isinstance(raw, dict):
        snippet = raw.get("snippet")
        return str(snippet) if snippet is not None else None
    return None


def _collect_row_confidences(node: Any) -> list[float]:
    """Collect confidence values from nested ExtractedValue-shaped dicts."""
    confidences: list[float] = []
    if isinstance(node, dict):
        if "confidence" in node and ("value" in node or "snippet" in node or "page" in node):
            try:
                confidences.append(float(node["confidence"]))
            except (TypeError, ValueError):
                pass
            return confidences
        for value in node.values():
            confidences.extend(_collect_row_confidences(value))
    elif isinstance(node, list):
        for item in node:
            confidences.extend(_collect_row_confidences(item))
    return confidences


def aggregate_list_confidence(rows: list[Any]) -> float:
    """Mean of row-level leaf confidences; empty list → 0.0."""
    if not rows:
        return 0.0
    confidences = _collect_row_confidences(rows)
    if not confidences:
        return 0.0
    return sum(confidences) / len(confidences)


def _list_needs_review(
    field_key: str,
    rows: list[Any],
    confidence: float,
    needs_review_fields: set[str],
) -> bool:
    """List fields need review when empty, low aggregate confidence, or a nested leaf flagged."""
    if not rows:
        return True
    if confidence < settings.review_threshold:
        return True
    if field_key in needs_review_fields:
        return True
    prefix_bracket = f"{field_key}["
    prefix_dot = f"{field_key}."
    return any(
        key.startswith(prefix_bracket) or key.startswith(prefix_dot)
        for key in needs_review_fields
    )


def _write_extracted_fields(
    session: Session,
    run: ExtractionRun,
    lease_id: uuid.UUID,
    extraction: LeaseExtraction,
    needs_review_fields: set[str],
) -> int:
    flat = flatten_lease_extraction(extraction)
    written = 0
    for field_key, raw in flat.items():
        if isinstance(raw, list):
            confidence = aggregate_list_confidence(raw)
            page = None
            snippet = None
            needs_review = _list_needs_review(field_key, raw, confidence, needs_review_fields)
        elif isinstance(raw, dict):
            confidence = _confidence_for_value(raw)
            page = _page_for_value(raw)
            snippet = _snippet_for_value(raw)
            empty_value = raw.get("value") is None
            needs_review = (
                field_key in needs_review_fields
                or confidence < settings.review_threshold
                or empty_value
            )
        else:
            confidence = 0.0
            page = None
            snippet = None
            needs_review = True

        session.add(
            ExtractedField(
                run_id=run.id,
                lease_id=lease_id,
                field_key=field_key,
                value_json=raw,
                confidence=confidence,
                page=page,
                source_snippet=snippet,
                needs_review=needs_review,
                effective=False,
            )
        )
        written += 1

    logger.info(
        "persist extracted_fields: lease_id=%s run_id=%s rows=%s keys=%s",
        lease_id,
        run.id,
        written,
        sorted(flat.keys()),
    )
    return written


def derive_obligations_for_lease(
    session: Session,
    lease_id: uuid.UUID,
) -> list[Obligation]:
    """Delete-and-recreate obligations from effective fields (D13)."""
    effective_fields = session.scalars(
        select(ExtractedField).where(
            ExtractedField.lease_id == lease_id,
            ExtractedField.effective.is_(True),
        )
    ).all()
    return _derive_obligations(session, lease_id, list(effective_fields))


def _derive_obligations(
    session: Session,
    lease_id: uuid.UUID,
    effective_fields: list[ExtractedField],
) -> list[Obligation]:
    session.execute(delete(Obligation).where(Obligation.lease_id == lease_id))

    by_key = {field.field_key: field for field in effective_fields}
    obligations: list[Obligation] = []

    expiration_field = by_key.get("expiration_date")
    expiration = None
    if expiration_field and isinstance(expiration_field.value_json, dict):
        expiration = _parse_date(expiration_field.value_json.get("value"))

    if expiration is not None:
        obligations.append(
            Obligation(
                lease_id=lease_id,
                kind="expiration",
                deadline=expiration,
                description="Lease expiration",
                source_field_id=expiration_field.id if expiration_field else None,
            )
        )

    renewal_field = by_key.get("renewal_options")
    if renewal_field and isinstance(renewal_field.value_json, list):
        for index, option in enumerate(renewal_field.value_json):
            if not isinstance(option, dict):
                continue
            term_months = option.get("term_months", {})
            notice_min_raw = option.get("notice_min_days", {})
            term_months_val = term_months.get("value") if isinstance(term_months, dict) else None
            notice_min = notice_min_raw.get("value") if isinstance(notice_min_raw, dict) else None
            if term_months_val is None or notice_min is None:
                continue

            if expiration is not None:
                deadline = expiration - timedelta(days=int(notice_min))
                description = f"Renewal notice window for option {index + 1}"
            else:
                deadline = None
                description = (
                    f"Renewal notice window for option {index + 1} "
                    f"[needs_review: expiration_date missing; notice_min_days={int(notice_min)}]"
                )

            obligations.append(
                Obligation(
                    lease_id=lease_id,
                    kind="renewal_notice",
                    deadline=deadline,
                    notice_window_days=int(notice_min),
                    description=description,
                    source_field_id=renewal_field.id,
                )
            )

    schedule_field = by_key.get("base_rent_schedule")
    if schedule_field and isinstance(schedule_field.value_json, list):
        for index, period in enumerate(schedule_field.value_json):
            if index == 0 or not isinstance(period, dict):
                continue
            period_start_raw = period.get("period_start", {})
            period_start = _parse_date(
                period_start_raw.get("value") if isinstance(period_start_raw, dict) else None
            )
            if period_start is None:
                continue
            obligations.append(
                Obligation(
                    lease_id=lease_id,
                    kind="rent_escalation",
                    deadline=period_start,
                    description=f"Rent escalation period {index + 1}",
                    source_field_id=schedule_field.id,
                )
            )

    termination_field = by_key.get("termination_option")
    if termination_field and isinstance(termination_field.value_json, dict):
        date_raw = termination_field.value_json.get("date", {})
        notice_raw = termination_field.value_json.get("notice_days", {})
        term_date = _parse_date(date_raw.get("value") if isinstance(date_raw, dict) else None)
        notice_days = notice_raw.get("value") if isinstance(notice_raw, dict) else None
        if term_date is not None:
            obligations.append(
                Obligation(
                    lease_id=lease_id,
                    kind="termination_option",
                    deadline=term_date,
                    notice_window_days=int(notice_days) if notice_days is not None else None,
                    description="Termination option deadline",
                    source_field_id=termination_field.id,
                )
            )

    for obligation in obligations:
        session.add(obligation)

    session.flush()
    return obligations


def persist_extraction(
    session: Session,
    document_id: uuid.UUID,
    lease_id: uuid.UUID,
    extraction: LeaseExtraction,
    context_truncated: bool,
    tokens_in: int,
    tokens_out: int,
    flagged: bool,
    needs_review_fields: set[str],
    scanned_pages: list[int],
    publisher: EventPublisher | None = None,
) -> ExtractionRun:
    """Write extraction run, fields, obligations; publish events."""
    event_publisher = publisher or PostgresEventPublisher(session)

    run = ExtractionRun(
        document_id=document_id,
        prompt_version=PROMPT_VERSION,
        model=settings.extraction_model,
        temperature=0.0,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        context_truncated=context_truncated,
        status=SUCCESS_STATUS,
    )
    session.add(run)
    session.flush()

    written = _write_extracted_fields(session, run, lease_id, extraction, needs_review_fields)
    session.flush()
    effective_count = consolidate(lease_id, session)
    logger.info(
        "persist consolidation: lease_id=%s run_id=%s written=%s effective=%s",
        lease_id,
        run.id,
        written,
        effective_count,
    )

    obligations = derive_obligations_for_lease(session, lease_id)

    event_publisher.publish(
        "extraction.completed",
        {
            "document_id": str(document_id),
            "lease_id": str(lease_id),
            "run_id": str(run.id),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "context_truncated": context_truncated,
        },
    )
    if flagged:
        flagged_payload: dict[str, Any] = {
            "document_id": str(document_id),
            "lease_id": str(lease_id),
            "run_id": str(run.id),
            "scanned_pages": scanned_pages,
        }
        event_publisher.publish("extraction.flagged", flagged_payload)
    for obligation in obligations:
        event_publisher.publish(
            "obligation.created",
            {
                "obligation_id": str(obligation.id),
                "lease_id": str(lease_id),
                "kind": obligation.kind,
                "deadline": obligation.deadline.isoformat() if obligation.deadline else None,
            },
        )

    session.flush()
    return run
