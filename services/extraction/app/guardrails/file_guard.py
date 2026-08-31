"""Input guard: PDF only, size limit, extractable pages (AGENTS.md §8)."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext


class FileGuard:
    def check(self, ctx: GuardContext) -> Result:
        if ctx.file_path is None:
            return Result(Verdict.BLOCK, "No file path provided")

        path = Path(ctx.file_path)
        if path.suffix.lower() != ".pdf":
            return Result(Verdict.BLOCK, "Only PDF files are accepted")

        size = path.stat().st_size
        if size > settings.max_upload_bytes:
            return Result(Verdict.BLOCK, f"File exceeds {settings.max_upload_bytes} bytes")

        if not ctx.pages:
            return Result(Verdict.BLOCK, "PDF has no pages")

        extractable = [page for page in ctx.pages if not page.maybe_scanned]
        if not extractable:
            return Result(Verdict.BLOCK, "PDF has no extractable text pages")

        return Result(Verdict.PASS)
