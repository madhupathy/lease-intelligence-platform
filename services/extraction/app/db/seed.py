"""Idempotent demo user seed (AGENTS.md §11).

Run via: python -m app.db.seed
"""

from __future__ import annotations

from sqlalchemy import select

from app.auth_utils import hash_password
from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal


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


def main() -> None:
    seed_demo_user()


if __name__ == "__main__":
    main()
