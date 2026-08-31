"""Add chunk cache columns and ivfflat index (post-seed)."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_chunk_cache_ivfflat"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cache columns for embedding idempotency (sha256(text) + model).
    op.add_column("lease_chunks", sa.Column("text_sha256", sa.String(length=64), nullable=True))
    op.add_column("lease_chunks", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.create_index("ix_lease_chunks_text_sha256", "lease_chunks", ["text_sha256"], unique=False)

    # IVFFlat requires existing rows; initial migration deferred this until after seeding.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_lease_chunks_embedding_ivfflat "
        "ON lease_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lease_chunks_embedding_ivfflat")
    op.drop_index("ix_lease_chunks_text_sha256", table_name="lease_chunks")
    op.drop_column("lease_chunks", "embedding_model")
    op.drop_column("lease_chunks", "text_sha256")
