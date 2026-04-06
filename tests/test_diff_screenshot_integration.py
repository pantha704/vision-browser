"""Tests for Differential Screenshot Integration into FastOrchestrator."""

from __future__ import annotations


from vision_browser.config import AppConfig
from vision_browser.diff_screenshot import DifferentialScreenshot


class TestDiffScreenshotConfig:
    """Test config defaults and overrides for differential screenshots."""

    def test_diff_defaults_off(self):
        cfg = AppConfig()
        assert cfg.orchestrator.auto_diff_screenshots is False
        assert cfg.orchestrator.diff_mode is False
        assert cfg.orchestrator.diff_threshold == 0.01
        assert cfg.orchestrator.diff_max_retain == 10

    def test_diff_enabled_via_auto_diff(self):
        cfg = AppConfig.model_validate(
            {"orchestrator": {"auto_diff_screenshots": True}}
        )
        assert cfg.orchestrator.auto_diff_screenshots is True

    def test_diff_enabled_via_diff_mode(self):
        cfg = AppConfig.model_validate({"orchestrator": {"diff_mode": True}})
        assert cfg.orchestrator.diff_mode is True

    def test_diff_threshold_override(self):
        cfg = AppConfig.model_validate({"orchestrator": {"diff_threshold": 0.05}})
        assert cfg.orchestrator.diff_threshold == 0.05

    def test_diff_max_retain_override(self):
        cfg = AppConfig.model_validate({"orchestrator": {"diff_max_retain": 25}})
        assert cfg.orchestrator.diff_max_retain == 25


class TestDiffScreenshotIntegration:
    """Test DifferentialScreenshot is initialized correctly in FastOrchestrator."""

    def test_diff_always_enabled_for_reliable_change_detection(self):
        """Diff screenshot is always enabled for reliable change detection."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig()
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)
        assert orchestrator.diff_screenshot is not None
        assert orchestrator._diff_log == []

    def test_diff_initialized_when_auto_diff_enabled(self):
        """When auto_diff_screenshots is True, diff_screenshot should be set."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig.model_validate(
            {"orchestrator": {"auto_diff_screenshots": True}}
        )
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)
        assert orchestrator.diff_screenshot is not None
        assert isinstance(orchestrator.diff_screenshot, DifferentialScreenshot)
        assert orchestrator.diff_screenshot.threshold == 0.01

    def test_diff_initialized_when_diff_mode_enabled(self):
        """When diff_mode is True (legacy flag), diff_screenshot should be set."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig.model_validate({"orchestrator": {"diff_mode": True}})
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)
        assert orchestrator.diff_screenshot is not None

    def test_diff_uses_custom_threshold(self):
        """Threshold from config should be passed to DifferentialScreenshot."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig.model_validate(
            {"orchestrator": {"auto_diff_screenshots": True, "diff_threshold": 0.05}}
        )
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)
        assert orchestrator.diff_screenshot.threshold == 0.05


class TestDiffLogAndCleanup:
    """Test diff logging and cleanup."""

    def test_log_diff_appends_entry(self):
        """_log_diff should append an entry with turn, action, changed, path."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig()
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)

        orchestrator._log_diff(
            turn=1, action="pre-analysis", changed=True, path="/tmp/test.png"
        )
        assert len(orchestrator._diff_log) == 1
        entry = orchestrator._diff_log[0]
        assert entry["turn"] == 1
        assert entry["action"] == "pre-analysis"
        assert entry["changed"] is True
        assert entry["path"] == "/tmp/test.png"
        assert "timestamp" in entry

    def test_cleanup_removes_oldest_entries(self):
        """_cleanup_diffs should remove oldest entries beyond max_retain."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig.model_validate(
            {"orchestrator": {"auto_diff_screenshots": True, "diff_max_retain": 3}}
        )
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)

        # Add 5 entries
        for i in range(5):
            orchestrator._log_diff(
                turn=i, action="test", changed=True, path=f"/tmp/{i}.png"
            )

        assert len(orchestrator._diff_log) == 5
        orchestrator._cleanup_diffs()
        assert len(orchestrator._diff_log) == 3
        # Should keep the last 3 (turns 2, 3, 4)
        assert orchestrator._diff_log[0]["turn"] == 2
        assert orchestrator._diff_log[-1]["turn"] == 4

    def test_cleanup_noop_when_under_limit(self):
        """_cleanup_diffs should do nothing when under max_retain."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig.model_validate(
            {"orchestrator": {"auto_diff_screenshots": True, "diff_max_retain": 10}}
        )
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)

        for i in range(3):
            orchestrator._log_diff(
                turn=i, action="test", changed=True, path=f"/tmp/{i}.png"
            )

        orchestrator._cleanup_diffs()
        assert len(orchestrator._diff_log) == 3

    def test_get_diff_report_returns_copy(self):
        """get_diff_report should return a copy, not the internal list."""
        from unittest.mock import patch
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig()
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orchestrator = FastOrchestrator(cfg)

        orchestrator._log_diff(
            turn=1, action="test", changed=True, path="/tmp/test.png"
        )
        report = orchestrator.get_diff_report()
        assert report is not orchestrator._diff_log  # Should be a copy
        assert len(report) == 1
