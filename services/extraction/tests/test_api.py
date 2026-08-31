"""API tests — auth, leases, events (mocked pipeline, no network)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent.schema import LeaseExtraction
from app.agent.serialization import lease_extraction_from_groups
from app.agent.pipeline import PipelineResult
from app.config import settings
from app.db.models import Event, ExtractedField, Lease
from app.main import app


def _minimal_extraction() -> LeaseExtraction:
    from app.agent.schema import ExtractedValue, Financial, Opex, OptionsObligations, PartiesPremises, Term

    empty = ExtractedValue(value=None, confidence=0.0, page=None, snippet=None)
    return lease_extraction_from_groups(
        parties_premises=PartiesPremises(
            landlord=ExtractedValue(value="ACME", confidence=0.9, page=1, snippet="ACME"),
            tenant=empty,
            premises_address=empty,
            rentable_sqft=empty,
        ),
        term=Term(
            commencement_date=empty,
            expiration_date=ExtractedValue(value=date(2030, 1, 1), confidence=0.9, page=2, snippet="2030"),
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


def test_protected_route_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/leases")
        assert response.status_code == 401


@pytest.mark.usefixtures("api_client")
class TestAuthAPI:
    def test_login_success(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/auth/login",
            json={"username": settings.demo_user, "password": settings.demo_password},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body

    def test_login_invalid_credentials(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/auth/login",
            json={"username": settings.demo_user, "password": "wrong-password"},
        )
        assert response.status_code == 401


@pytest.mark.usefixtures("api_client")
class TestLeaseAPI:
    def _auth_headers(self, api_client: TestClient) -> dict[str, str]:
        login = api_client.post(
            "/api/auth/login",
            json={"username": settings.demo_user, "password": settings.demo_password},
        )
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @patch("app.api.leases.run_extraction")
    @patch("app.api.leases.validate_upload_bytes")
    def test_upload_and_list_lease(
        self, mock_validate, mock_run_extraction, api_client: TestClient, db_session
    ) -> None:
        from app.agent.types import PageText
        from app.guardrails.context import GuardContext

        mock_validate.return_value = (
            [PageText(page=1, text="Extractable lease body text for guardrails.", char_count=60, maybe_scanned=False)],
            GuardContext(),
        )
        extraction = _minimal_extraction()
        mock_run_extraction.return_value = PipelineResult(
            extraction=extraction,
            run_id=None,
            tokens_in=100,
            tokens_out=50,
            cache_hit=False,
            flagged=False,
            context_truncated=False,
            needs_review_count=0,
            scanned_pages=[],
        )

        headers = self._auth_headers(api_client)
        pdf_bytes = b"%PDF-1.4 test content for upload"
        response = api_client.post(
            "/api/leases",
            headers=headers,
            data={"name": "Test Tower", "kind": "base"},
            files={"pdf": ("lease.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["tokens_in"] == 100

        list_response = api_client.get("/api/leases", headers=headers)
        assert list_response.status_code == 200
        leases = list_response.json()
        assert len(leases) == 1
        assert leases[0]["name"] == "Test Tower"
        assert leases[0]["landlord"] == "ACME"

    def test_get_lease_detail(self, api_client: TestClient, db_session) -> None:
        lease = Lease(name="Detail Lease", status="active")
        db_session.add(lease)
        db_session.flush()

        field = ExtractedField(
            run_id=None,
            lease_id=lease.id,
            field_key="landlord",
            value_json={"value": "Detail Landlord", "confidence": 0.9, "page": 1, "snippet": "x"},
            confidence=0.9,
            page=1,
            source_snippet="x",
            needs_review=False,
            effective=True,
        )
        # run_id required - create minimal run
        from app.db.models import Document, ExtractionRun

        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="a" * 64,
            filename="detail.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()
        run = ExtractionRun(
            document_id=document.id,
            prompt_version="v1.0",
            model=settings.extraction_model,
            status="completed",
        )
        db_session.add(run)
        db_session.flush()
        field.run_id = run.id
        db_session.add(field)
        db_session.commit()

        headers = self._auth_headers(api_client)
        response = api_client.get(f"/api/leases/{lease.id}", headers=headers)
        assert response.status_code == 200
        detail = response.json()
        assert detail["name"] == "Detail Lease"
        assert len(detail["fields"]["parties_premises"]) == 1

    def test_field_review_flow(self, api_client: TestClient, db_session) -> None:
        from app.db.models import Document, ExtractionRun

        lease = Lease(name="Review Lease", status="active")
        db_session.add(lease)
        db_session.flush()
        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="b" * 64,
            filename="review.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()
        run = ExtractionRun(
            document_id=document.id,
            prompt_version="v1.0",
            model=settings.extraction_model,
            status="completed",
        )
        db_session.add(run)
        db_session.flush()
        field = ExtractedField(
            run_id=run.id,
            lease_id=lease.id,
            field_key="tenant",
            value_json={"value": "Old Tenant", "confidence": 0.5, "page": 1, "snippet": "Old"},
            confidence=0.5,
            page=1,
            source_snippet="Old",
            needs_review=True,
            effective=True,
        )
        db_session.add(field)
        db_session.commit()

        headers = self._auth_headers(api_client)
        response = api_client.post(
            f"/api/fields/{field.id}/review",
            headers=headers,
            json={"accepted": True, "corrected_value": "New Tenant"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["field_key"] == "tenant"
        assert body["effective"] is True
        assert body["needs_review"] is False


@pytest.mark.usefixtures("api_client")
class TestEventsAPI:
    def test_list_events(self, api_client: TestClient, db_session) -> None:
        db_session.add(Event(type="lease.ingested", payload={"lease_id": "1"}))
        db_session.commit()

        login = api_client.post(
            "/api/auth/login",
            json={"username": settings.demo_user, "password": settings.demo_password},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = api_client.get("/api/events?limit=10", headers=headers)
        assert response.status_code == 200
        events = response.json()
        assert len(events) >= 1
        assert events[0]["type"] == "lease.ingested"
