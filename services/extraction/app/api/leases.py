"""Lease portfolio and detail APIs."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.pipeline import create_document_for_upload, run_extraction, validate_upload_bytes
from app.api.deps import get_current_user
from app.db.models import Document, ExtractedField, ExtractionRun, Lease, Obligation, User
from app.db.session import get_db
from app.field_groups import FIELD_GROUPS
from app.qa.service import answer_lease_question

router = APIRouter(prefix="/api/leases", tags=["leases"], dependencies=[Depends(get_current_user)])


class RunSummaryResponse(BaseModel):
    document_id: str
    lease_id: str
    run_id: str | None
    status: str
    tokens_in: int
    tokens_out: int
    cache_hit: bool
    flagged: bool
    deduplicated: bool
    needs_review_count: int
    scanned_pages: list[int]
    context_truncated: bool


class LeaseSummaryResponse(BaseModel):
    id: str
    name: str
    landlord: str | None
    tenant: str | None
    expiration: date | None
    needs_review_count: int
    obligation_count: int


class FieldValueResponse(BaseModel):
    id: str
    field_key: str
    value: Any
    confidence: float | None
    page: int | None
    snippet: str | None
    needs_review: bool
    effective: bool


class GroupedFieldsResponse(BaseModel):
    parties_premises: list[FieldValueResponse]
    term: list[FieldValueResponse]
    financial: list[FieldValueResponse]
    options_obligations: list[FieldValueResponse]
    opex: list[FieldValueResponse]


class DocumentResponse(BaseModel):
    id: str
    kind: str
    filename: str
    sha256: str
    page_count: int | None
    uploaded_at: str


class ObligationResponse(BaseModel):
    id: str
    kind: str
    deadline: date | None
    notice_window_days: int | None
    description: str | None


class LeaseDetailResponse(BaseModel):
    id: str
    name: str
    status: str
    fields: GroupedFieldsResponse
    documents: list[DocumentResponse]
    obligations: list[ObligationResponse]


class RunHistoryItem(BaseModel):
    id: str
    document_id: str
    prompt_version: str
    model: str
    tokens_in: int | None
    tokens_out: int | None
    context_truncated: bool
    status: str
    created_at: str


class QAHistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class QARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    history: list[QAHistoryTurn] | None = None


class QACitationResponse(BaseModel):
    page: int | None
    section_tag: str | None
    snippet: str


class QAResponse(BaseModel):
    answer: str
    citations: list[QACitationResponse]
    retrieved_chunk_ids: list[str]


def _effective_value(fields: list[ExtractedField], key: str) -> Any | None:
    for field in fields:
        if field.field_key == key and field.effective:
            if isinstance(field.value_json, dict):
                return field.value_json.get("value")
            return field.value_json
    return None


def _field_response(field: ExtractedField) -> FieldValueResponse:
    value_json = field.value_json if isinstance(field.value_json, dict) else {}
    return FieldValueResponse(
        id=str(field.id),
        field_key=field.field_key,
        value=value_json.get("value") if isinstance(value_json, dict) else field.value_json,
        confidence=float(field.confidence) if field.confidence is not None else None,
        page=field.page,
        snippet=field.source_snippet,
        needs_review=field.needs_review,
        effective=field.effective,
    )


def _group_fields(effective_fields: list[ExtractedField]) -> GroupedFieldsResponse:
    by_key = {field.field_key: field for field in effective_fields if field.effective}
    grouped: dict[str, list[FieldValueResponse]] = {group: [] for group in FIELD_GROUPS}
    for group, keys in FIELD_GROUPS.items():
        for key in keys:
            field = by_key.get(key)
            if field is not None:
                grouped[group].append(_field_response(field))
    return GroupedFieldsResponse(
        parties_premises=grouped["parties_premises"],
        term=grouped["term"],
        financial=grouped["financial"],
        options_obligations=grouped["options_obligations"],
        opex=grouped["opex"],
    )


@router.post("", response_model=RunSummaryResponse)
def upload_lease(
    response: Response,
    pdf: UploadFile = File(...),
    name: str = Form(...),
    kind: str = Form(...),
    lease_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> RunSummaryResponse:
    if kind not in {"base", "amendment"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kind must be base or amendment")

    content = pdf.file.read()
    pages, _ = validate_upload_bytes(content, pdf.filename or "upload.pdf")

    parsed_lease_id = uuid.UUID(lease_id) if lease_id else None
    document, deduplicated = create_document_for_upload(
        session=db,
        content=content,
        filename=pdf.filename or "upload.pdf",
        name=name,
        kind=kind,
        lease_id=parsed_lease_id,
        page_count=len(pages),
    )

    pipeline_result = run_extraction(document.id, db)
    db.commit()
    response.status_code = (
        status.HTTP_200_OK if deduplicated else status.HTTP_201_CREATED
    )
    if pipeline_result.run_id is not None:
        response.headers["X-Run-Id"] = str(pipeline_result.run_id)

    return RunSummaryResponse(
        document_id=str(document.id),
        lease_id=str(document.lease_id),
        run_id=str(pipeline_result.run_id) if pipeline_result.run_id else None,
        status="completed",
        tokens_in=pipeline_result.tokens_in,
        tokens_out=pipeline_result.tokens_out,
        cache_hit=pipeline_result.cache_hit,
        flagged=pipeline_result.flagged,
        deduplicated=deduplicated,
        needs_review_count=pipeline_result.needs_review_count,
        scanned_pages=pipeline_result.scanned_pages,
        context_truncated=pipeline_result.context_truncated,
    )


@router.get("", response_model=list[LeaseSummaryResponse])
def list_leases(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[LeaseSummaryResponse]:
    leases = db.scalars(select(Lease).order_by(Lease.created_at.desc())).all()
    summaries: list[LeaseSummaryResponse] = []

    for lease in leases:
        effective_fields = db.scalars(
            select(ExtractedField).where(
                ExtractedField.lease_id == lease.id,
                ExtractedField.effective.is_(True),
            )
        ).all()
        needs_review_count = db.scalar(
            select(func.count())
            .select_from(ExtractedField)
            .where(ExtractedField.lease_id == lease.id, ExtractedField.needs_review.is_(True))
        ) or 0
        open_obligations = db.scalar(
            select(func.count())
            .select_from(Obligation)
            .where(Obligation.lease_id == lease.id)
        ) or 0

        expiration_raw = _effective_value(list(effective_fields), "expiration_date")
        expiration = date.fromisoformat(str(expiration_raw)) if expiration_raw else None

        summaries.append(
            LeaseSummaryResponse(
                id=str(lease.id),
                name=lease.name,
                landlord=_effective_value(list(effective_fields), "landlord"),
                tenant=_effective_value(list(effective_fields), "tenant"),
                expiration=expiration,
                needs_review_count=int(needs_review_count),
                obligation_count=int(open_obligations),
            )
        )

    return summaries


@router.get("/{lease_id}", response_model=LeaseDetailResponse)
def get_lease(
    lease_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> LeaseDetailResponse:
    lease = db.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    effective_fields = db.scalars(
        select(ExtractedField).where(
            ExtractedField.lease_id == lease.id,
            ExtractedField.effective.is_(True),
        )
    ).all()
    documents = db.scalars(
        select(Document).where(Document.lease_id == lease.id).order_by(Document.uploaded_at.asc())
    ).all()
    obligations = db.scalars(
        select(Obligation).where(Obligation.lease_id == lease.id).order_by(Obligation.deadline.asc())
    ).all()

    return LeaseDetailResponse(
        id=str(lease.id),
        name=lease.name,
        status=lease.status,
        fields=_group_fields(list(effective_fields)),
        documents=[
            DocumentResponse(
                id=str(doc.id),
                kind=doc.kind,
                filename=doc.filename,
                sha256=doc.sha256,
                page_count=doc.page_count,
                uploaded_at=doc.uploaded_at.isoformat(),
            )
            for doc in documents
        ],
        obligations=[
            ObligationResponse(
                id=str(item.id),
                kind=item.kind,
                deadline=item.deadline,
                notice_window_days=item.notice_window_days,
                description=item.description,
            )
            for item in obligations
        ],
    )


@router.get("/{lease_id}/runs", response_model=list[RunHistoryItem])
def list_runs(
    lease_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[RunHistoryItem]:
    lease = db.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    document_ids = db.scalars(select(Document.id).where(Document.lease_id == lease_id)).all()
    if not document_ids:
        return []

    runs = db.scalars(
        select(ExtractionRun)
        .where(ExtractionRun.document_id.in_(document_ids))
        .order_by(ExtractionRun.created_at.desc())
    ).all()

    return [
        RunHistoryItem(
            id=str(run.id),
            document_id=str(run.document_id),
            prompt_version=run.prompt_version,
            model=run.model,
            tokens_in=run.tokens_in,
            tokens_out=run.tokens_out,
            context_truncated=run.context_truncated,
            status=run.status,
            created_at=run.created_at.isoformat(),
        )
        for run in runs
    ]


@router.post("/{lease_id}/qa", response_model=QAResponse)
def ask_lease_question(
    lease_id: uuid.UUID,
    payload: QARequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> QAResponse:
    lease = db.get(Lease, lease_id)
    if lease is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

    if not settings.enable_qa:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Q&A disabled")

    history = None
    if payload.history:
        history = [turn.model_dump() for turn in payload.history[-6:]]

    result = answer_lease_question(
        session=db,
        lease_id=lease_id,
        question=payload.question,
        history=history,
    )
    db.commit()

    return QAResponse(
        answer=result.answer,
        citations=[
            QACitationResponse(page=c.page, section_tag=c.section_tag, snippet=c.snippet)
            for c in result.citations
        ],
        retrieved_chunk_ids=result.retrieved_chunk_ids,
    )
