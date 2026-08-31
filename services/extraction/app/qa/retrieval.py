"""Vector retrieval over lease_chunks (AGENTS.md §9 level 2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.embeddings import embed_texts
from app.config import settings
from app.db.models import LeaseChunk
from langchain_core.embeddings import Embeddings


@dataclass(frozen=True)
class RetrievedChunk:
    id: uuid.UUID
    text: str
    page: int | None
    section_tag: str | None
    similarity: float


def retrieve_chunks(
    session: Session,
    lease_id: uuid.UUID,
    question: str,
    top_k: int | None = None,
    embeddings: Embeddings | None = None,
) -> list[RetrievedChunk]:
    """Cosine similarity search filtered by lease_id."""
    limit = top_k if top_k is not None else settings.qa_top_k
    query_vector = embed_texts([question], embeddings=embeddings)[0]

    distance_expr = LeaseChunk.embedding.cosine_distance(query_vector)
    rows = session.execute(
        select(LeaseChunk, distance_expr.label("distance"))
        .where(
            LeaseChunk.lease_id == lease_id,
            LeaseChunk.embedding.is_not(None),
        )
        .order_by(distance_expr)
        .limit(limit)
    ).all()

    results: list[RetrievedChunk] = []
    for chunk, distance in rows:
        similarity = 1.0 - float(distance)
        results.append(
            RetrievedChunk(
                id=chunk.id,
                text=chunk.text,
                page=chunk.page,
                section_tag=chunk.section_tag,
                similarity=similarity,
            )
        )
    return results
