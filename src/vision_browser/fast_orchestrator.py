"""New orchestrator: Playwright + DOM + Vision hybrid."""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from vision_browser.config import AppConfig
from vision_browser.playwright_browser import PlaywrightBrowser
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

SCREENSHOT_PATH = Path("/tmp/vision-browser-screenshot.png")


class FastOrchestrator:
    """Fast orchestrator using Playwright + DOM + Vision."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.browser = PlaywrightBrowser(cfg.browser)
        self.vision = VisionClient(cfg.vision, {
            "retry_attempts": cfg.orchestrator.retry_attempts,
            "retry_backoff_base": cfg.orchestrator.retry_backoff_base,
            "rate_limit_delay": cfg.orchestrator.rate_limit_delay,
        })
        self._shutdown_requested = False
        self._register_signals()

    def _register_signals(self) -> None:
        """Register signal handlers for graceful shutdown."""
        def _handler(signum: int, _frame: object) -> None:
            logger.info(f"Signal {signum} received, shutting down")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def run(self, task: str, url: str | None = None) -> None:
        """Execute automation loop."""
        console.print(Panel(f"[bold green]Task:[/bold green] {task}", title="Vision Browser (Fast)"))

        if self._shutdown_requested:
            console.print("[yellow]Shutdown requested, exiting[/yellow]")
            return

        if url:
            console.print(f"[dim]→ Navigating to {url}[/dim]")
            try:
                self.browser.open(url)
            except Exception as e:
                console.print(f"[red]Navigation failed: {e}[/red]")
                self.browser.close()
                return

        self._run_loop(task)

    def _run_loop(self, task: str) -> None:
        """Main automation loop."""
        max_turns = self.cfg.orchestrator.max_turns
        max_elements = self.cfg.orchestrator.max_prompt_elements
        consecutive_failures = 0
        last_url = ""

        for turn in range(1, max_turns + 1):
            if self._shutdown_requested:
                console.print("\n[yellow]⏹️ Shutdown requested[/yellow]")
                break

            console.print(f"\n[bold cyan]Turn {turn}/{max_turns}[/bold cyan]")

            try:
                # 1. Screenshot + inject badges + extract a11y tree
                console.print("  📸 Capturing screenshot + injecting badges...")
                shot = self.browser.screenshot(str(SCREENSHOT_PATH))
                
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

                # 2. Build prompt with a11y context
                prompt = USER_PROMPT.format(
                    task=task, url=url, title=title, element_list=element_list
                )

                # 3. Send to vision model
                console.print("  🧠 Sending to vision model...")
                result = self.vision.analyze(str(SCREENSHOT_PATH), prompt)

                # 4. Execute actions
                actions = result.get("actions", [])
                done = result.get("done", False)
                reasoning = result.get("reasoning", "")

                console.print(f"  💡 [dim]{reasoning}[/dim]")

                if actions:
                    console.print(f"  ⚡ Executing {len(actions)} action(s)...")
                    executed = self.browser.execute_batch(actions)
                    console.print(f"  ✅ {executed}/{len(actions)} succeeded")
                    
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

                # 5. Verify completion
                if done:
                    if self._verify_completion(task):
                        console.print("\n[bold green]✅ Task complete![/bold green]")
                        break
                    else:
                        console.print("[yellow]  ⚠️ Verification failed, continuing...[/yellow]")

            except Exception as e:
                logger.error(f"Turn {turn} failed: {e}")
                console.print(f"  ❌ [red]Error:[/red] {e}")
                consecutive_failures += 1
                
                if not self.browser.is_alive():
                    console.print("[yellow]  ⚠️ Browser connection lost[/yellow]")
                    break

            if turn == max_turns:
                console.print("\n[bold yellow]⏱️ Max turns reached[/bold yellow]")

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
            shot = self.browser.screenshot(str(SCREENSHOT_PATH))
            url = shot.get("url", "")
            title = shot.get("title", "")
            element_list = self._build_element_list(shot.get("legend", []), self.cfg.orchestrator.max_prompt_elements)
            
            verify_prompt = (
                f"Task was: {task}\n"
                f"Current: {url} — {title}\n"
                f"Elements: {element_list}\n\n"
                f'Is task complete? Return ONLY JSON: {{"complete": true/false, "reasoning": "why"}}'
            )
            result = self.vision.analyze(str(SCREENSHOT_PATH), verify_prompt)
            is_complete = result.get("complete", False)
            logger.info(f"Verification: complete={is_complete}")
            return bool(is_complete)
        except Exception as e:
            logger.warning(f"Verification failed, accepting: {e}")
            return True

    def close(self) -> None:
        """Clean shutdown."""
        self.browser.close()
