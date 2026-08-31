"""Idempotent demo user + portfolio seed (AGENTS.md §11, §13).

Run via: python -m app.db.seed
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, select

from app.agent.pipeline import create_document_for_upload, run_extraction, validate_upload_bytes
from app.auth_utils import hash_password
from app.config import settings
from app.db.models import Lease, User
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _seed_pdf_dir() -> Path:
    """Resolve seed/pdfs for Docker (/app/seed/pdfs) or monorepo dev layouts."""
    here = Path(__file__).resolve()
    for depth in (2, 3):
        candidate = here.parents[depth] / "seed" / "pdfs"
        if candidate.is_dir():
            return candidate
    return here.parents[2] / "seed" / "pdfs"


def seed_demo_user() -> None:
    """Create the demo user if it does not already exist."""
    with SessionLocal() as session:
        existing = session.scalar(select(User).where(User.username == settings.demo_user))
        if existing is not None:
            return

        session.add(
            User(
                username=settings.demo_user,
                password_hash=hash_password(settings.demo_password),
            )
        )
        session.commit()


def seed_portfolio() -> None:
    """Extract portfolio PDFs from seed/pdfs/ when leases table is empty."""
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

        pdf_dir = _seed_pdf_dir()
        pdfs = sorted(pdf_dir.glob("*.pdf"))
        if not pdfs:
            logger.warning("No PDFs found in %s — skipping portfolio seed", pdf_dir)
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


def main() -> None:
    seed_demo_user()
    seed_portfolio()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
