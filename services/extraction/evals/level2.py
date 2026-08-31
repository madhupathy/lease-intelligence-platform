"""Level 2 — retrieval eval (future).

Q&A embeddings / pgvector are currently disabled. When re-enabled, measure
recall@5 and MRR of gold_page in vector search results per question in gold/qa.json.
"""

from __future__ import annotations


def note() -> str:
    return (
        "LEVEL 2 (retrieval): stubbed — Q&A embeddings disabled; "
        "future: recall@5 + MRR vs gold/qa.json"
    )


def run() -> None:
    raise NotImplementedError(note())
