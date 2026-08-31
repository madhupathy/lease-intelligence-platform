"""Persist lease chunks + embeddings with content-hash cache."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.chunker import ChunkDraft
from app.agent.embeddings import embed_texts
from app.config import settings
from app.db.models import LeaseChunk
from langchain_core.embeddings import Embeddings


def persist_chunks(
    session: Session,
    lease_id: uuid.UUID,
    document_id: uuid.UUID,
    drafts: list[ChunkDraft],
    embeddings: Embeddings | None = None,
) -> int:
    """Store section-aware chunks; skip rows already embedded for text_sha256+model."""
    embedding_model = settings.embedding_model
    pending: list[ChunkDraft] = []

    for draft in drafts:
        existing = session.scalar(
            select(LeaseChunk.id).where(
                LeaseChunk.document_id == document_id,
                LeaseChunk.text_sha256 == draft.text_sha256,
                LeaseChunk.embedding_model == embedding_model,
                LeaseChunk.embedding.is_not(None),
            )
        )
        if existing is not None:
            continue
        pending.append(draft)

    if not pending:
        return 0

    vectors = embed_texts([draft.text for draft in pending], embeddings=embeddings)
    for draft, vector in zip(pending, vectors, strict=True):
        session.add(
            LeaseChunk(
                lease_id=lease_id,
                document_id=document_id,
                page=draft.page,
                section_tag=draft.section_tag,
                text=draft.text,
                text_sha256=draft.text_sha256,
                embedding_model=embedding_model,
                embedding=vector,
            )
        )

    session.flush()
    return len(pending)
