"""Tests for mock response builders."""

from __future__ import annotations

import json

from tests.mocks import (
    groq_empty_response,
    groq_success_response,
    groq_tool_call_response,
    nim_empty_response,
    nim_markdown_response,
    nim_partial_json_response,
    nim_prose_response,
    nim_success_response,
)
from vision_browser.vision import VisionClient


class TestNIMMockResponses:
    """Verify NIM mock responses are parseable by VisionClient._extract_json."""

    def test_nim_success_response_is_valid_json(self):
        resp = nim_success_response()
        content = resp["choices"][0]["message"]["content"]
        result = VisionClient._extract_json(content)
        assert result["done"] is True
        assert "actions" in result

    def test_nim_success_response_with_custom_content(self):
        resp = nim_success_response(
            content='{"actions": [{"action": "click"}], "done": false, "reasoning": "test"}'
        )
        content = resp["choices"][0]["message"]["content"]
        result = VisionClient._extract_json(content)
        assert result["done"] is False
        assert len(result["actions"]) == 1

    def test_nim_markdown_response_parsed(self):
        resp = nim_markdown_response()
        content = resp["choices"][0]["message"]["content"]
        result = VisionClient._extract_json(content)
        assert "actions" in result
        assert result["done"] is False

    def test_nim_prose_response_fallback(self):
        resp = nim_prose_response()
        content = resp["choices"][0]["message"]["content"]
        result = VisionClient._extract_json(content)
        # Should fall back to safe dict with reasoning
        assert "actions" in result
        assert result["done"] is False
        assert "login form" in result["reasoning"]

    def test_nim_empty_response(self):
        resp = nim_empty_response()
        content = resp["choices"][0]["message"]["content"]
        assert content == ""

    def test_nim_partial_json_response(self):
        resp = nim_partial_json_response()
        content = resp["choices"][0]["message"]["content"]
        result = VisionClient._extract_json(content)
        # Should fall back to safe dict since JSON is truncated
        assert isinstance(result, dict)
        assert "actions" in result


class TestGroqMockResponses:
    """Verify Groq mock response structure."""

    def test_groq_success_response(self):
        resp = groq_success_response()
        assert len(resp.choices) == 1
        assert resp.choices[0].message.content is not None
        assert resp.choices[0].message.tool_calls is None
        result = json.loads(resp.choices[0].message.content)
        assert result["done"] is True

    def test_groq_success_response_custom_content(self):
        resp = groq_success_response(content='{"done": false}')
        result = json.loads(resp.choices[0].message.content)
        assert result["done"] is False

    def test_groq_tool_call_response(self):
        resp = groq_tool_call_response()
        assert len(resp.choices) == 1
        assert resp.choices[0].message.content is None
        assert resp.choices[0].message.tool_calls is not None
        assert len(resp.choices[0].message.tool_calls) == 1
        args = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)
        assert "actions" in args

    def test_groq_tool_call_response_custom_args(self):
        resp = groq_tool_call_response(arguments='{"custom": true}')
        args = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)
        assert args["custom"] is True

    def test_groq_empty_response(self):
        resp = groq_empty_response()
        assert resp.choices[0].message.content is None
        assert resp.choices[0].message.tool_calls is None
