"""Stage 5 — extractor: LangChain + Claude structured output (AGENTS.md §7)."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from app.agent.prompts import render_prompt_template
from app.agent.schema import (
    Financial,
    Opex,
    OptionsObligations,
    PartiesPremises,
    Term,
)
from app.agent.types import ExtractGroupResult
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

GROUP_MODELS: dict[str, type[BaseModel]] = {
    "parties_premises": PartiesPremises,
    "term": Term,
    "financial": Financial,
    "options_obligations": OptionsObligations,
    "opex": Opex,
}

PROMPT_TEMPLATES: dict[str, str] = {
    "parties_premises": "parties_premises_v1.0.md.j2",
    "term": "term_v1.0.md.j2",
    "financial": "financial_v1.0.md.j2",
    "options_obligations": "options_obligations_v1.0.md.j2",
    "opex": "opex_v1.0.md.j2",
}

PROMPT_VERSION = "v1.0"


def _default_llm() -> BaseChatModel:
    return ChatAnthropic(
        model=settings.extraction_model,
        temperature=0,
        api_key=settings.anthropic_api_key or None,
    )


def _extract_usage_metadata(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))

    response_metadata = getattr(response, "response_metadata", {}) or {}
    usage_meta = response_metadata.get("usage", {})
    return int(usage_meta.get("input_tokens", 0)), int(usage_meta.get("output_tokens", 0))


def extract_group(
    group_name: str,
    context: str,
    llm: BaseChatModel | None = None,
) -> ExtractGroupResult:
    """One LLM call per field group, temperature 0, retry once on schema-invalid."""
    if group_name not in GROUP_MODELS:
        raise ValueError(f"Unknown extraction group: {group_name}")

    model_cls = GROUP_MODELS[group_name]
    template_name = PROMPT_TEMPLATES[group_name]
    prompt_text = render_prompt_template(template_name, context)

    chat_model = llm or _default_llm()
    structured = chat_model.with_structured_output(model_cls, include_raw=True)

    messages = [HumanMessage(content=prompt_text)]
    tokens_in = 0
    tokens_out = 0

    try:
        response = structured.invoke(messages)
        parsed = response["parsed"]
        raw = response.get("raw")
        if raw is not None:
            tokens_in, tokens_out = _extract_usage_metadata(raw)
        if parsed is None:
            raise ValidationError.from_exception_data(
                model_cls.__name__,
                [{"type": "missing", "loc": (), "msg": "Structured output was empty"}],
            )
        validated = model_cls.model_validate(parsed.model_dump())
    except (ValidationError, ValueError, TypeError) as first_error:
        logger.warning("Schema validation failed for %s, retrying once: %s", group_name, first_error)
        retry_messages = messages + [
            HumanMessage(content=f"Validation error — fix output to match schema: {first_error}")
        ]
        response = structured.invoke(retry_messages)
        parsed = response["parsed"]
        raw = response.get("raw")
        if raw is not None:
            retry_in, retry_out = _extract_usage_metadata(raw)
            tokens_in += retry_in
            tokens_out += retry_out
        if parsed is None:
            raise ValidationError.from_exception_data(
                model_cls.__name__,
                [{"type": "missing", "loc": (), "msg": "Structured output was empty on retry"}],
            )
        validated = model_cls.model_validate(parsed.model_dump())

    return ExtractGroupResult(
        group_name=group_name,
        model=validated,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
