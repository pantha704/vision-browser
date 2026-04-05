"""Tests for FastOrchestrator, CLI, and inject.js."""

from __future__ import annotations

import signal
from unittest.mock import ANY, MagicMock, patch

import pytest

from vision_browser.config import AppConfig
from vision_browser.fast_orchestrator import (
    ACTION_SCHEMA,
    FastOrchestrator,
    SYSTEM_PROMPT,
    USER_PROMPT,
)


# ── FastOrchestrator Tests ─────────────────────────────────────────


class TestFastOrchestratorInit:
    def test_init_with_config(self):
        """Test FastOrchestrator initialization with config."""
        cfg = AppConfig()
        with (
            patch("vision_browser.fast_orchestrator.PlaywrightBrowser") as mock_browser,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision,
            patch("signal.signal"),
        ):
            orchestrator = FastOrchestrator(cfg)
            assert orchestrator.cfg == cfg
            mock_browser.assert_called_once_with(cfg.browser)
            mock_vision.assert_called_once()

    def test_init_registers_signals(self):
        """Test signal handlers are registered."""
        cfg = AppConfig()
        with (
            patch("vision_browser.fast_orchestrator.PlaywrightBrowser"),
            patch("vision_browser.fast_orchestrator.VisionClient"),
            patch("signal.signal") as mock_signal,
        ):
            FastOrchestrator(cfg)
            assert mock_signal.call_count == 2
            mock_signal.assert_any_call(signal.SIGINT, ANY)
            mock_signal.assert_any_call(signal.SIGTERM, ANY)


class TestBuildElementList:
    def test_empty_legend(self):
        """Empty legend returns no-elements message."""
        cfg = AppConfig()
        with (
            patch("vision_browser.fast_orchestrator.PlaywrightBrowser"),
            patch("vision_browser.fast_orchestrator.VisionClient"),
            patch("signal.signal"),
        ):
            orchestrator = FastOrchestrator(cfg)
            result = orchestrator._build_element_list([], 5)
            assert "no interactive elements" in result

    def test_legend_within_max(self):
        """Legend within max_elements returns all items."""
        cfg = AppConfig()
        with (
            patch("vision_browser.fast_orchestrator.PlaywrightBrowser"),
            patch("vision_browser.fast_orchestrator.VisionClient"),
            patch("signal.signal"),
        ):
            orchestrator = FastOrchestrator(cfg)
            legend = ["[1] #search (combobox)", "[2] #submit (button)"]
            result = orchestrator._build_element_list(legend, 5)
            assert "[1]" in result
            assert "[2]" in result
            assert "more" not in result

    def test_legend_exceeds_max(self):
        """Legend exceeding max_elements is truncated with count."""
        cfg = AppConfig()
        with (
            patch("vision_browser.fast_orchestrator.PlaywrightBrowser"),
            patch("vision_browser.fast_orchestrator.VisionClient"),
            patch("signal.signal"),
        ):
            orchestrator = FastOrchestrator(cfg)
            legend = [f"[{i}] elem{i}" for i in range(1, 11)]
            result = orchestrator._build_element_list(legend, 3)
            lines = result.split("\n")
            assert len(lines) == 4  # 3 elements + "... and N more"
            assert "7 more" in lines[-1]


