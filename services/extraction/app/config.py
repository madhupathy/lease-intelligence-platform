"""Central configuration. ALL tunables live here (AGENTS.md §11, §12).

Every value is sourced from the environment via pydantic-settings so there are no
magic numbers in code. Defaults mirror AGENTS.md §12.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service metadata ---
    service_name: str = "extraction"
    version: str = "0.1.0"

    # --- Persistence ---
    database_url: str = "postgresql+psycopg://lease:lease@postgres:5432/lease"
    storage_dir: str = "/app/storage"

    # --- LLM / extraction (AGENTS.md §12) ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    extraction_model: str = "claude-sonnet-4-6"
    embedding_model: str = "text-embedding-3-small"
    max_context_tokens: int = 12000

    # --- Q&A / retrieval ---
    qa_top_k: int = 5
    qa_min_similarity: float = 0.25
    chunk_target_tokens: int = 800
    chunk_overlap_tokens: int = 100
    qa_history_max_turns: int = 6

    # --- Guardrails (AGENTS.md §8, §12) ---
    review_threshold: float = 0.7
    max_upload_bytes: int = 25 * 1024 * 1024

    # --- Auth (AGENTS.md §11, §12) ---
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 12
    demo_user: str = "demo"
    demo_password: str = "demo"

    # --- Risk engine tunables (shared config surface, AGENTS.md §12) ---
    risk_critical_days: int = 90
    risk_warning_days: int = 180
    schedule_delay_ms: int = 300000


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()


def get_input_guardrails() -> list:
    from app.guardrails.file_guard import FileGuard
    from app.guardrails.injection_scan import InjectionScan

    return [FileGuard(), InjectionScan()]


def get_output_guardrails() -> list:
    from app.guardrails.citation_guard import CitationGuard
    from app.guardrails.confidence_gate import ConfidenceGate
    from app.guardrails.sanity_guard import SanityGuard
    from app.guardrails.schema_guard import SchemaGuard

    return [SchemaGuard(), SanityGuard(), CitationGuard(), ConfidenceGate()]
