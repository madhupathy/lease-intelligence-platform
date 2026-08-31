"""FastAPI application entrypoint.

Wires the API routers. Business logic lives in app/agent, app/guardrails, and
app/db — this module only assembles the app (AGENTS.md §4).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import auth, events, fields, health, leases
from app.config import settings
from app.errors import register_exception_handlers
from app.middleware import RequestLoggingMiddleware

# Packaged by Dockerfile: COPY web/standalone/ → /app/static/
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DASHBOARD_INDEX = STATIC_DIR / "index.html"

app = FastAPI(title="Lease Intelligence — Extraction", version=settings.version)

register_exception_handlers(app)
app.add_middleware(RequestLoggingMiddleware)
# Demo: allow any origin; production should restrict allow_origins to the dashboard's real origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(leases.router)
app.include_router(fields.router)
app.include_router(events.router)


@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
def standalone_dashboard() -> FileResponse:
    """Serve the vanilla interview dashboard (same-origin with the API)."""
    if not DASHBOARD_INDEX.is_file():
        raise HTTPException(status_code=404, detail="Dashboard not packaged in this image")
    return FileResponse(DASHBOARD_INDEX, media_type="text/html")
