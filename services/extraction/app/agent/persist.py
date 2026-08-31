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
from app.agent.serialization import flatten_lease_extraction, lease_extraction_from_field_rows
from app.agent.schema import LeaseExtraction
from app.config import settings
from app.db.models import Document, ExtractedField, ExtractionRun, Obligation
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


def _write_extracted_fields(
    session: Session,
    run: ExtractionRun,
    lease_id: uuid.UUID,
    extraction: LeaseExtraction,
    needs_review_fields: set[str],
) -> None:
    flat = flatten_lease_extraction(extraction)
    for field_key, raw in flat.items():
        confidence = _confidence_for_value(raw) if isinstance(raw, dict) else 0.0
        page = _page_for_value(raw) if isinstance(raw, dict) else None
        snippet = _snippet_for_value(raw) if isinstance(raw, dict) else None
        needs_review = field_key in needs_review_fields or confidence < settings.review_threshold

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
    if renewal_field and expiration is not None and isinstance(renewal_field.value_json, list):
        for index, option in enumerate(renewal_field.value_json):
            notice_min_raw = option.get("notice_min_days", {})
            notice_min = notice_min_raw.get("value")
            if notice_min is None:
                continue
            deadline = expiration - timedelta(days=int(notice_min))
            obligations.append(
                Obligation(
                    lease_id=lease_id,
                    kind="renewal_notice",
                    deadline=deadline,
                    notice_window_days=int(notice_min),
                    description=f"Renewal notice window for option {index + 1}",
                    source_field_id=renewal_field.id,
                )
            )

    schedule_field = by_key.get("base_rent_schedule")
    if schedule_field and isinstance(schedule_field.value_json, list):
        for index, period in enumerate(schedule_field.value_json):
            if index == 0:
                continue
            period_start = _parse_date(period.get("period_start", {}).get("value"))
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
        term_date = _parse_date(termination_field.value_json.get("date", {}).get("value"))
        notice_days = termination_field.value_json.get("notice_days", {}).get("value")
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

    _write_extracted_fields(session, run, lease_id, extraction, needs_review_fields)
    consolidate(lease_id, session)

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
