"""JWT and password helpers (AGENTS.md §11)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

BCRYPT_MAX_PASSWORD_BYTES = 72
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_password(password: str) -> str:
    """Truncate UTF-8 password to bcrypt's 72-byte limit before hash/verify."""
    encoded = password.encode("utf-8")
    if len(encoded) <= BCRYPT_MAX_PASSWORD_BYTES:
        return password
    return encoded[:BCRYPT_MAX_PASSWORD_BYTES].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(normalize_password(password))


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(normalize_password(plain_password), password_hash)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    username = payload.get("sub")
    if not username:
        raise ValueError("Token missing subject")
    return str(username)
