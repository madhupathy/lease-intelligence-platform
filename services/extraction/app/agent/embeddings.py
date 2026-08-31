"""LangChain embeddings for lease chunk vectorization.

Provider selection (D17): try Anthropic-family embeddings from langchain-anthropic
if exposed; otherwise OpenAI text-embedding-3-small at native 1536 dimensions on
OPENAI_API_KEY. No vector padding.
"""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_PROVIDER = "openai"
EMBEDDING_DIMENSION = 1536
EMBEDDING_MODEL_DEFAULT = "text-embedding-3-small"


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
