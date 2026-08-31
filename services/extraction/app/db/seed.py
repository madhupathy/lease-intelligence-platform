"""Idempotent demo user seed (AGENTS.md §11).

Run via: python -m app.db.seed
"""

from __future__ import annotations

from passlib.context import CryptContext
from sqlalchemy import select

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


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
