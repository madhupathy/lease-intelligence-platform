"""Persist → detail-query round-trip for extracted fields."""

from __future__ import annotations

from datetime import date

import pytest

from app.agent.persist import persist_extraction
from app.agent.schema import (
    ExtractedValue,
    Financial,
    Opex,
    OptionsObligations,
    PartiesPremises,
    Term,
)
from app.agent.serialization import lease_extraction_from_groups
from app.api.leases import _group_fields, load_effective_fields
from app.db.models import Document, Lease
from app.field_groups import FIELD_GROUPS


def _mixed_extraction():
    empty = ExtractedValue(value=None, confidence=0.0, page=None, snippet=None)
    return lease_extraction_from_groups(
        parties_premises=PartiesPremises(
            landlord=ExtractedValue(value="ACME LLC", confidence=0.95, page=1, snippet="Landlord: ACME"),
            tenant=ExtractedValue(value="Beta Inc", confidence=0.9, page=1, snippet="Tenant: Beta"),
            premises_address=empty,
            rentable_sqft=empty,
        ),
        term=Term(
            commencement_date=ExtractedValue(
                value=date(2024, 1, 1), confidence=0.9, page=2, snippet="Commencement"
            ),
            expiration_date=empty,
            initial_term_months=empty,
        ),
        financial=Financial(
            base_rent_schedule=[],
            escalation_type=empty,
            escalation_value=empty,
            security_deposit=ExtractedValue(
                value=100000.0, confidence=0.85, page=5, snippet="Deposit $100,000"
            ),
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
class TestPersistDetailRoundTrip:
    def test_persist_then_detail_query_returns_all_schema_fields(self, db_session) -> None:
        lease = Lease(name="Persist Round Trip", status="active")
        db_session.add(lease)
        db_session.flush()
        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="b" * 64,
            filename="roundtrip.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()

        extraction = _mixed_extraction()
        run = persist_extraction(
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

        effective = load_effective_fields(db_session, lease.id)
        assert len(effective) == sum(len(keys) for keys in FIELD_GROUPS.values())
        assert all(field.effective for field in effective)
        assert all(field.lease_id == lease.id for field in effective)
        assert all(field.run_id == run.id for field in effective)

        grouped = _group_fields(effective)
        expected_keys = {key for keys in FIELD_GROUPS.values() for key in keys}
        returned_keys = {
            item.field_key
            for group in (
                grouped.parties_premises,
                grouped.term,
                grouped.financial,
                grouped.options_obligations,
                grouped.opex,
            )
            for item in group
        }
        assert returned_keys == expected_keys

        by_key = {field.field_key: field for field in effective}
        assert by_key["landlord"].value_json["value"] == "ACME LLC"
        assert by_key["premises_address"].value_json["value"] is None
        assert by_key["premises_address"].needs_review is True
        assert by_key["security_deposit"].value_json["value"] == 100000.0
        assert by_key["termination_option"].value_json is None
        assert by_key["base_rent_schedule"].value_json == []
