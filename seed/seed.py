"""Idempotent portfolio seed from seed/pdfs/ (AGENTS.md §13)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, select

from app.agent.pipeline import create_document_for_upload, run_extraction, validate_upload_bytes
from app.config import settings
from app.db.models import Lease
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
SEED_PDF_DIR = Path(__file__).resolve().parent / "pdfs"


def main() -> None:
    if not settings.anthropic_api_key or not settings.openai_api_key:
        logger.warning(
            "ANTHROPIC_API_KEY and/or OPENAI_API_KEY unset — skipping PDF seed extraction"
        )
        return

    with SessionLocal() as session:
        lease_count = session.scalar(select(func.count()).select_from(Lease)) or 0
        if lease_count > 0:
            logger.info("Leases table not empty — skipping portfolio seed")
            return

        pdfs = sorted(SEED_PDF_DIR.glob("*.pdf"))
        if not pdfs:
            logger.warning("No PDFs found in %s — skipping portfolio seed", SEED_PDF_DIR)
            return

        for pdf_path in pdfs:
            content = pdf_path.read_bytes()
            pages, _ = validate_upload_bytes(content, pdf_path.name)
            document, _ = create_document_for_upload(
                session=session,
                content=content,
                filename=pdf_path.name,
                name=pdf_path.stem,
                kind="base",
                lease_id=None,
                page_count=len(pages),
            )
            run_extraction(document.id, session)
            session.commit()
            logger.info("Seeded lease from %s (document_id=%s)", pdf_path.name, document.id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
