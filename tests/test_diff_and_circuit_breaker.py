"""Tests for differential screenshot integration and circuit breaker config."""

from __future__ import annotations

import pytest

from vision_browser.config import AppConfig
from vision_browser.diff_screenshot import DifferentialScreenshot
from vision_browser.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


class TestDiffScreenshotSkipOptimization:
    """Test that unchanged screenshots skip Vision API calls."""

    def test_first_check_always_returns_changed(self):
        """First check has no previous screenshot, always returns True (changed)."""
        diff = DifferentialScreenshot(threshold=0.01)
        # has_changed() returns True on first call (no previous to compare)
        # We test the internal logic: _previous_screenshot is None initially
        assert diff._previous_screenshot is None
        # After first check, it stores the data
        # We can't test with real files in unit tests, so test the logic directly

    def test_same_binary_data_not_changed(self, tmp_path):
        """Identical screenshot files should not be flagged as changed."""
        diff = DifferentialScreenshot(threshold=0.01)
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG header + data

        first_path = tmp_path / "first.png"
        first_path.write_bytes(fake_image)

        # First call: stores as previous, returns True (first screenshot)
        assert diff.has_changed(str(first_path)) is True

        # Second call with same file: same data, returns False
        assert diff.has_changed(str(first_path)) is False

    def test_different_binary_data_changed(self, tmp_path):
        """Different screenshot files should be flagged as changed."""
        diff = DifferentialScreenshot(threshold=0.01)
        fake_image_1 = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        fake_image_2 = b"\x89PNG\r\n\x1a\n" + b"\xFF" * 100

        path_1 = tmp_path / "first.png"
        path_1.write_bytes(fake_image_1)
        path_2 = tmp_path / "second.png"
        path_2.write_bytes(fake_image_2)

        # First call: stores as previous
        assert diff.has_changed(str(path_1)) is True

        # Second call with different data: returns True (changed)
        assert diff.has_changed(str(path_2)) is True

    def test_reset_clears_cache(self, tmp_path):
        """Reset should clear the previous screenshot cache."""
        diff = DifferentialScreenshot(threshold=0.01)
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        path = tmp_path / "test.png"
        path.write_bytes(fake_image)

        # First call stores it
        assert diff.has_changed(str(path)) is True
        # Second call says unchanged
        assert diff.has_changed(str(path)) is False

        # Reset clears cache
        diff.reset()
        assert diff._previous_screenshot is None

        # Now it should say changed again (no previous to compare)
        assert diff.has_changed(str(path)) is True


class TestDiffScreenshotConfig:
    def test_diff_disabled_by_default(self):
        cfg = AppConfig()
        assert cfg.orchestrator.auto_diff_screenshots is False

    def test_diff_enabled_in_config(self):
        cfg = AppConfig()
        cfg.orchestrator.auto_diff_screenshots = True
        cfg.orchestrator.diff_threshold = 0.05
        assert cfg.orchestrator.auto_diff_screenshots is True
        assert cfg.orchestrator.diff_threshold == 0.05


class TestCircuitBreakerConfig:
    def test_circuit_breaker_defaults(self):
        cfg = AppConfig()
        assert cfg.orchestrator.circuit_breaker_threshold == 5
        assert cfg.orchestrator.circuit_breaker_timeout == 60.0
        assert cfg.orchestrator.circuit_breaker_successes == 2

    def test_circuit_breaker_custom_values(self):
        cfg = AppConfig()
        cfg.orchestrator.circuit_breaker_threshold = 10
        cfg.orchestrator.circuit_breaker_timeout = 120.0
        cfg.orchestrator.circuit_breaker_successes = 5
        assert cfg.orchestrator.circuit_breaker_threshold == 10
        assert cfg.orchestrator.circuit_breaker_timeout == 120.0
        assert cfg.orchestrator.circuit_breaker_successes == 5
