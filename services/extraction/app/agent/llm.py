"""Centralized LangChain Anthropic client construction."""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def build_chat_anthropic() -> BaseChatModel:
    """Build ChatAnthropic with identity-linked workspace header when configured."""
    kwargs: dict[str, Any] = {
        "model": settings.extraction_model,
        "temperature": 0,
        "api_key": settings.anthropic_api_key or None,
    }
    if settings.anthropic_workspace_id:
        kwargs["default_headers"] = {
            "anthropic-workspace-id": settings.anthropic_workspace_id,
        }
    return ChatAnthropic(**kwargs)
