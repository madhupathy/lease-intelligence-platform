"""LangChain embeddings for lease chunk vectorization.

Provider selection (D17): try Anthropic-family embeddings from langchain-anthropic
if exposed; otherwise OpenAI text-embedding-3-small at native 1536 dimensions on
OPENAI_API_KEY. No vector padding.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_PROVIDER = "openai"
EMBEDDING_DIMENSION = 1536
EMBEDDING_MODEL_DEFAULT = "text-embedding-3-small"
EMBEDDING_SKIP_WARNING = (
    "Embeddings unavailable — Q&A disabled for this lease; extraction unaffected"
)


def _try_anthropic_embeddings() -> Embeddings | None:
    """Return Anthropic embeddings if langchain-anthropic exposes a class."""
    try:
        from langchain_anthropic import AnthropicEmbeddings  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        return None

    if not settings.anthropic_api_key:
        return None

    logger.info("Using AnthropicEmbeddings from langchain-anthropic")
    return AnthropicEmbeddings(
        model=settings.embedding_model,
        api_key=settings.anthropic_api_key,
    )


def embeddings_configured() -> bool:
    """Return True when an embedding provider can be constructed."""
    if _try_anthropic_embeddings() is not None:
        return True
    return bool(settings.openai_api_key)


def get_embedding_model() -> Embeddings:
    """Return the configured LangChain embeddings implementation."""
    anthropic = _try_anthropic_embeddings()
    if anthropic is not None:
        return anthropic

    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required for embeddings "
            "(Anthropic does not expose an embeddings API in langchain-anthropic)"
        )

    from langchain_openai import OpenAIEmbeddings

    logger.info("Using OpenAIEmbeddings model=%s", settings.embedding_model)
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


def is_embedding_api_error(exc: BaseException) -> bool:
    """Detect auth/quota failures from OpenAI or wrapped LangChain errors."""
    visited: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in visited:
        visited.add(id(current))

        status_code = getattr(current, "status_code", None)
        if status_code in (401, 403, 429):
            return True

        message = str(current).lower()
        if any(
            token in message
            for token in (
                "insufficient_quota",
                "invalid_api_key",
                "incorrect api key",
                "authentication",
                "unauthorized",
            )
        ):
            return True

        body: Any = getattr(current, "body", None)
        if isinstance(body, dict):
            error = body.get("error", {})
            if isinstance(error, dict) and error.get("code") in (
                "insufficient_quota",
                "invalid_api_key",
            ):
                return True

        current = current.__cause__ or current.__context__
    return False


def embed_texts(texts: list[str], embeddings: Embeddings | None = None) -> list[list[float]]:
    """Embed texts at the provider's native dimension (no padding)."""
    model = embeddings or get_embedding_model()
    vectors = model.embed_documents(texts)
    result: list[list[float]] = []
    for vector in vectors:
        values = list(vector)
        if len(values) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding dimension {len(values)} != expected native {EMBEDDING_DIMENSION}"
            )
        result.append(values)
    return result
