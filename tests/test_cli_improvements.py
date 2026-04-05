"""Tests for CLI Improvements — progress indicators, error messages, task summary, Rich fallback."""

from __future__ import annotations

import pytest


class TestTaskSummary:
    """Test CLI-03: Task summary report."""

    def test_get_task_summary_initial_state(self):
        """Fresh orchestrator has zeroed metrics."""
        from unittest.mock import patch
        from vision_browser.config import AppConfig
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig()
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orch = FastOrchestrator(cfg)

        summary = orch.get_task_summary()
        assert summary["status"] == "not_started"
        assert summary["turns"] == 0
        assert summary["total_actions"] == 0
        assert summary["succeeded_actions"] == 0
        assert summary["failed_actions"] == 0
        assert summary["final_url"] == ""

    def test_get_task_summary_after_run(self):
        """After run, summary reflects task state."""
        from unittest.mock import patch, MagicMock
        from vision_browser.config import AppConfig
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig()
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orch = FastOrchestrator(cfg)

        orch._task_status = "complete"
        orch._task_turns = 5
        orch._task_total_actions = 8
        orch._task_succeeded_actions = 7
        orch._task_failed_actions = 1
        orch._task_final_url = "https://example.com"

        summary = orch.get_task_summary()
        assert summary["status"] == "complete"
        assert summary["turns"] == 5
        assert summary["total_actions"] == 8
        assert summary["succeeded_actions"] == 7
        assert summary["failed_actions"] == 1
        assert summary["final_url"] == "https://example.com"
        assert summary["elapsed_seconds"] >= 0

    def test_print_task_summary_outputs_something(self, capsys):
        """print_task_summary should output formatted text."""
        from unittest.mock import patch
        from vision_browser.config import AppConfig
        from vision_browser.fast_orchestrator import FastOrchestrator

        cfg = AppConfig()
        with patch("vision_browser.fast_orchestrator.PlaywrightBrowser"):
            orch = FastOrchestrator(cfg)

        orch._task_status = "complete"
        orch._task_turns = 3
        orch.print_task_summary()

        captured = capsys.readouterr()
        assert "Task Summary" in captured.out
        assert "complete" in captured.out


class TestRichFallback:
    """Test CLI-04: Graceful fallback when Rich is unavailable."""

    def test_fallback_console_strips_markup(self):
        """Fallback console should strip Rich markup from output."""
        import re
        from vision_browser import cli

        # Save original HAS_RICH
        original_has_rich = cli.HAS_RICH

        # Force fallback
        cli.HAS_RICH = False
        fallback = cli._FallbackConsole()

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            fallback.print("[bold red]Error:[/bold red] Something went wrong")
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            cli.HAS_RICH = original_has_rich

        # Should NOT contain Rich markup markers
        assert "[bold" not in output
        assert "[/bold" not in output
        assert "Error:" in output
        assert "Something went wrong" in output


class TestUserErrorMessages:
    """Test CLI-02: Human-readable error messages."""

    def test_print_user_error_shows_message(self, capsys):
        """_print_user_error should display the message."""
        from vision_browser.cli import _print_user_error

        _print_user_error("Test error", "Try again")
        captured = capsys.readouterr()
        assert "Test error" in captured.out
        assert "Try again" in captured.out

    def test_print_user_error_without_suggestion(self, capsys):
        """_print_user_error works without suggestion."""
        from vision_browser.cli import _print_user_error

        _print_user_error("Just an error")
        captured = capsys.readouterr()
        assert "Just an error" in captured.out


class TestCLIConfigOverrides:
    """Test CLI config defaults for new fields."""

    def test_orchestrator_config_has_diff_fields(self):
        """OrchestratorConfig should have new diff-related fields."""
        from vision_browser.config import OrchestratorConfig

        cfg = OrchestratorConfig()
        assert hasattr(cfg, "auto_diff_screenshots")
        assert hasattr(cfg, "diff_threshold")
        assert hasattr(cfg, "diff_max_retain")
        assert cfg.auto_diff_screenshots is False
        assert cfg.diff_threshold == 0.01
        assert cfg.diff_max_retain == 10
