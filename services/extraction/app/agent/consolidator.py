"""Stage 6 — consolidator: amendment consolidation (AGENTS.md §7)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, ExtractedField, ExtractionRun


def consolidate(lease_id: uuid.UUID, session: Session) -> int:
    """Latest-document-wins per field_key; rewrite effective flags; never delete rows.

    Fields are loaded by run_id query (not the relationship collection) so newly
    added ExtractedField rows are visible even before the relationship is refreshed.
    """
    session.flush()

    documents = session.scalars(
        select(Document)
        .where(Document.lease_id == lease_id)
        .order_by(Document.uploaded_at.asc())
    ).all()

    winners: dict[str, ExtractedField] = {}

    for document in documents:
        run = session.scalar(
            select(ExtractionRun)
            .where(
                ExtractionRun.document_id == document.id,
                ExtractionRun.status == "completed",
            )
            .order_by(ExtractionRun.created_at.desc())
        )
        if run is None:
            continue

        run_fields = session.scalars(
            select(ExtractedField).where(ExtractedField.run_id == run.id)
        ).all()
        for field in run_fields:
            winners[field.field_key] = field

    all_fields = session.scalars(
        select(ExtractedField).where(ExtractedField.lease_id == lease_id)
    ).all()

    effective_count = 0
    for field in all_fields:
        winner = winners.get(field.field_key)
        field.effective = winner is not None and field.id == winner.id
        if field.effective:
            effective_count += 1

    session.flush()
    return effective_count
