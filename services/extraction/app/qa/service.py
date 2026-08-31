"""Lease Q&A service — retrieval-augmented generation (AGENTS.md §9)."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.agent.prompts import render_prompt_template
from app.config import settings
from app.events import PostgresEventPublisher
from app.qa.retrieval import RetrievedChunk, retrieve_chunks

logger = logging.getLogger(__name__)

NOT_FOUND_ANSWER = "Not found in this lease's documents."
QA_TEMPLATE = "qa_v1.0.md.j2"


@dataclass
class QACitation:
    page: int | None
    section_tag: str | None
    snippet: str


@dataclass
class QAResult:
    answer: str
    citations: list[QACitation]
    retrieved_chunk_ids: list[str]
    flagged: bool


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        tag = chunk.section_tag or "general"
        page = chunk.page if chunk.page is not None else "?"
        blocks.append(f"[Chunk {index} | page {page} | section {tag}]\n{chunk.text}")
    return "\n\n".join(blocks)


def _parse_llm_response(raw: str) -> tuple[str, list[QACitation], bool]:
    try:
        payload = json.loads(raw)
        answer = str(payload.get("answer", NOT_FOUND_ANSWER))
        citations_raw = payload.get("citations", [])
        citations: list[QACitation] = []
        for item in citations_raw:
            citations.append(
                QACitation(
                    page=item.get("page"),
                    section_tag=item.get("section_tag"),
                    snippet=str(item.get("snippet", ""))[:300],
                )
            )
        return answer, citations, True
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw.strip(), [], False


def verify_citations(citations: list[QACitation], chunks: list[RetrievedChunk]) -> list[QACitation]:
    """CitationGuard-style check: snippet must appear in a retrieved chunk."""
    chunk_texts = [_normalize_whitespace(chunk.text) for chunk in chunks]
    verified: list[QACitation] = []
    for citation in citations:
        snippet = _normalize_whitespace(citation.snippet)
        if not snippet:
            continue
        if any(snippet in chunk_text for chunk_text in chunk_texts):
            verified.append(citation)
    return verified


def answer_lease_question(
    session: Session,
    lease_id: uuid.UUID,
    question: str,
    history: list[dict[str, str]] | None = None,
    llm: BaseChatModel | None = None,
    embeddings: Embeddings | None = None,
) -> QAResult:
    """RAG Q&A with similarity gate and citation verification."""
    chunks = retrieve_chunks(session, lease_id, question, embeddings=embeddings)
    retrieved_ids = [str(chunk.id) for chunk in chunks]

    if not chunks or chunks[0].similarity < settings.qa_min_similarity:
        PostgresEventPublisher(session).publish(
            "extraction.flagged",
            {
                "lease_id": str(lease_id),
                "reason": "qa_low_similarity",
                "top_similarity": chunks[0].similarity if chunks else 0.0,
            },
        )
        session.flush()
        return QAResult(
            answer=NOT_FOUND_ANSWER,
            citations=[],
            retrieved_chunk_ids=retrieved_ids,
            flagged=True,
        )

    context = _build_context(chunks)
    prompt = render_prompt_template(QA_TEMPLATE, context)
    messages: list[Any] = [SystemMessage(content=prompt)]

    for turn in (history or [])[-settings.qa_history_max_turns:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))

    messages.append(HumanMessage(content=question))

    chat_model = llm or ChatAnthropic(
        model=settings.extraction_model,
        temperature=0,
        api_key=settings.anthropic_api_key or None,
    )
    response = chat_model.invoke(messages)
    raw_content = response.content if isinstance(response.content, str) else str(response.content)
    answer, citations, parsed_ok = _parse_llm_response(raw_content)
    flagged = False
    if not parsed_ok:
        PostgresEventPublisher(session).publish(
            "extraction.flagged",
            {"lease_id": str(lease_id), "reason": "qa_unparseable"},
        )
        session.flush()
        flagged = True
    verified = verify_citations(citations, chunks)

    if answer != NOT_FOUND_ANSWER and not verified and citations:
        answer = NOT_FOUND_ANSWER

    return QAResult(
        answer=answer,
        citations=verified,
        retrieved_chunk_ids=retrieved_ids,
        flagged=flagged,
    )
