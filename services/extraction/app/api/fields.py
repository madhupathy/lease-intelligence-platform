"""Field review API."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.persist import derive_obligations_for_lease
from app.api.deps import get_current_user
from app.db.models import ExtractedField, User
from app.db.session import get_db

router = APIRouter(prefix="/api/fields", tags=["fields"], dependencies=[Depends(get_current_user)])


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    corrected_value: Any | None = None


class ReviewResponse(BaseModel):
    field_id: str
    field_key: str
    effective: bool
    needs_review: bool


@router.post("/{field_id}/review", response_model=ReviewResponse)
def review_field(
    field_id: uuid.UUID,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ReviewResponse:
    old_field = db.get(ExtractedField, field_id)
    if old_field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    if not isinstance(old_field.value_json, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Field is not reviewable")

    new_value_json = dict(old_field.value_json)
    if payload.corrected_value is not None:
        new_value_json["value"] = payload.corrected_value

    needs_review = not payload.accepted
    if payload.accepted:
        new_value_json["confidence"] = max(float(new_value_json.get("confidence", 0)), 0.95)

    old_field.effective = False

    new_field = ExtractedField(
        run_id=old_field.run_id,
        lease_id=old_field.lease_id,
        field_key=old_field.field_key,
        value_json=new_value_json,
        confidence=float(new_value_json.get("confidence", old_field.confidence or 0)),
        page=new_value_json.get("page", old_field.page),
        source_snippet=new_value_json.get("snippet", old_field.source_snippet),
        needs_review=needs_review,
        effective=True,
    )
    db.add(new_field)
    db.flush()

    others = db.scalars(
        select(ExtractedField).where(
            ExtractedField.lease_id == old_field.lease_id,
            ExtractedField.field_key == old_field.field_key,
            ExtractedField.id != new_field.id,
        )
    ).all()
    for field in others:
        field.effective = False

    derive_obligations_for_lease(db, old_field.lease_id)
    db.commit()
    db.refresh(new_field)

    return ReviewResponse(
        field_id=str(new_field.id),
        field_key=new_field.field_key,
        effective=new_field.effective,
        needs_review=new_field.needs_review,
    )
