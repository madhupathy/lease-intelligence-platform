"""Obligation derivation from effective extracted fields."""

from __future__ import annotations

from datetime import date

import pytest

from app.agent.persist import aggregate_list_confidence, derive_obligations_for_lease
from app.db.models import Document, ExtractedField, ExtractionRun, Lease, Obligation


@pytest.mark.usefixtures("db_session")
class TestObligationDerivation:
    def test_renewal_notice_from_renewal_options_row(self, db_session) -> None:
        lease = Lease(name="CrowdStrike-like", status="active")
        db_session.add(lease)
        db_session.flush()
        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="c" * 64,
            filename="crowdstrike.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()
        run = ExtractionRun(
            document_id=document.id,
            prompt_version="v1.0",
            model="test-model",
            status="completed",
        )
        db_session.add(run)
        db_session.flush()

        expiration = ExtractedField(
            run_id=run.id,
            lease_id=lease.id,
            field_key="expiration_date",
            value_json={
                "value": "2030-12-31",
                "confidence": 0.9,
                "page": 3,
                "snippet": "expires December 31, 2030",
            },
            confidence=0.9,
            effective=True,
        )
        renewals = ExtractedField(
            run_id=run.id,
            lease_id=lease.id,
            field_key="renewal_options",
            value_json=[
                {
                    "term_months": {"value": 60, "confidence": 0.88, "page": 10, "snippet": "five years"},
                    "notice_min_days": {
                        "value": 365,
                        "confidence": 0.87,
                        "page": 10,
                        "snippet": "365 days",
                    },
                    "notice_max_days": {"value": None, "confidence": 0.0, "page": None, "snippet": None},
                    "rent_basis": {"value": "FMV", "confidence": 0.8, "page": 10, "snippet": "FMV"},
                }
            ],
            confidence=aggregate_list_confidence(
                [
                    {
                        "term_months": {"value": 60, "confidence": 0.88},
                        "notice_min_days": {"value": 365, "confidence": 0.87},
                    }
                ]
            ),
            effective=True,
        )
        db_session.add_all([expiration, renewals])
        db_session.flush()

        obligations = derive_obligations_for_lease(db_session, lease.id)
        db_session.commit()

        renewal_notices = [o for o in obligations if o.kind == "renewal_notice"]
        assert len(renewal_notices) == 1
        assert renewal_notices[0].notice_window_days == 365
        assert renewal_notices[0].deadline == date(2029, 12, 31)

        expirations = [o for o in obligations if o.kind == "expiration"]
        assert len(expirations) == 1

    def test_renewal_notice_without_expiration_still_created(self, db_session) -> None:
        lease = Lease(name="No Expiration", status="active")
        db_session.add(lease)
        db_session.flush()
        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="d" * 64,
            filename="partial.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()
        run = ExtractionRun(
            document_id=document.id,
            prompt_version="v1.0",
            model="test-model",
            status="completed",
        )
        db_session.add(run)
        db_session.flush()

        renewals = ExtractedField(
            run_id=run.id,
            lease_id=lease.id,
            field_key="renewal_options",
            value_json=[
                {
                    "term_months": {"value": 60, "confidence": 0.9, "page": 1, "snippet": "60 months"},
                    "notice_min_days": {"value": 365, "confidence": 0.9, "page": 1, "snippet": "365"},
                    "notice_max_days": {"value": None, "confidence": 0.0, "page": None, "snippet": None},
                    "rent_basis": {"value": None, "confidence": 0.0, "page": None, "snippet": None},
                }
            ],
            confidence=0.9,
            effective=True,
        )
        db_session.add(renewals)
        db_session.flush()

        obligations = derive_obligations_for_lease(db_session, lease.id)
        renewal_notices = [o for o in obligations if o.kind == "renewal_notice"]
        assert len(renewal_notices) == 1
        assert renewal_notices[0].deadline is None
        assert renewal_notices[0].notice_window_days == 365
        assert "needs_review" in (renewal_notices[0].description or "")


def test_aggregate_list_confidence_mean() -> None:
    rows = [
        {
            "period_start": {"value": "2024-01-01", "confidence": 0.8},
            "period_end": {"value": "2024-12-31", "confidence": 0.6},
            "annual_rent": {"value": 100.0, "confidence": 1.0},
            "monthly_rent": {"value": 10.0, "confidence": 0.6},
        }
    ]
    assert aggregate_list_confidence(rows) == pytest.approx(0.75)
    assert aggregate_list_confidence([]) == 0.0
