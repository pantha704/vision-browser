"""Tests for vision-browser core components."""

from __future__ import annotations

import json
import os

import pytest

from vision_browser.browser import _validate_url, _element_to_ref
from vision_browser.config import (
    AppConfig,
    BrowserConfig,
    DesktopConfig,
    OrchestratorConfig,
    VisionConfig,
)
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
        data = {
            "actions": [
                {
                    "action": "click",
                    "element": 1,
                    "meta": {"x": 10, "y": 20, "z": {"a": 1}},
                }
            ],
            "done": False,
        }
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

    def test_viewport_upper_validation(self):
        with pytest.raises(Exception):
            BrowserConfig(viewport=(8000, 5000))

    def test_desktop_config_defaults(self):
        cfg = DesktopConfig()
        assert cfg.screenshot_cmd == "scrot"
        assert cfg.type_delay_ms == 20

    def test_desktop_config_custom(self):
        cfg = DesktopConfig(screenshot_cmd="gnome-screenshot", type_delay_ms=50)
        assert cfg.screenshot_cmd == "gnome-screenshot"
        assert cfg.type_delay_ms == 50

    def test_orchestrator_defaults(self):
        cfg = OrchestratorConfig()
        assert cfg.max_turns == 20
        assert cfg.batch_actions is True
        assert cfg.diff_mode is False
        assert cfg.max_prompt_elements == 30
        assert cfg.retry_attempts == 3
        assert cfg.retry_backoff_base == 1.0
        assert cfg.rate_limit_delay == 0.5

    def test_orchestrator_custom(self):
        cfg = OrchestratorConfig(
            max_turns=50,
            batch_actions=False,
            diff_mode=True,
            max_prompt_elements=50,
            retry_attempts=5,
            retry_backoff_base=2.0,
            rate_limit_delay=1.0,
        )
        assert cfg.max_turns == 50
        assert cfg.batch_actions is False
        assert cfg.diff_mode is True

    def test_from_yaml_loads_existing_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("vision:\n  provider: groq\n  groq_model: test-model\n")
        cfg = AppConfig.from_yaml(str(config_file))
        assert cfg.vision.provider == "groq"
        assert cfg.vision.groq_model == "test-model"

    def test_from_yaml_fallback_no_file(self):
        cfg = AppConfig.from_yaml("/nonexistent/config.yaml")
        assert isinstance(cfg, AppConfig)
        assert cfg.vision.provider == "nim"

    def test_from_yaml_empty_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = AppConfig.from_yaml(str(config_file))
        assert isinstance(cfg, AppConfig)


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
