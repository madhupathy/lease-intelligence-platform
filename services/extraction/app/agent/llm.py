"""Centralized LangChain Anthropic client construction."""

from __future__ import annotations

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_TEMPERATURE = 0


def build_chat_anthropic() -> BaseChatModel:
    """Build ChatAnthropic with identity-linked workspace header when configured."""
    kwargs: dict[str, Any] = {
        "model": settings.extraction_model,
        "temperature": EXTRACTION_TEMPERATURE,
        "api_key": settings.anthropic_api_key or None,
    }
    if settings.anthropic_workspace_id:
        kwargs["default_headers"] = {
            "anthropic-workspace-id": settings.anthropic_workspace_id,
        }
    logger.info(
        "ChatAnthropic configured model=%s temperature=%s workspace_id_set=%s",
        settings.extraction_model,
        EXTRACTION_TEMPERATURE,
        bool(settings.anthropic_workspace_id),
    )
    return ChatAnthropic(**kwargs)
