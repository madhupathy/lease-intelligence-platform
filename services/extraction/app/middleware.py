"""Request logging middleware."""

from __future__ import annotations

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/leases") and request.method == "POST":
            run_id = response.headers.get("X-Run-Id")
            logger.info(
                "extraction route %s %s status=%s run_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                run_id,
            )
        return response
