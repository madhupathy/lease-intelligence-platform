"""Stage 5 — extractor: LangChain + Claude structured output (AGENTS.md §7)."""

from __future__ import annotations

import logging
import time
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agent.llm import EXTRACTION_TEMPERATURE, build_chat_anthropic
from app.agent.prompts import render_prompt_template
from app.agent.schema import (
    Financial,
    Opex,
    OptionsObligations,
    PartiesPremises,
    Term,
    empty_group,
)
from app.agent.types import ExtractGroupResult

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

MAX_STRUCTURED_ATTEMPTS = 3  # initial + 2 retries
RETRY_BACKOFF_SECONDS = 0.75
RETRY_INSTRUCTION = (
    "Return a valid JSON object matching the schema. If a field is unknown, "
    "set value to null with confidence 0 — but DO NOT return an empty object."
)
RAW_LOG_LIMIT = 500


def _default_llm() -> BaseChatModel:
    return build_chat_anthropic()


def _extract_usage_metadata(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))

    response_metadata = getattr(response, "response_metadata", {}) or {}
    usage_meta = response_metadata.get("usage", {})
    return int(usage_meta.get("input_tokens", 0)), int(usage_meta.get("output_tokens", 0))


def _raw_preview(raw: Any, limit: int = RAW_LOG_LIMIT) -> str:
    if raw is None:
        return "<none>"
    content = getattr(raw, "content", raw)
    text = str(content)
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def _bind_structured(chat_model: BaseChatModel, model_cls: type[BaseModel]) -> Any:
    """Default tool-calling structured output (reliable for this Anthropic + LangChain stack)."""
    structured = chat_model.with_structured_output(model_cls, include_raw=True)
    logger.info(
        "structured_output method=default(tool_calling) temperature=%s schema=%s",
        EXTRACTION_TEMPERATURE,
        model_cls.__name__,
    )
    return structured


def _coerce_group_model(model_cls: type[BaseModel], parsed: Any) -> BaseModel:
    """Validate LLM output; missing/null fields become null leaves."""
    if parsed is None:
        raise ValueError("Structured output was empty")
    if isinstance(parsed, BaseModel):
        return model_cls.model_validate(parsed.model_dump(mode="python"))
    return model_cls.model_validate(parsed)


def extract_group(
    group_name: str,
    context: str,
    llm: BaseChatModel | None = None,
) -> ExtractGroupResult:
    """One LLM call per field group at temperature 0, with retries on empty/invalid output.

    After retries, degrade to an empty (null-leaf) group instead of crashing the pipeline.
    LLM calls are bounded by ChatAnthropic default_request_timeout so hangs cannot stall seed.
    """
    if group_name not in GROUP_MODELS:
        raise ValueError(f"Unknown extraction group: {group_name}")

    model_cls = GROUP_MODELS[group_name]
    template_name = PROMPT_TEMPLATES[group_name]
    prompt_text = render_prompt_template(template_name, context)

    chat_model = llm or _default_llm()
    temperature = getattr(chat_model, "temperature", EXTRACTION_TEMPERATURE)
    logger.debug("extract_group=%s using temperature=%s", group_name, temperature)

    structured = _bind_structured(chat_model, model_cls)
    messages: list[Any] = [HumanMessage(content=prompt_text)]
    tokens_in = 0
    tokens_out = 0
    last_error: Exception | None = None

    for attempt in range(1, MAX_STRUCTURED_ATTEMPTS + 1):
        try:
            response = structured.invoke(messages)
            if not isinstance(response, dict):
                raise ValueError(f"Unexpected structured response type: {type(response)}")

            parsed = response.get("parsed")
            raw = response.get("raw")
            parsing_error = response.get("parsing_error")
            if raw is not None:
                attempt_in, attempt_out = _extract_usage_metadata(raw)
                tokens_in += attempt_in
                tokens_out += attempt_out

            if parsed is None:
                preview = _raw_preview(raw)
                logger.warning(
                    "Structured output empty for %s attempt=%s/%s parsing_error=%s raw=%s",
                    group_name,
                    attempt,
                    MAX_STRUCTURED_ATTEMPTS,
                    parsing_error,
                    preview,
                )
                raise ValueError("Structured output was empty")

            validated = _coerce_group_model(model_cls, parsed)
            return ExtractGroupResult(
                group_name=group_name,
                model=validated,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                degraded=False,
            )
        except Exception as error:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            last_error = error
            logger.warning(
                "Schema validation failed for %s attempt=%s/%s: %s",
                group_name,
                attempt,
                MAX_STRUCTURED_ATTEMPTS,
                error,
            )
            if attempt >= MAX_STRUCTURED_ATTEMPTS:
                break
            messages = messages + [
                HumanMessage(
                    content=(
                        f"Validation error — fix output to match schema: {error}\n"
                        f"{RETRY_INSTRUCTION}"
                    )
                )
            ]
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    logger.warning(
        "Structured output empty/invalid for %s after %s attempts — degrading to null leaves "
        "(last_error=%s)",
        group_name,
        MAX_STRUCTURED_ATTEMPTS,
        last_error,
    )
    return ExtractGroupResult(
        group_name=group_name,
        model=empty_group(model_cls),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        degraded=True,
    )
