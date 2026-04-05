"""New orchestrator: Playwright + DOM + Vision hybrid."""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from vision_browser.config import AppConfig
from vision_browser.diff_screenshot import DifferentialScreenshot
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.screenshot_manager import ScreenshotManager
from vision_browser.vision import VisionClient

logger = logging.getLogger(__name__)
console = Console()

SYSTEM_PROMPT = """\
You are a browser automation agent. Analyze the screenshot and accessibility tree, then return actions as JSON.

RULES:
1. ONLY use element numbers that appear in the available elements list.
2. Element numbers NOT in the list DO NOT EXIST.
3. Return ONLY valid JSON. No markdown, no explanation.
4. If on search homepage: use "fill" on the search bar element, then "press" Enter.
5. If on search results: click the most relevant result link.
6. Set "done": true ONLY when task is complete.

RESPONSE FORMAT:
{"actions": [{"action": "fill", "element": 9, "text": "query"}, {"action": "press", "key": "Enter"}], "done": false, "reasoning": "why"}
"""

USER_PROMPT = """\
TASK: {task}

URL: {url}
TITLE: {title}

ELEMENTS:
{element_list}

Return ONLY JSON.
"""

# Global constant removed - now managed by ScreenshotManager

# JSON schema for structured output
ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["click", "fill", "press", "scroll", "wait", "navigate"]
                    },
                    "element": {"type": "integer"},
                    "text": {"type": "string"},
                    "key": {"type": "string"},
                    "direction": {"type": "string", "enum": ["up", "down"]},
                    "amount": {"type": "integer"},
                    "url": {"type": "string", "format": "uri"}
                },
                "required": ["action"],
                "additionalProperties": False
            }
        },
        "done": {"type": "boolean"},
        "reasoning": {"type": "string"}
    },
    "required": ["actions", "done", "reasoning"],
    "additionalProperties": False
}


