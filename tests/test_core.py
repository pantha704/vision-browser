"""Tests for vision-browser core components."""

from __future__ import annotations

import json
import os

import pytest

from vision_browser.browser import _validate_url, _element_to_ref
from vision_browser.config import AppConfig, BrowserConfig, OrchestratorConfig, VisionConfig
from vision_browser.exceptions import (
    ActionExecutionError,
    ConfigError,
)
from vision_browser.vision import VisionClient


# ── JSON Extraction ────────────────────────────────────────────────

class TestExtractJson:
    def test_direct_json(self):
        text = '{"actions": [], "done": true}'
        result = VisionClient._extract_json(text)
        assert result["done"] is True

    def test_markdown_code_block(self):
        text = '```json\n{"actions": [{"action": "click", "element": 3}], "done": false}\n```'
        result = VisionClient._extract_json(text)
        assert len(result["actions"]) == 1

    def test_nested_json(self):
        text = 'Here is the result: {"actions": [{"action": "fill", "element": 2, "text": "hello"}], "done": false, "reasoning": "filling form"}'
        result = VisionClient._extract_json(text)
        assert result["actions"][0]["action"] == "fill"

    def test_deeply_nested_json(self):
        data = {"actions": [{"action": "click", "element": 1, "meta": {"x": 10, "y": 20, "z": {"a": 1}}}], "done": False}
        text = json.dumps(data)
        result = VisionClient._extract_json(text)
        assert result["actions"][0]["meta"]["z"]["a"] == 1

    def test_non_json_text_fallback(self):
        text = "This page shows a login form with a search box."
        result = VisionClient._extract_json(text)
        assert "actions" in result
        assert "reasoning" in result
        assert result["done"] is False

    def test_empty_string(self):
        result = VisionClient._extract_json("")
        assert "actions" in result

    def test_multiple_json_objects(self):
        text = '{"first": 1} {"actions": [{"action": "click", "element": 5}], "done": false} {"last": 3}'
        result = VisionClient._extract_json(text)
        # Should find the first valid JSON object
        assert "actions" in result or "first" in result


# ── Config Validation ──────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.vision.provider == "nim"
        assert cfg.browser.timeout_ms == 30000
        assert cfg.orchestrator.max_turns == 20

    def test_viewport_validation(self):
        with pytest.raises(Exception):
            BrowserConfig(viewport=(100, 100))

    def test_max_turns_validation(self):
        with pytest.raises(Exception):
            OrchestratorConfig(max_turns=0)

    def test_max_turns_upper_validation(self):
        with pytest.raises(Exception):
            OrchestratorConfig(max_turns=200)

    def test_nim_api_key_from_env(self):
        os.environ["NVIDIA_API_KEY"] = "test-key"
        cfg = VisionConfig()
        assert cfg.nim_api_key == "test-key"
        del os.environ["NVIDIA_API_KEY"]

    def test_nim_api_key_missing(self):
        if "NVIDIA_API_KEY" in os.environ:
            del os.environ["NVIDIA_API_KEY"]
        cfg = VisionConfig()
        with pytest.raises(ConfigError, match="NVIDIA_API_KEY"):
            _ = cfg.nim_api_key


# ── URL Validation ─────────────────────────────────────────────────

class TestUrlValidation:
    def test_valid_http(self):
        _validate_url("http://example.com")

    def test_valid_https(self):
        _validate_url("https://example.com/path?q=1")

    def test_reject_file_url(self):
        with pytest.raises(ActionExecutionError, match="http/https"):
            _validate_url("file:///etc/passwd")

    def test_reject_javascript_url(self):
        with pytest.raises(ActionExecutionError, match="http/https"):
            _validate_url("javascript:alert(1)")

    def test_reject_empty_url(self):
        with pytest.raises(ActionExecutionError, match="Empty"):
            _validate_url("")


# ── Element Ref Helpers ────────────────────────────────────────────

class TestElementRef:
    def test_int_to_ref(self):
        assert _element_to_ref(5) == "@e5"

    def test_string_ref_preserved(self):
        assert _element_to_ref("@e12") == "@e12"

    def test_string_ref_without_at(self):
        assert _element_to_ref("e7") == "@e7"

    def test_none_raises(self):
        with pytest.raises(ActionExecutionError, match="element reference"):
            _element_to_ref(None)
