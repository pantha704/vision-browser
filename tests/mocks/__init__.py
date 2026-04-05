"""Mock response builders for NIM and Groq APIs."""

from .nim_responses import (
    nim_success_response,
    nim_markdown_response,
    nim_prose_response,
    nim_empty_response,
    nim_partial_json_response,
)
from .groq_responses import (
    groq_success_response,
    groq_tool_call_response,
    groq_empty_response,
)

__all__ = [
    "nim_success_response",
    "nim_markdown_response",
    "nim_prose_response",
    "nim_empty_response",
    "nim_partial_json_response",
    "groq_success_response",
    "groq_tool_call_response",
    "groq_empty_response",
]
