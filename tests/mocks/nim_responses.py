"""Mock response builders for NVIDIA NIM API."""

from __future__ import annotations


def nim_success_response(content: str | None = None) -> dict:
    """Return a valid JSON NIM response.

    Default content: {"actions": [], "done": true, "reasoning": "ok"}
    """
    if content is None:
        content = '{"actions": [], "done": true, "reasoning": "ok"}'
    return {"choices": [{"message": {"content": content}}]}


def nim_markdown_response(content: str | None = None) -> dict:
    """Return a NIM response with JSON wrapped in ```json``` markdown block."""
    if content is None:
        content = '{"actions": [], "done": false, "reasoning": "markdown wrapped"}'
    wrapped = f'```json\n{content}\n```'
    return {"choices": [{"message": {"content": wrapped}}]}


def nim_prose_response() -> dict:
    """Return a NIM response with prose text instead of JSON."""
    return {
        "choices": [
            {
                "message": {
                    "content": "This page shows a login form with username and password fields"
                }
            }
        ]
    }


def nim_empty_response() -> dict:
    """Return a NIM response with empty content."""
    return {"choices": [{"message": {"content": ""}}]}


def nim_partial_json_response() -> dict:
    """Return a NIM response with truncated/partial JSON."""
    return {"choices": [{"message": {"content": '{"actions": [{"action": "click", "elem'}}]}
