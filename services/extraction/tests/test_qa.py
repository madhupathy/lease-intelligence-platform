"""Retrieval and Q&A service tests (no network)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.agent.embeddings import EMBEDDING_DIMENSION
from app.qa.retrieval import RetrievedChunk, retrieve_chunks
from app.qa.service import NOT_FOUND_ANSWER, QACitation, answer_lease_question, verify_citations


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            seed = sum(ord(c) for c in text) % 1000
            vectors.append([float(seed)] * EMBEDDING_DIMENSION)
        return vectors


@pytest.mark.usefixtures("db_session")
class TestRetrieval:
    def test_retrieve_chunks_with_fake_embeddings(self, db_session) -> None:
        from app.db.models import Document, Lease, LeaseChunk

        lease = Lease(name="QA Lease", status="active")
        db_session.add(lease)
        db_session.flush()
        document = Document(
            lease_id=lease.id,
            kind="base",
            sha256="g" * 64,
            filename="qa.pdf",
            page_count=1,
        )
        db_session.add(document)
        db_session.flush()

        db_session.add(
            LeaseChunk(
                lease_id=lease.id,
                document_id=document.id,
                page=1,
                section_tag="base_rent",
                text="Tenant pays base rent of fifty thousand dollars monthly.",
                text_sha256="abc",
                embedding_model="test",
                embedding=[1.0] * EMBEDDING_DIMENSION,
            )
        )
        db_session.commit()

        chunks = retrieve_chunks(
            db_session,
            lease.id,
            "base rent monthly",
            top_k=3,
            embeddings=FakeEmbeddings(),
        )
        assert len(chunks) == 1
        assert "base rent" in chunks[0].text.lower()


class TestQAService:
    def test_verify_citations_only_from_chunks(self) -> None:
        chunks = [
            RetrievedChunk(
                id=uuid.uuid4(),
                text="Tenant pays base rent monthly.",
                page=1,
                section_tag="base_rent",
                similarity=0.9,
            )
        ]
        good = verify_citations(
            [QACitation(page=1, section_tag="base_rent", snippet="base rent monthly")],
            chunks,
        )
        assert len(good) == 1

        bad = verify_citations(
            [QACitation(page=2, section_tag="term", snippet="not in chunk")],
            chunks,
        )
        assert bad == []

    @patch("app.qa.service.build_chat_anthropic")
    def test_low_similarity_returns_not_found_without_llm(self, mock_chat, db_session) -> None:
        from app.db.models import Lease

        lease = Lease(name="Low Sim", status="active")
        db_session.add(lease)
        db_session.commit()

        with patch("app.qa.service.retrieve_chunks", return_value=[]):
            result = answer_lease_question(
                db_session,
                lease.id,
                "unrelated question",
                embeddings=FakeEmbeddings(),
            )
        assert result.answer == NOT_FOUND_ANSWER
        mock_chat.assert_not_called()

    @patch("app.qa.service.build_chat_anthropic")
    def test_qa_with_mocked_llm(self, mock_chat, db_session) -> None:
        from app.db.models import Lease

        lease = Lease(name="QA", status="active")
        db_session.add(lease)
        db_session.commit()

        chunk = RetrievedChunk(
            id=uuid.uuid4(),
            text="Tenant pays base rent of fifty thousand dollars monthly.",
            page=4,
            section_tag="base_rent",
            similarity=0.95,
        )
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = MagicMock(
            content='{"answer":"Base rent is $50,000 monthly.","citations":[{"page":4,"section_tag":"base_rent","snippet":"base rent of fifty thousand dollars monthly"}]}'
        )
        mock_chat.return_value = mock_instance

        with patch("app.qa.service.retrieve_chunks", return_value=[chunk]):
            result = answer_lease_question(
                db_session,
                lease.id,
                "What is the base rent?",
                embeddings=FakeEmbeddings(),
                llm=mock_instance,
            )

        assert "50,000" in result.answer
        assert len(result.citations) == 1
        assert result.citations[0].page == 4

    @patch("app.qa.service.build_chat_anthropic")
    def test_unparseable_llm_response_flags_and_returns_raw(self, mock_chat, db_session) -> None:
        from app.db.models import Event, Lease

        lease = Lease(name="Unparseable", status="active")
        db_session.add(lease)
        db_session.commit()

        chunk = RetrievedChunk(
            id=uuid.uuid4(),
            text="Tenant pays base rent monthly.",
            page=1,
            section_tag="base_rent",
            similarity=0.95,
        )
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = MagicMock(content="not valid json at all")
        mock_chat.return_value = mock_instance

        with patch("app.qa.service.retrieve_chunks", return_value=[chunk]):
            result = answer_lease_question(
                db_session,
                lease.id,
                "What is rent?",
                embeddings=FakeEmbeddings(),
                llm=mock_instance,
            )

        assert result.answer == "not valid json at all"
        assert result.flagged is True
        flagged = db_session.scalars(
            select(Event).where(Event.type == "extraction.flagged")
        ).all()
        assert any(e.payload.get("reason") == "qa_unparseable" for e in flagged)