class FastOrchestrator:
    """Fast orchestrator using Playwright + DOM + Vision."""

    def __init__(self, cfg: AppConfig, keep_screenshots: bool = False):
        self.cfg = cfg
        self.browser = PlaywrightBrowser(cfg.browser)
        self.vision = VisionClient(cfg.vision, {
            "retry_attempts": cfg.orchestrator.retry_attempts,
            "retry_backoff_base": cfg.orchestrator.retry_backoff_base,
            "rate_limit_delay": cfg.orchestrator.rate_limit_delay,
        })
        self.screenshots = ScreenshotManager(keep=keep_screenshots, max_retain=20)
        self._shutdown_requested = False

        # Differential screenshot integration (opt-in)
        diff_enabled = cfg.orchestrator.auto_diff_screenshots or cfg.orchestrator.diff_mode
        self.diff_screenshot: DifferentialScreenshot | None = None
        if diff_enabled:
            self.diff_screenshot = DifferentialScreenshot(
                threshold=cfg.orchestrator.diff_threshold
            )
        self._diff_log: list[dict] = []  # Diff capture log for debugging

        # Task metrics for CLI summary
        self._task_start_time: float = 0.0
        self._task_total_actions: int = 0
        self._task_succeeded_actions: int = 0
        self._task_failed_actions: int = 0
        self._task_turns: int = 0
        self._task_final_url: str = ""
        self._task_status: str = "not_started"

        self._register_signals()

    def _register_signals(self) -> None:
        """Register signal handlers for graceful shutdown and screenshot cleanup."""
        def _handler(signum: int, _frame: object) -> None:
            logger.info(f"Signal {signum} received, shutting down")
            self._shutdown_requested = True
            self.screenshots.cleanup()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def close(self) -> None:
        """Clean shutdown with screenshot cleanup."""
        self.browser.close()
        self.screenshots.cleanup()

    def run(self, task: str, url: str | None = None) -> None:
        """Execute automation loop."""
        import time
        self._task_start_time = time.monotonic()
        self._task_status = "running"
        console.print(Panel(f"[bold green]Task:[/bold green] {task}", title="Vision Browser (Fast)"))

        if self._shutdown_requested:
            console.print("[yellow]Shutdown requested, exiting[/yellow]")
            self._task_status = "interrupted"
            return

        if url:
            console.print(f"[dim]→ Navigating to {url}[/dim]")
            try:
                self.browser.open(url)
            except Exception as e:
                console.print(f"[red]Navigation failed: {e}[/red]")
                self._task_status = "failed"
                self._task_final_url = url
                self.close()
                return

        self._run_loop(task)
        self.close()

    def _run_loop(self, task: str) -> None:
        """Main automation loop."""
        max_turns = self.cfg.orchestrator.max_turns
        max_elements = self.cfg.orchestrator.max_prompt_elements
        consecutive_failures = 0
        last_url = ""

        for turn in range(1, max_turns + 1):
            self._task_turns = turn
            if self._shutdown_requested:
                console.print("\n[yellow]⏹️ Shutdown requested[/yellow]")
                break

            console.print(f"\n[bold cyan]Turn {turn}/{max_turns}[/bold cyan]")

            try:
                # 1. Screenshot + inject badges + extract a11y tree
                console.print("  📸 Capturing screenshot + injecting badges...")
                shot_path = self.screenshots.next_path()
                shot = self.browser.screenshot(str(shot_path))
                
                url = shot.get("url", "") or self.browser.get_url()
                title = shot.get("title", "") or self.browser.get_title()
                element_list = self._build_element_list(shot.get("legend", []), max_elements)

                # Detect same-URL loop
                if url == last_url:
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        console.print(f"[yellow]  ⚠️ Stuck on same URL. Forcing strategy change.[/yellow]")
                else:
                    consecutive_failures = 0
                last_url = url

                console.print(f"  📍 {url} — {title}")
                console.print(f"  📋 Found {len(shot.get('refs', {}))} interactive elements")

                # 1.5 Differential screenshot check (before analysis)
                diff_changed = False
                if self.diff_screenshot is not None:
                    diff_changed = self.diff_screenshot.has_changed(str(shot_path))
                    if diff_changed:
                        logger.debug(f"Screenshot changed at turn {turn}")
                    else:
                        logger.debug(f"Screenshot unchanged at turn {turn}")
                    self._log_diff(turn=turn, action="pre-analysis", changed=diff_changed, path=str(shot_path))
                    # Cleanup old diffs
                    self._cleanup_diffs()

                # 2. Build prompt with a11y context
                prompt = USER_PROMPT.format(
                    task=task, url=url, title=title, element_list=element_list
                )

                # 3. Send to vision model with structured output schema
                console.print("  🧠 Sending to vision model...")
                result = self.vision.analyze(
                    str(self.screenshots.current_path),
                    prompt,
                    schema=ACTION_SCHEMA
                )

                # 4. Execute actions
                actions = result.get("actions", [])
                done = result.get("done", False)
                reasoning = result.get("reasoning", "")

                console.print(f"  💡 [dim]{reasoning}[/dim]")

                if actions:
                    console.print(f"  ⚡ Executing {len(actions)} action(s)...")
                    executed = self.browser.execute_batch(actions)
                    console.print(f"  ✅ {executed}/{len(actions)} succeeded")

                    self._task_total_actions += len(actions)
                    self._task_succeeded_actions += executed
                    self._task_failed_actions += (len(actions) - executed)

                    if executed > 0:
                        consecutive_failures = 0
                else:
                    # No valid actions - try auto-fill fallback for Google homepage
                    if "/search" not in url and "google" in url.lower():
                        console.print("[yellow]  🔄 No actions from model. Auto-filling search bar...[/yellow]")
                        # Find combobox element
                        for num, legend in enumerate(shot.get("legend", []), 1):
                            if "combobox" in legend.lower() or "search" in legend.lower():
                                try:
                                    import re
                                    query_match = re.search(r"['\"]([^'\"]+)['\"]", task)
                                    query = query_match.group(1) if query_match else task[:50]
                                    console.print(f"[yellow]   Filling with: {query}[/yellow]")
                                    self.browser.fill(num, query)
                                    self.browser.press("Enter")
                                    consecutive_failures = 0
                                    break
                                except Exception as e:
                                    logger.debug(f"Auto-fill failed: {e}")
                    else:
                        consecutive_failures += 1

                # 4.5 Post-action differential screenshot
                if self.diff_screenshot is not None and actions:
                    post_shot_path = self.screenshots.next_path()
                    self.browser.screenshot(str(post_shot_path))
                    post_changed = self.diff_screenshot.has_changed(str(post_shot_path))
                    self._log_diff(
                        turn=turn, action="post-execution", changed=post_changed,
                        path=str(post_shot_path), actions_executed=executed if 'executed' in dir() else 0,
                    )
                    self._cleanup_diffs()

                # 5. Verify completion
                if done:
                    if self._verify_completion(task):
                        console.print("\n[bold green]✅ Task complete![/bold green]")
                        self._task_status = "complete"
                        self._task_final_url = url
                        break
                    else:
                        console.print("[yellow]  ⚠️ Verification failed, continuing...[/yellow]")

            except Exception as e:
                logger.error(f"Turn {turn} failed: {e}")
                console.print(f"  ❌ [red]Error:[/red] {e}")
                consecutive_failures += 1

                if not self.browser.is_alive():
                    console.print("[yellow]  ⚠️ Browser connection lost[/yellow]")
                    self._task_status = "browser_crashed"
                    break

            if turn == max_turns:
                console.print("\n[bold yellow]⏱️ Max turns reached[/bold yellow]")
                self._task_status = "max_turns_reached"
                self._task_final_url = url

    def _build_element_list(self, legend: list[str], max_elements: int) -> str:
        """Build element list from badge legend."""
        if not legend:
            return "  (no interactive elements found)"
        
        elements = legend[:max_elements]
        if len(legend) > max_elements:
            elements.append(f"  ... and {len(legend) - max_elements} more")
        
        return "\n".join(elements)

    def _verify_completion(self, task: str) -> bool:
        """Verify task is actually complete."""
        try:
            shot_path = self.screenshots.next_path()
            shot = self.browser.screenshot(str(shot_path))
            url = shot.get("url", "")
            title = shot.get("title", "")
            element_list = self._build_element_list(shot.get("legend", []), self.cfg.orchestrator.max_prompt_elements)
            
            verify_prompt = (
                f"Task was: {task}\n"
                f"Current: {url} — {title}\n"
                f"Elements: {element_list}\n\n"
                f'Is task complete? Return ONLY JSON: {{"complete": true/false, "reasoning": "why"}}'
            )
            result = self.vision.analyze(str(shot_path), verify_prompt)
            is_complete = result.get("complete", False)
            logger.info(f"Verification: complete={is_complete}")
            return bool(is_complete)
        except Exception as e:
            logger.warning(f"Verification failed, accepting: {e}")
            return True

    # ── Differential Screenshot Helpers ──────────────────────────────

    def _log_diff(self, turn: int, action: str, changed: bool, path: str, **extra: object) -> None:
        """Log a differential screenshot event."""
        import time
        entry: dict[str, object] = {
            "turn": turn,
            "action": action,
            "changed": changed,
            "path": path,
            "timestamp": time.time(),
            **extra,
        }
        self._diff_log.append(entry)
        logger.debug(f"Diff log: turn={turn} {action} changed={changed}")

    def _cleanup_diffs(self) -> None:
        """Remove oldest diff log entries beyond the configured limit."""
        max_retain = self.cfg.orchestrator.diff_max_retain
        if len(self._diff_log) > max_retain:
            removed = len(self._diff_log) - max_retain
            self._diff_log = self._diff_log[-max_retain:]
            logger.debug(f"Cleaned up {removed} old diff entries")

    def get_diff_report(self) -> list[dict]:
        """Return the differential screenshot log for debugging."""
        return list(self._diff_log)

    def get_task_summary(self) -> dict:
        """Return task execution summary for CLI reporting."""
        import time
        elapsed = time.monotonic() - self._task_start_time if self._task_start_time else 0
        return {
            "status": self._task_status,
            "turns": self._task_turns,
            "total_actions": self._task_total_actions,
            "succeeded_actions": self._task_succeeded_actions,
            "failed_actions": self._task_failed_actions,
            "elapsed_seconds": round(elapsed, 1),
            "final_url": self._task_final_url,
        }

    def print_task_summary(self) -> None:
        """Print a formatted task summary to the console."""
        summary = self.get_task_summary()
        status_icon = {"complete": "✅", "failed": "❌", "interrupted": "⏹️"}.get(summary["status"], "⏱️")

        lines = [
            "",
            "── Task Summary " + "─" * 30,
            f"  Status: {status_icon} {summary['status']}",
            f"  Turns: {summary['turns']}",
            f"  Actions: {summary['total_actions']} ({summary['succeeded_actions']} succeeded, {summary['failed_actions']} failed)",
            f"  Time: {summary['elapsed_seconds']}s",
        ]
        if summary["final_url"]:
            lines.append(f"  Final URL: {summary['final_url']}")
        lines.append("─" * 50)

        for line in lines:
            console.print(line)

    def close(self) -> None:
        """Clean shutdown with screenshot cleanup."""
        self.browser.close()
        self.screenshots.cleanup()
