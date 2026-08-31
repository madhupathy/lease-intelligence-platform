"""Password hashing — bcrypt pin + 72-byte guard."""

from __future__ import annotations

from app.auth_utils import hash_password, verify_password


def test_short_password_round_trip() -> None:
    password = "demo"
    hashed = hash_password(password)
    assert verify_password(password, hashed)


def test_long_password_round_trip() -> None:
    password = "a" * 80
    hashed = hash_password(password)
    assert verify_password(password, hashed)
