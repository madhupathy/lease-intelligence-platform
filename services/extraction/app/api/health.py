"""Health router. Returns liveness for the extraction service."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe consumed by the gateway and docker healthcheck."""
    return {"status": "ok", "version": settings.version}
