"""Pytest fixtures for Postgres-backed integration tests."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

DATABASE_URL = os.environ.get("DATABASE_URL")

SKIP_REASON = (
    "DATABASE_URL not set — Postgres with pgvector required for DB tests (sqlite is not supported)"
)


def _require_postgres_url() -> str:
    if not DATABASE_URL:
        pytest.skip(SKIP_REASON)
    return DATABASE_URL


@pytest.fixture(scope="session")
def db_engine():
    url = _require_postgres_url()
    engine = create_engine(url, pool_pre_ping=True)

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def api_client(db_session):
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app.auth_utils import pwd_context
    from app.config import settings
    from app.db.models import User
    from app.db.session import get_db
    from app.main import app

    existing = db_session.scalar(select(User).where(User.username == settings.demo_user))
    if existing is None:
        db_session.add(
            User(
                username=settings.demo_user,
                password_hash=pwd_context.hash(settings.demo_password),
            )
        )
        db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
