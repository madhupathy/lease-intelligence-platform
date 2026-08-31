"""EventPublisher interface + Postgres implementation (AGENTS.md §3, §11).

Event types (AGENTS.md §11): lease.ingested, extraction.completed,
extraction.flagged, obligation.created, alert.raised, alert.acknowledged.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.db.models import Event


class EventPublisher(Protocol):
    def publish(self, type: str, payload: dict) -> None: ...


class PostgresEventPublisher:
    """Postgres-backed stand-in for a broker; swap for KafkaEventPublisher in
    production without touching call sites."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def publish(self, type: str, payload: dict) -> None:
        self._session.add(Event(type=type, payload=payload))
        self._session.flush()
