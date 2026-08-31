"""Integration tests for the Postgres schema (AGENTS.md §5)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Document, ExtractedField, ExtractionRun, Lease


@pytest.mark.usefixtures("db_session")
class TestExtractionSchema:
    def test_lease_document_run_field_chain(self, db_session) -> None:
        lease = Lease(name="Midtown Tower Lease")
        db_session.add(lease)
        db_session.flush()

        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="a" * 64,
            filename="midtown-tower.pdf",
            page_count=42,
        )
        db_session.add(document)
        db_session.flush()

        run = ExtractionRun(
            document_id=document.id,
            prompt_version="parties_premises_v1.0",
            model="claude-sonnet-4-6",
            temperature=0.0,
            tokens_in=1200,
            tokens_out=400,
            context_truncated=False,
            status="completed",
        )
        db_session.add(run)
        db_session.flush()

        field = ExtractedField(
            run_id=run.id,
            lease_id=lease.id,
            field_key="landlord",
            value_json={"value": "ACME Properties LLC"},
            confidence=0.92,
            page=3,
            source_snippet="Landlord: ACME Properties LLC",
            needs_review=False,
            effective=True,
        )
        db_session.add(field)
        db_session.flush()

        fetched = db_session.scalar(
            select(ExtractedField).where(ExtractedField.id == field.id)
        )
        assert fetched is not None
        assert fetched.run_id == run.id
        assert fetched.lease_id == lease.id
        assert fetched.field_key == "landlord"
        assert fetched.value_json == {"value": "ACME Properties LLC"}
        assert float(fetched.confidence) == 0.92
        assert fetched.page == 3
        assert fetched.effective is True

        run_loaded = db_session.get(ExtractionRun, run.id)
        assert run_loaded is not None
        assert run_loaded.document_id == document.id
        assert len(run_loaded.extracted_fields) == 1

    def test_extraction_run_idempotency_rejects_duplicate(self, db_session) -> None:
        lease = Lease(name="Duplicate Run Lease")
        db_session.add(lease)
        db_session.flush()

        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="b" * 64,
            filename="duplicate.pdf",
            page_count=10,
        )
        db_session.add(document)
        db_session.flush()

        first_run = ExtractionRun(
            document_id=document.id,
            prompt_version="financial_v1.0",
            model="claude-sonnet-4-6",
            status="completed",
        )
        db_session.add(first_run)
        db_session.flush()

        duplicate_run = ExtractionRun(
            document_id=document.id,
            prompt_version="financial_v1.0",
            model="claude-sonnet-4-6",
            status="pending",
        )
        db_session.add(duplicate_run)

        with pytest.raises(IntegrityError):
            db_session.flush()
