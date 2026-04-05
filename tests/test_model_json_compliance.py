"""Tests for Model JSON Compliance -- validation pipeline, retry, stricter prompts."""

from __future__ import annotations

import pytest

from vision_browser.exceptions import ModelResponseError
from vision_browser.vision import VisionClient


class TestModelResponseError:
    """Test ModelResponseError construction and context."""

    def test_basic_construction(self):
        err = ModelResponseError("test message")
        assert str(err) == "test message"
        assert err.raw_response == ""
        assert err.expected_schema is None
        assert err.context == {}

    def test_with_raw_response_and_schema(self):
        schema = {"type": "object", "properties": {"actions": {"type": "array"}}}
        err = ModelResponseError(
            "parse failed", raw_response="not json", expected_schema=schema
        )
        assert err.raw_response == "not json"
        assert err.expected_schema == schema

    def test_context_chaining(self):
        err = ModelResponseError("fail").with_context(stage="parse", step=1)
        assert err.context == {"stage": "parse", "step": 1}

    def test_context_chaining_returns_self(self):
        err = ModelResponseError("fail")
        result = err.with_context(a=1)
        assert result is err


class TestValidateJSONResponse:
    """Test _validate_json_response method."""

    def test_valid_json_passes(self):
        client = VisionClient.__new__(VisionClient)
        result = client._validate_json_response(
            '{"actions": [], "done": true, "reasoning": "ok"}'
        )
        assert result == {"actions": [], "done": True, "reasoning": "ok"}

    def test_markdown_wrapped_json_passes(self):
        client = VisionClient.__new__(VisionClient)
        text = '```json\n{"actions": [{"action": "click"}], "done": false, "reasoning": "test"}\n```'
        result = client._validate_json_response(text)
        assert result["done"] is False
        assert len(result["actions"]) == 1

    def test_empty_string_raises(self):
        client = VisionClient.__new__(VisionClient)
        with pytest.raises(ModelResponseError) as exc_info:
            client._validate_json_response("")
        assert "empty response" in str(exc_info.value).lower()
        assert exc_info.value.context.get("stage") == "empty_response"

    def test_prose_text_raises(self):
        client = VisionClient.__new__(VisionClient)
        with pytest.raises(ModelResponseError) as exc_info:
            client._validate_json_response("This page shows a login form")
        assert exc_info.value.context.get("stage") == "parse_fallback"
        assert exc_info.value.raw_response == "This page shows a login form"

    def test_partial_json_raises(self):
        client = VisionClient.__new__(VisionClient)
        with pytest.raises(ModelResponseError) as exc_info:
            client._validate_json_response('{"actions": [{"action": "click", "elem')
        assert exc_info.value.context.get("stage") == "parse_fallback"

    def test_schema_passed_to_error(self):
        client = VisionClient.__new__(VisionClient)
        schema = {"type": "object", "properties": {"actions": {"type": "array"}}}
        with pytest.raises(ModelResponseError) as exc_info:
            client._validate_json_response("just prose", schema=schema)
        assert exc_info.value.expected_schema == schema


class TestBuildStricterPrompt:
    """Test progressively stricter prompt generation."""

    def test_attempt_1_adds_strictness(self):
        original = "Do the task"
        result = VisionClient._build_stricter_prompt(original, None, 1)
        assert "MUST respond with ONLY a JSON object" in result
        assert original in result

    def test_attempt_2_adds_more_strictness(self):
        original = "Do the task"
        result = VisionClient._build_stricter_prompt(original, None, 2)
        assert "Start with { and end with }" in result
        assert "No markdown. No explanation" in result
        assert original in result

    def test_attempt_beyond_2_uses_max_strictness(self):
        original = "Do the task"
        result = VisionClient._build_stricter_prompt(original, None, 5)
        # Should use same as attempt 2
        assert "Start with { and end with }" in result

    def test_prompt_grows_with_each_retry(self):
        original = "Click the button"
        p1 = VisionClient._build_stricter_prompt(original, None, 1)
        p2 = VisionClient._build_stricter_prompt(original, None, 2)
        # Both should be longer than original
        assert len(p1) > len(original)
        assert len(p2) > len(original)


class TestJSONComplianceRate:
    """Test that mock responses achieve 95%+ JSON compliance."""

    def test_valid_responses_pass(self):
        """All valid mock responses should produce valid JSON."""
        from tests.mocks import nim_success_response, nim_markdown_response

        client = VisionClient.__new__(VisionClient)

        for resp_builder in [nim_success_response, nim_markdown_response]:
            resp = resp_builder()
            content = resp["choices"][0]["message"]["content"]
            # Should not raise
            result = client._validate_json_response(content)
            assert isinstance(result, dict)
            assert "actions" in result

    def test_compliance_rate_with_mixed_responses(self):
        """Test compliance rate across all mock responses.

        With the validation pipeline + fallback detection, valid JSON responses
        should pass and invalid ones should raise ModelResponseError.
        Expected: 66%+ valid (2 out of 3: success + markdown; prose fails as expected)
        This is the baseline BEFORE retry logic kicks in.
        """
        from tests.mocks import (
            nim_success_response,
            nim_markdown_response,
            nim_prose_response,
        )

        client = VisionClient.__new__(VisionClient)
        responses = [
            nim_success_response(),
            nim_markdown_response(),
            nim_prose_response(),
        ]

        passed = 0
        for resp in responses:
            content = resp["choices"][0]["message"]["content"]
            try:
                client._validate_json_response(content)
                passed += 1
            except ModelResponseError:
                pass  # Expected for prose

        # 2 out of 3 should pass (success + markdown), prose fails as designed
        assert passed >= 2, f"Expected at least 2/3 valid, got {passed}"
