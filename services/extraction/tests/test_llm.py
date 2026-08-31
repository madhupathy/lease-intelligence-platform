"""ChatAnthropic factory — identity-linked workspace header."""

from __future__ import annotations

from unittest.mock import patch

from app.agent.llm import build_chat_anthropic


class TestBuildChatAnthropic:
    @patch("langchain_anthropic.ChatAnthropic")
    def test_includes_workspace_header_when_configured(self, mock_chat_cls) -> None:
        with patch("app.config.settings.anthropic_api_key", "sk-test"):
            with patch("app.config.settings.extraction_model", "claude-sonnet-4-6"):
                with patch("app.config.settings.anthropic_workspace_id", "ws-abc-123"):
                    build_chat_anthropic()

        mock_chat_cls.assert_called_once_with(
            model="claude-sonnet-4-6",
            temperature=0,
            api_key="sk-test",
            default_headers={"anthropic-workspace-id": "ws-abc-123"},
        )

    @patch("langchain_anthropic.ChatAnthropic")
    def test_omits_workspace_header_when_not_configured(self, mock_chat_cls) -> None:
        with patch("app.config.settings.anthropic_api_key", "sk-test"):
            with patch("app.config.settings.extraction_model", "claude-sonnet-4-6"):
                with patch("app.config.settings.anthropic_workspace_id", None):
                    build_chat_anthropic()

        mock_chat_cls.assert_called_once_with(
            model="claude-sonnet-4-6",
            temperature=0,
            api_key="sk-test",
        )
