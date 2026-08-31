"""Level 3 — generation faithfulness eval (future).

When Q&A is enabled, score answers with a small hand-written judge prompt
(supported-by-context 0/1 + rationale). No RAGAS dependency.
"""

from __future__ import annotations


def note() -> str:
    return (
        "LEVEL 3 (generation): stubbed — Q&A embeddings disabled; "
        "future: faithfulness judge vs retrieved context"
    )


def run() -> None:
    raise NotImplementedError(note())
