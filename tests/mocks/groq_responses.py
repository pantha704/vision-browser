"""Mock response builders for Groq API."""

from __future__ import annotations

from unittest.mock import MagicMock


def groq_success_response(content: str | None = None) -> MagicMock:
    """Return a mock Groq response with valid JSON content.

    Default content: {"actions": [], "done": true, "reasoning": "ok"}
    """
    if content is None:
        content = '{"actions": [], "done": true, "reasoning": "ok"}'

    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response


def groq_tool_call_response(arguments: str | None = None) -> MagicMock:
    """Return a mock Groq response with tool calls (function calling)."""
    if arguments is None:
        arguments = '{"actions": [], "done": true, "reasoning": "tool call"}'

    mock_function = MagicMock()
    mock_function.arguments = arguments

    mock_tool_call = MagicMock()
    mock_tool_call.function = mock_function

    mock_message = MagicMock()
    mock_message.content = None
    mock_message.tool_calls = [mock_tool_call]

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response


def groq_empty_response() -> MagicMock:
    """Return a mock Groq response with empty content and no tool calls."""
    mock_message = MagicMock()
    mock_message.content = None
    mock_message.tool_calls = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response
