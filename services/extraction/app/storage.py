"""PDF storage keyed by content hash (D11)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import settings


def pdf_path_for_sha256(sha256: str) -> Path:
    return Path(settings.storage_dir) / f"{sha256}.pdf"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_pdf_bytes(content: bytes) -> tuple[str, Path]:
    """Persist PDF bytes to STORAGE_DIR/<sha256>.pdf (idempotent if hash exists)."""
    sha256 = sha256_bytes(content)
    destination = pdf_path_for_sha256(sha256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(content)
    return sha256, destination


def resolve_document_path(sha256: str) -> Path:
    """Resolve stored PDF path from document.sha256."""
    path = pdf_path_for_sha256(sha256)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found for sha256={sha256} at {path}")
    return path
