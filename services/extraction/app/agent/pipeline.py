"""Extraction pipeline orchestration + CLI (AGENTS.md §7)."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.chunker import chunk_sectioned_pages
from app.agent.chunk_store import persist_chunks
from app.agent.extractor import GROUP_MODELS, extract_group
from app.agent.loader import load_pages
from app.agent.matrix import load_field_matrix
from app.agent.persist import load_cached_run, persist_extraction
from app.agent.router import route
from app.agent.sectioner import tag_sections
from app.agent.serialization import lease_extraction_from_groups
from app.config import get_input_guardrails, get_output_guardrails, settings
from app.db.models import Document, Lease
from app.db.session import SessionLocal
from app.events import PostgresEventPublisher
from app.guardrails.context import GuardContext
from app.guardrails.runner import run_guardrails
from app.agent.types import PageText
from app.storage import resolve_document_path, save_pdf_bytes

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    extraction: object
    run_id: uuid.UUID | None
    tokens_in: int
    tokens_out: int
    cache_hit: bool
    flagged: bool
    context_truncated: bool
    needs_review_count: int
    scanned_pages: list[int]


def validate_upload_bytes(content: bytes, filename: str) -> tuple[list[PageText], GuardContext]:
    """Run input guardrails on upload bytes before persisting anything."""
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise ValueError("Only PDF files are accepted")
    if len(content) > settings.max_upload_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_bytes} bytes")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        pages = load_pages(tmp_path)
        input_ctx = GuardContext(file_path=tmp_path, pages=pages)
        input_result = run_guardrails(get_input_guardrails(), input_ctx)
        if input_result.verdict.value == "block":
            raise ValueError(f"Input guardrail blocked upload: {input_result.reason}")
        return pages, input_ctx
    finally:
        tmp_path.unlink(missing_ok=True)


def create_document_for_upload(
    session: Session,
    content: bytes,
    filename: str,
    name: str,
    kind: str,
    lease_id: uuid.UUID | None,
    page_count: int,
) -> tuple[Document, bool]:
    """Save PDF to storage and create lease/document rows.

    Returns (document, deduplicated). When deduplicated is True the sha256 already existed.
    """
    sha256, _ = save_pdf_bytes(content)
    existing = session.scalar(select(Document).where(Document.sha256 == sha256))
    if existing is not None:
        return existing, True

    if lease_id is not None:
        lease = session.get(Lease, lease_id)
        if lease is None:
            raise ValueError(f"Lease not found: {lease_id}")
    else:
        lease = Lease(name=name, status="active")
        session.add(lease)
        session.flush()

    document = Document(
        lease_id=lease.id,
        kind=kind,
        sha256=sha256,
        filename=filename,
        page_count=page_count,
    )
    session.add(document)
    session.flush()

    publisher = PostgresEventPublisher(session)
    publisher.publish(
        "lease.ingested",
        {
            "lease_id": str(lease.id),
            "document_id": str(document.id),
            "filename": document.filename,
            "sha256": document.sha256,
        },
    )
    session.flush()
    return document, False


def ingest_pdf(pdf_path: Path, session: Session, name: str | None = None) -> Document:
    """CLI helper: read PDF from path, store by hash, create lease/document."""
    content = pdf_path.read_bytes()
    pages, _ = validate_upload_bytes(content, pdf_path.name)
    return create_document_for_upload(
        session=session,
        content=content,
        filename=pdf_path.name,
        name=name or pdf_path.stem,
        kind="base",
        lease_id=None,
        page_count=len(pages),
    )[0]


def run_extraction(
    document_id: uuid.UUID,
    session: Session,
    llm: BaseChatModel | None = None,
) -> PipelineResult:
    """Orchestrate loader → sectioner → router → budget → extractor → guardrails → persist."""
    document = session.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document not found: {document_id}")

    cached = load_cached_run(session, document_id)
    if cached is not None:
        run, extraction = cached
        needs_review_count = sum(1 for field in run.extracted_fields if field.needs_review)
        return PipelineResult(
            extraction=extraction,
            run_id=run.id,
            tokens_in=run.tokens_in or 0,
            tokens_out=run.tokens_out or 0,
            cache_hit=True,
            flagged=False,
            context_truncated=run.context_truncated,
            needs_review_count=needs_review_count,
            scanned_pages=[],
        )

    pdf_path = resolve_document_path(document.sha256)
    pages = load_pages(pdf_path)
    scanned_pages = [page.page for page in pages if page.maybe_scanned]

    input_ctx = GuardContext(file_path=pdf_path, pages=pages)
    input_result = run_guardrails(get_input_guardrails(), input_ctx)
    if input_result.verdict.value == "block":
        raise ValueError(f"Input guardrail blocked extraction: {input_result.reason}")

    flagged = bool(input_ctx.flags) or bool(scanned_pages)
    sectioned = tag_sections(pages, load_field_matrix())
    chunk_drafts = chunk_sectioned_pages(sectioned)
    persist_chunks(session, document.lease_id, document.id, chunk_drafts)
    page_texts = {page.page: page.text for page in pages}

    group_models: dict[str, object] = {}
    tokens_in = 0
    tokens_out = 0
    context_truncated = False
    needs_review_fields: set[str] = set()

    for group_name in GROUP_MODELS:
        blocks = route(sectioned, group_name)
        budget = enforce_budget(blocks, all_pages=pages)
        context_truncated = context_truncated or budget.truncated

        extract_result = extract_group(group_name, budget.context, llm=llm)
        tokens_in += extract_result.tokens_in
        tokens_out += extract_result.tokens_out

        output_ctx = GuardContext(
            group_name=group_name,
            group_model=extract_result.model,
            page_texts=page_texts,
        )
        output_result = run_guardrails(get_output_guardrails(), output_ctx)
        if output_ctx.flags:
            flagged = True
        needs_review_fields.update(output_ctx.needs_review_fields)
        if output_result.verdict.value == "block":
            flagged = True

        group_models[group_name] = extract_result.model

    extraction = lease_extraction_from_groups(
        parties_premises=group_models["parties_premises"],  # type: ignore[arg-type]
        term=group_models["term"],  # type: ignore[arg-type]
        financial=group_models["financial"],  # type: ignore[arg-type]
        options_obligations=group_models["options_obligations"],  # type: ignore[arg-type]
        opex=group_models["opex"],  # type: ignore[arg-type]
    )

    run = persist_extraction(
        session=session,
        document_id=document.id,
        lease_id=document.lease_id,
        extraction=extraction,
        context_truncated=context_truncated,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        flagged=flagged,
        needs_review_fields=needs_review_fields,
        scanned_pages=scanned_pages,
        publisher=PostgresEventPublisher(session),
    )

    needs_review_count = sum(1 for field in run.extracted_fields if field.needs_review)

    return PipelineResult(
        extraction=extraction,
        run_id=run.id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_hit=False,
        flagged=flagged,
        context_truncated=context_truncated,
        needs_review_count=needs_review_count,
        scanned_pages=scanned_pages,
    )


def _result_to_json(result: PipelineResult) -> dict:
    payload = result.extraction.model_dump(mode="json")  # type: ignore[union-attr]
    payload["_meta"] = {
        "run_id": str(result.run_id) if result.run_id else None,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cache_hit": result.cache_hit,
        "flagged": result.flagged,
        "context_truncated": result.context_truncated,
        "needs_review_count": result.needs_review_count,
        "scanned_pages": result.scanned_pages,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lease extraction on a PDF")
    parser.add_argument("pdf_path", type=Path, help="Path to lease PDF")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    with SessionLocal() as session:
        document = ingest_pdf(args.pdf_path, session)
        result = run_extraction(document.id, session)
        session.commit()
        print(json.dumps(_result_to_json(result), indent=2))


if __name__ == "__main__":
    main()