class TestRunLoop:
    def test_run_loop_single_turn_success(self):
        """Test run loop completes successfully in one turn."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision_cls,
            patch("vision_browser.fast_orchestrator.Console"),
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            mock_vision = MagicMock()
            mock_vision_cls.return_value = mock_vision

            mock_browser.screenshot.return_value = {
                "url": "https://example.com",
                "title": "Example",
                "legend": ["[1] #search (combobox)"],
                "refs": {"1": "#search"},
            }
            mock_browser.execute_batch.return_value = 1
            mock_browser.get_url.return_value = "https://example.com"
            mock_browser.get_title.return_value = "Example"
            mock_vision.analyze.return_value = {
                "actions": [{"action": "fill", "element": 1, "text": "hello"}],
                "done": True,
                "reasoning": "Filling search field",
            }

            orchestrator = FastOrchestrator(cfg)
            orchestrator._verify_completion = MagicMock(return_value=True)
            orchestrator._run_loop("Search for hello")

            mock_browser.screenshot.assert_called()
            mock_vision.analyze.assert_called()

    def test_run_loop_shutdown_requested(self):
        """Test run loop exits when shutdown requested."""
        cfg = AppConfig()
        with (
            patch("vision_browser.fast_orchestrator.PlaywrightBrowser"),
            patch("vision_browser.fast_orchestrator.VisionClient"),
            patch("vision_browser.fast_orchestrator.Console"),
            patch("signal.signal"),
        ):
            orchestrator = FastOrchestrator(cfg)
            orchestrator._shutdown_requested = True
            orchestrator._run_loop("test task")
            # Should exit immediately without calling screenshot

    def test_run_loop_consecutive_failures(self):
        """Test run loop detects consecutive failures on same URL."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision_cls,
            patch("vision_browser.fast_orchestrator.Console"),
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            mock_vision = MagicMock()
            mock_vision_cls.return_value = mock_vision

            mock_browser.screenshot.return_value = {
                "url": "https://example.com/error",
                "title": "Error",
                "legend": [],
                "refs": {},
            }
            mock_browser.get_url.return_value = "https://example.com/error"
            mock_browser.get_title.return_value = "Error"
            mock_browser.execute_batch.return_value = 0
            mock_vision.analyze.return_value = {
                "actions": [],
                "done": False,
                "reasoning": "No actions",
            }

            orchestrator = FastOrchestrator(cfg)
            orchestrator.cfg.orchestrator.max_turns = 4
            orchestrator._verify_completion = MagicMock(return_value=False)
            orchestrator._run_loop("test task")

            # Should detect consecutive failures
            assert orchestrator._shutdown_requested is False

    def test_run_loop_max_turns(self):
        """Test run loop stops at max turns."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision_cls,
            patch("vision_browser.fast_orchestrator.Console"),
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            mock_vision = MagicMock()
            mock_vision_cls.return_value = mock_vision

            mock_browser.screenshot.return_value = {
                "url": "https://example.com",
                "title": "Example",
                "legend": [],
                "refs": {},
            }
            mock_browser.get_url.return_value = "https://example.com"
            mock_browser.get_title.return_value = "Example"
            mock_browser.execute_batch.return_value = 0
            mock_vision.analyze.return_value = {
                "actions": [],
                "done": False,
                "reasoning": "Nothing to do",
            }

            orchestrator = FastOrchestrator(cfg)
            orchestrator.cfg.orchestrator.max_turns = 2
            orchestrator._verify_completion = MagicMock(return_value=False)
            orchestrator._run_loop("test task")

            assert mock_browser.screenshot.call_count == 2

    def test_run_loop_exception_handling(self):
        """Test run loop handles exceptions gracefully."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision_cls,
            patch("vision_browser.fast_orchestrator.Console"),
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            mock_vision = MagicMock()
            mock_vision_cls.return_value = mock_vision

            mock_browser.screenshot.side_effect = Exception("Browser crashed")
            mock_browser.is_alive.return_value = False

            orchestrator = FastOrchestrator(cfg)
            orchestrator.cfg.orchestrator.max_turns = 3
            orchestrator._run_loop("test task")

            # Should not raise, should exit loop
            mock_browser.is_alive.assert_called()


class TestVerifyCompletion:
    def test_verify_complete_returns_true(self):
        """Test verification returns True when model says complete."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision_cls,
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            mock_vision = MagicMock()
            mock_vision_cls.return_value = mock_vision

            mock_browser.screenshot.return_value = {
                "url": "https://example.com/results",
                "title": "Results",
                "legend": [],
                "refs": {},
            }
            mock_vision.analyze.return_value = {"complete": True, "reasoning": "Done"}

            orchestrator = FastOrchestrator(cfg)
            result = orchestrator._verify_completion("Search for something")
            assert result is True

    def test_verify_complete_exception_returns_true(self):
        """Test verification returns True (accepts) when verification fails."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient") as mock_vision_cls,
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            mock_vision = MagicMock()
            mock_vision_cls.return_value = mock_vision

            mock_browser.screenshot.side_effect = Exception("Verification failed")

            orchestrator = FastOrchestrator(cfg)
            result = orchestrator._verify_completion("Search for something")
            assert result is True  # Falls back to accepting


