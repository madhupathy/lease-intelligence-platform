"""Events read API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Event, User
from app.db.session import get_db

router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(get_current_user)])


class EventResponse(BaseModel):
    id: str
    type: str
    payload: dict[str, Any]
    created_at: datetime


@router.get("")
def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EventResponse]:
    events = db.scalars(select(Event).order_by(Event.created_at.desc()).limit(limit)).all()
    return [
        EventResponse(
            id=str(event.id),
            type=event.type,
            payload=event.payload,
            created_at=event.created_at,
        )
        for event in events
    ]
