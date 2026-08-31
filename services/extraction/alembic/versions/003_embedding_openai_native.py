"""Set lease_chunks.embedding to OpenAI text-embedding-3-small native dimension (1536).

Voyage provider and zero-padding were removed (D17). Invalidate cached embeddings
so re-extraction re-embeds with the OpenAI model. IVFFlat is recreated after
clearing rows that may have used non-native padded vectors.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "003_embedding_openai_native"
down_revision: Union[str, None] = "002_chunk_cache_ivfflat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NATIVE_DIMENSION = 1536


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lease_chunks_embedding_ivfflat")
    op.execute("UPDATE lease_chunks SET embedding = NULL, embedding_model = NULL")

    # Native dimension for OpenAI text-embedding-3-small (no padding).
    op.execute(
        f"ALTER TABLE lease_chunks "
        f"ALTER COLUMN embedding TYPE vector({NATIVE_DIMENSION}) "
        f"USING embedding::vector({NATIVE_DIMENSION})"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lease_chunks_embedding_ivfflat "
        "ON lease_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lease_chunks_embedding_ivfflat")
    op.execute("UPDATE lease_chunks SET embedding = NULL, embedding_model = NULL")
    op.execute(
        f"ALTER TABLE lease_chunks "
        f"ALTER COLUMN embedding TYPE vector({NATIVE_DIMENSION}) "
        f"USING embedding::vector({NATIVE_DIMENSION})"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lease_chunks_embedding_ivfflat "
        "ON lease_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