class TestClose:
    def test_close_delegates_to_browser(self):
        """Test close calls browser.close()."""
        cfg = AppConfig()
        with (
            patch(
                "vision_browser.fast_orchestrator.PlaywrightBrowser"
            ) as mock_browser_cls,
            patch("vision_browser.fast_orchestrator.VisionClient"),
            patch("signal.signal"),
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser

            orchestrator = FastOrchestrator(cfg)
            orchestrator.close()
            mock_browser.close.assert_called_once()


# ── CLI Tests ──────────────────────────────────────────────────────


class TestCLI:
    def test_main_argparse_task_required(self):
        """Test CLI requires task argument."""
        from vision_browser.cli import main

        with pytest.raises(SystemExit):
            with patch("sys.argv", ["vision-browser"]):
                main()

    def test_main_config_file_not_found_uses_defaults(self):
        """Test CLI uses defaults when config file not found."""
        from vision_browser.cli import main

        mock_cfg_instance = MagicMock()
        with (
            patch("sys.argv", ["vision-browser", "test", "--fast"]),
            patch("vision_browser.cli._setup_logging"),
            patch(
                "vision_browser.cli.shutil.which", return_value="/usr/bin/agent-browser"
            ),
            patch("vision_browser.cli.AppConfig") as mock_cfg,
            patch("vision_browser.fast_orchestrator.FastOrchestrator") as mock_fast,
            patch("vision_browser.orchestrator.Orchestrator"),
            patch("sys.exit"),
        ):
            mock_cfg.from_yaml.side_effect = FileNotFoundError
            mock_cfg.return_value = mock_cfg_instance
            mock_fast.return_value = MagicMock()

            main()

            mock_cfg.assert_called()  # Default config used

    def test_main_config_error_exits(self):
        """Test CLI exits on config error."""
        from vision_browser.cli import main

        with (
            patch("sys.argv", ["vision-browser", "test"]),
            patch("vision_browser.cli._setup_logging"),
            patch(
                "vision_browser.cli.shutil.which", return_value="/usr/bin/agent-browser"
            ),
            patch("vision_browser.cli.AppConfig") as mock_cfg,
        ):
            mock_cfg.from_yaml.side_effect = Exception("bad config")
            with pytest.raises(SystemExit):
                main()

    def test_main_agent_browser_missing(self):
        """Test CLI errors when agent-browser not on PATH."""
        from vision_browser.cli import main

        with (
            patch("sys.argv", ["vision-browser", "test"]),
            patch("vision_browser.cli._setup_logging"),
            patch("vision_browser.cli.shutil.which", return_value=None),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_config_override_brave(self):
        """Test CLI applies --brave config override."""
        from vision_browser.cli import main

        mock_cfg_instance = MagicMock()
        with (
            patch(
                "sys.argv",
                [
                    "vision-browser",
                    "test",
                    "--fast",
                    "--brave",
                ],
            ),
            patch("vision_browser.cli._setup_logging"),
            patch(
                "vision_browser.cli.shutil.which", return_value="/usr/bin/agent-browser"
            ),
            patch("vision_browser.cli.AppConfig") as mock_cfg,
            patch("vision_browser.fast_orchestrator.FastOrchestrator") as mock_fast,
            patch("vision_browser.orchestrator.Orchestrator"),
            patch("sys.exit"),
        ):
            mock_cfg.from_yaml.return_value = mock_cfg_instance
            mock_fast.return_value = MagicMock()

            main()

            assert mock_cfg_instance.browser.cdp_url == "http://localhost:9222"

    def test_main_config_override_session(self):
        """Test CLI applies --session config override."""
        from vision_browser.cli import main

        mock_cfg_instance = MagicMock()
        with (
            patch(
                "sys.argv",
                [
                    "vision-browser",
                    "test",
                    "--session",
                    "auth-session",
                ],
            ),
            patch("vision_browser.cli._setup_logging"),
            patch(
                "vision_browser.cli.shutil.which", return_value="/usr/bin/agent-browser"
            ),
            patch("vision_browser.cli.AppConfig") as mock_cfg,
            patch("vision_browser.fast_orchestrator.FastOrchestrator") as mock_fast,
            patch("vision_browser.orchestrator.Orchestrator"),
            patch("sys.exit"),
        ):
            mock_cfg.from_yaml.return_value = mock_cfg_instance
            mock_fast.return_value = MagicMock()

            main()

            assert mock_cfg_instance.browser.session_name == "auth-session"

    def test_main_verbose_flag(self):
        """Test CLI passes verbose flag to logging setup."""
        from vision_browser.cli import main

        with (
            patch("sys.argv", ["vision-browser", "test", "--verbose"]),
            patch("vision_browser.cli._setup_logging") as mock_logging,
            patch(
                "vision_browser.cli.shutil.which", return_value="/usr/bin/agent-browser"
            ),
            patch("vision_browser.cli.AppConfig") as mock_cfg,
            patch("vision_browser.fast_orchestrator.FastOrchestrator"),
            patch("vision_browser.orchestrator.Orchestrator"),
            patch("sys.exit"),
        ):
            mock_cfg.from_yaml.return_value = MagicMock()
            main()
            mock_logging.assert_called_once_with(verbose=True)


# ── Prompts and Schema Tests ───────────────────────────────────────


class TestPrompts:
    def test_system_prompt_defined(self):
        """Test system prompt is defined."""
        assert SYSTEM_PROMPT
        assert "browser automation agent" in SYSTEM_PROMPT.lower()

    def test_user_prompt_template(self):
        """Test user prompt can be formatted."""
        result = USER_PROMPT.format(
            task="Search for cats",
            url="https://example.com",
            title="Example",
            element_list="[1] #search (combobox)",
        )
        assert "Search for cats" in result
        assert "https://example.com" in result

    def test_action_schema_structure(self):
        """Test action schema has required fields."""
        assert "actions" in ACTION_SCHEMA["required"]
        assert "done" in ACTION_SCHEMA["required"]
        assert "reasoning" in ACTION_SCHEMA["required"]
        assert ACTION_SCHEMA["properties"]["actions"]["type"] == "array"
