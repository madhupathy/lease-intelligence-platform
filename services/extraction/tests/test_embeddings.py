"""Embedding provider selection and native dimension (no padding)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agent.embeddings import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_DEFAULT,
    EMBEDDING_PROVIDER,
    embed_texts,
    get_embedding_model,
)


class TestEmbeddings:
    def test_constants_match_openai_native(self) -> None:
        assert EMBEDDING_PROVIDER == "openai"
        assert EMBEDDING_DIMENSION == 1536
        assert EMBEDDING_MODEL_DEFAULT == "text-embedding-3-small"

    def test_embed_texts_rejects_wrong_dimension(self) -> None:
        fake = MagicMock()
        fake.embed_documents.return_value = [[1.0, 2.0]]
        with pytest.raises(ValueError, match="Embedding dimension"):
            embed_texts(["hello"], embeddings=fake)

    def test_embed_texts_accepts_native_dimension(self) -> None:
        fake = MagicMock()
        fake.embed_documents.return_value = [[1.0] * EMBEDDING_DIMENSION]
        vectors = embed_texts(["hello"], embeddings=fake)
        assert len(vectors[0]) == EMBEDDING_DIMENSION

    def test_get_embedding_model_uses_openai_when_no_anthropic_class(self) -> None:
        with patch("app.agent.embeddings._try_anthropic_embeddings", return_value=None):
            with patch("app.config.settings.openai_api_key", "sk-test"):
                with patch("langchain_openai.OpenAIEmbeddings") as mock_openai_cls:
                    get_embedding_model()
        mock_openai_cls.assert_called_once()
