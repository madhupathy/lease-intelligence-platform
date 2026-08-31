"""Integration tests for consolidator and idempotency (Postgres)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.agent.consolidator import consolidate
from app.agent.extractor import PROMPT_VERSION
from app.agent.persist import load_cached_extraction, persist_extraction
from app.agent.pipeline import run_extraction
from app.agent.schema import (
    ExtractedValue,
    Financial,
    LeaseExtraction,
    Opex,
    OptionsObligations,
    PartiesPremises,
    Term,
)
from app.agent.serialization import lease_extraction_from_groups
from app.agent.types import ExtractGroupResult
from app.config import settings
from app.db.models import Document, ExtractedField, ExtractionRun, Lease


def _minimal_extraction() -> LeaseExtraction:
    empty = ExtractedValue(value=None, confidence=0.0, page=None, snippet=None)
    return lease_extraction_from_groups(
        parties_premises=PartiesPremises(
            landlord=empty,
            tenant=empty,
            premises_address=empty,
            rentable_sqft=empty,
        ),
        term=Term(
            commencement_date=empty,
            expiration_date=ExtractedValue(
                value=date(2030, 1, 1),
                confidence=0.9,
                page=1,
                snippet="expires 2030",
            ),
            initial_term_months=empty,
        ),
        financial=Financial(
            base_rent_schedule=[],
            escalation_type=empty,
            escalation_value=empty,
            security_deposit=empty,
        ),
        options_obligations=OptionsObligations(
            renewal_options=[],
            termination_option=None,
            holdover_rate_pct=empty,
        ),
        opex=Opex(
            cam_structure=empty,
            base_year=empty,
            cam_cap_pct=empty,
            cam_cap_type=empty,
        ),
    )


@pytest.mark.usefixtures("db_session")
class TestConsolidatorAndIdempotency:
    def test_consolidator_latest_document_wins(self, db_session) -> None:
        lease = Lease(name="Amendment Lease", status="active")
        db_session.add(lease)
        db_session.flush()

        doc_old = Document(
            lease_id=lease.id,
            kind="base",
            sha256="c" * 64,
            filename="base.pdf",
            page_count=1,
        )
        doc_new = Document(
            lease_id=lease.id,
            kind="amendment",
            sha256="d" * 64,
            filename="amendment.pdf",
            page_count=1,
        )
        doc_old.uploaded_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        doc_new.uploaded_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        db_session.add_all([doc_old, doc_new])
        db_session.flush()

        run_old = ExtractionRun(
            document_id=doc_old.id,
            prompt_version=PROMPT_VERSION,
            model=settings.extraction_model,
            status="completed",
        )
        run_new = ExtractionRun(
            document_id=doc_new.id,
            prompt_version=PROMPT_VERSION,
            model=settings.extraction_model,
            status="completed",
        )
        db_session.add_all([run_old, run_new])
        db_session.flush()

        field_old = ExtractedField(
            run_id=run_old.id,
            lease_id=lease.id,
            field_key="landlord",
            value_json={"value": "Old Landlord", "confidence": 0.8},
            confidence=0.8,
            effective=False,
        )
        field_new = ExtractedField(
            run_id=run_new.id,
            lease_id=lease.id,
            field_key="landlord",
            value_json={"value": "New Landlord", "confidence": 0.9},
            confidence=0.9,
            effective=False,
        )
        db_session.add_all([field_old, field_new])
        db_session.flush()

        effective_count = consolidate(lease.id, db_session)
        db_session.commit()

        assert effective_count == 1
        refreshed_old = db_session.get(ExtractedField, field_old.id)
        refreshed_new = db_session.get(ExtractedField, field_new.id)
        assert refreshed_old is not None and refreshed_old.effective is False
        assert refreshed_new is not None and refreshed_new.effective is True

    def test_load_cached_extraction_short_circuits(self, db_session) -> None:
        lease = Lease(name="Cache Lease", status="active")
        db_session.add(lease)
        db_session.flush()

        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="e" * 64,
            filename="cache.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()

        extraction = _minimal_extraction()
        persist_extraction(
            session=db_session,
            document_id=document.id,
            lease_id=lease.id,
            extraction=extraction,
            context_truncated=False,
            tokens_in=100,
            tokens_out=50,
            flagged=False,
            needs_review_fields=set(),
            scanned_pages=[],
        )
        db_session.commit()

        cached = load_cached_extraction(db_session, document.id)
        assert cached is not None
        assert cached.term.expiration_date.value == date(2030, 1, 1)

    @patch("app.agent.pipeline.extract_group")
    def test_run_extraction_cache_hit_skips_llm(self, mock_extract_group, db_session, tmp_path) -> None:
        from app.storage import pdf_path_for_sha256

        sha256 = "f" * 64
        pdf_path = pdf_path_for_sha256(sha256)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4 minimal")

        lease = Lease(name="Pipeline Cache", status="active")
        db_session.add(lease)
        db_session.flush()
        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256=sha256,
            filename="sample.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.commit()

        extraction = _minimal_extraction()
        persist_extraction(
            session=db_session,
            document_id=document.id,
            lease_id=lease.id,
            extraction=extraction,
            context_truncated=False,
            tokens_in=10,
            tokens_out=5,
            flagged=False,
            needs_review_fields=set(),
            scanned_pages=[],
        )
        db_session.commit()

        result = run_extraction(document.id, db_session)
        assert result.cache_hit is True
        assert result.tokens_in == 0
        assert result.tokens_out == 0
        mock_extract_group.assert_not_called()
