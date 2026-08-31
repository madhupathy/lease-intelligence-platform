"""API tests for lease Q&A endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.qa.service import QACitation, QAResult


@pytest.mark.usefixtures("api_client")
class TestLeaseQAAPI:
    def _auth_headers(self, api_client: TestClient) -> dict[str, str]:
        from app.config import settings

        login = api_client.post(
            "/api/auth/login",
            json={"username": settings.demo_user, "password": settings.demo_password},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    @patch("app.qa.service.answer_lease_question")
    def test_qa_endpoint_returns_citations(self, mock_answer, api_client: TestClient, db_session) -> None:
        from app.db.models import Lease

        lease = Lease(name="QA API Lease", status="active")
        db_session.add(lease)
        db_session.commit()

        mock_answer.return_value = QAResult(
            answer="Base rent is $50,000 monthly.",
            citations=[QACitation(page=2, section_tag="base_rent", snippet="base rent monthly")],
            retrieved_chunk_ids=["chunk-1"],
            flagged=False,
        )

        headers = self._auth_headers(api_client)
        response = api_client.post(
            f"/api/leases/{lease.id}/qa",
            headers=headers,
            json={"question": "What is base rent?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "50,000" in body["answer"]
        assert body["citations"][0]["page"] == 2
        assert body["retrieved_chunk_ids"] == ["chunk-1"]
