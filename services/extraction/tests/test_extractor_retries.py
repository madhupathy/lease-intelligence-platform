"""Extractor structured-output retries and empty-response handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agent.extractor import RETRY_INSTRUCTION, extract_group
from app.agent.schema import Financial


class TestExtractGroupRetries:
    @patch("app.agent.extractor.time.sleep")
    def test_retries_twice_then_degrades_on_empty(self, mock_sleep) -> None:
        llm = MagicMock()
        structured = MagicMock()
        llm.with_structured_output.return_value = structured
        llm.temperature = 0

        empty = {"parsed": None, "raw": MagicMock(content="{}", usage_metadata={}), "parsing_error": None}
        structured.invoke.return_value = empty

        with patch("app.agent.extractor.render_prompt_template", return_value="prompt"):
            result = extract_group("financial", "context", llm=llm)

        assert result.degraded is True
        assert isinstance(result.model, Financial)
        assert structured.invoke.call_count == 3
        assert mock_sleep.call_count == 2

        second_call_messages = structured.invoke.call_args_list[1].args[0]
        assert any(RETRY_INSTRUCTION in getattr(m, "content", "") for m in second_call_messages)

    @patch("app.agent.extractor.time.sleep")
    def test_uses_json_schema_method(self, mock_sleep) -> None:
        llm = MagicMock()
        structured = MagicMock()
        llm.with_structured_output.return_value = structured
        llm.temperature = 0
        structured.invoke.return_value = {
            "parsed": Financial.model_validate({}),
            "raw": MagicMock(content="ok", usage_metadata={"input_tokens": 1, "output_tokens": 1}),
            "parsing_error": None,
        }

        with patch("app.agent.extractor.render_prompt_template", return_value="prompt"):
            result = extract_group("financial", "context", llm=llm)

        assert result.degraded is False
        llm.with_structured_output.assert_called()
        kwargs = llm.with_structured_output.call_args.kwargs
        assert kwargs.get("method") == "json_schema"
        assert kwargs.get("include_raw") is True
