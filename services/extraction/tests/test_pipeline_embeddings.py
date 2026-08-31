"""Pipeline resilience when embeddings are unavailable."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

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
from app.db.models import Document, ExtractedField, Lease, LeaseChunk


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


def _extract_side_effect(extraction: LeaseExtraction):
    models = {
        "parties_premises": extraction.parties_premises,
        "term": extraction.term,
        "financial": extraction.financial,
        "options_obligations": extraction.options_obligations,
        "opex": extraction.opex,
    }

    def _extract(group_name: str, context: str, llm=None) -> ExtractGroupResult:
        return ExtractGroupResult(
            group_name=group_name,
            model=models[group_name],
            tokens_in=10,
            tokens_out=5,
        )

    return _extract


class InsufficientQuotaError(Exception):
    status_code = 429

    def __str__(self) -> str:
        return "Error code: 429 - insufficient_quota"


@pytest.mark.usefixtures("db_session")
class TestPipelineEmbeddingResilience:
    @patch("app.agent.pipeline.extract_group")
    @patch("app.agent.chunk_store.embed_texts")
    def test_run_extraction_persists_fields_when_embed_raises_429(
        self,
        mock_embed_texts,
        mock_extract_group,
        db_session,
        tmp_path,
    ) -> None:
        from app.storage import pdf_path_for_sha256

        sha256 = "a" * 64
        pdf_path = pdf_path_for_sha256(sha256)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4 minimal")

        lease = Lease(name="Embedding Skip", status="active")
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
        mock_extract_group.side_effect = _extract_side_effect(extraction)
        mock_embed_texts.side_effect = InsufficientQuotaError()

        result = run_extraction(document.id, db_session)
        db_session.commit()

        assert result.cache_hit is False
        assert result.run_id is not None

        field_count = db_session.scalar(
            select(func.count()).select_from(ExtractedField).where(
                ExtractedField.run_id == result.run_id
            )
        )
        assert field_count is not None and field_count > 0

        chunk_count = db_session.scalar(
            select(func.count()).select_from(LeaseChunk).where(
                LeaseChunk.document_id == document.id
            )
        )
        assert chunk_count == 0
