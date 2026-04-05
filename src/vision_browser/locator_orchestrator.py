"""Locator-based orchestrator using Playwright semantic locators.

Uses indexed elements with CSS selectors so the model references
elements by number (e.g., click: 5) instead of guessing strategies.
Includes action result feedback for the next turn.
"""

from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel

from vision_browser.config import AppConfig
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.vision import VisionClient

logger = logging.getLogger(__name__)
console = Console()

# System prompt — model references elements by INDEX number
LOCATOR_SYSTEM_PROMPT = """\
You are a browser automation agent. The page state is provided as a numbered list of interactive elements with their CSS selectors, roles, and visible text.

TASK FORMAT:
- Elements are numbered [1], [2], [3], etc.
- Each element shows: role, visible text/label, and a CSS selector.

AVAILABLE ACTIONS:
- click: Click element by index (e.g., {"action": "click", "element": 5})
- fill: Fill input by index with text (e.g., {"action": "fill", "element": 3, "text": "hello"})
- click_first_video: Click the first video result on a YouTube search page (e.g., {"action": "click_first_video"})
- press: Press a key (e.g., {"action": "press", "key": "Enter"})
- scroll: Scroll page (e.g., {"action": "scroll", "direction": "down", "amount": 500})
- navigate: Go to a URL (e.g., {"action": "navigate", "url": "https://example.com"})
- wait: Wait for page to load (e.g., {"action": "wait"})
- type: Type text into element by index (e.g., {"action": "type", "element": 3, "text": "hello"})

RULES:
1. Use the ELEMENT NUMBER to reference elements — do NOT guess selectors.
2. If you need to search: fill the search input index, then press Enter.
3. If you need to click a link: use the element number.
4. Return ONLY valid JSON. No markdown, no explanation.
5. Set "done" to true ONLY when the task is fully complete (URL changed, content loaded).

RESPONSE FORMAT:
{"actions": [{"action": "fill", "element": 3, "text": "query"}, {"action": "press", "key": "Enter"}], "done": false, "reasoning": "why"}
"""

LOCATOR_USER_PROMPT = """\
TASK: {task}

CURRENT PAGE:
URL: {url}
TITLE: {title}

INTERACTIVE ELEMENTS:
{element_list}

{feedback_text}

Return ONLY JSON with actions to accomplish the task.
"""


class LocatorOrchestrator:
    """Fast orchestrator using Playwright indexed elements.

    Strategy:
    1. Extract all interactive elements with CSS selectors (instant, JS eval)
    2. Build numbered element list for model prompt
    3. Model returns actions referencing element by index
    4. Execute via CSS selector directly (no Vision API for finding elements)
    5. Report success/failure back to model next turn
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.browser = PlaywrightBrowser(cfg.browser)
        self.vision = VisionClient(
            cfg.vision,
            {
                "retry_attempts": cfg.orchestrator.retry_attempts,
                "retry_backoff_base": cfg.orchestrator.retry_backoff_base,
                "rate_limit_delay": cfg.orchestrator.rate_limit_delay,
            },
        )
        self._shutdown_requested = False
        self._error_count = 0
        self._last_action_key = ""
        self._same_action_count = 0
        self._initial_url: str = ""
        self._visited_watch_url: bool = False  # Track if we ever hit /watch

        # Task metrics
        self._task_start_time: float = 0.0
        self._task_total_actions: int = 0
        self._task_succeeded_actions: int = 0
        self._task_failed_actions: int = 0
        self._task_turns: int = 0
        self._task_final_url: str = ""
        self._task_status: str = "not_started"

    def run(self, task: str, url: str | None = None) -> None:
        """Execute automation loop."""
        self._task_start_time = time.monotonic()
        self._task_status = "running"
        console.print(
            Panel(
                f"[bold green]Task:[/bold green] {task}",
                title="Vision Browser (Locator Mode)",
            )
        )

        if url:
            console.print(f"[dim]→ Navigating to {url}[/dim]")
            try:
                self.browser.open(url)
                self._initial_url = url
            except Exception as e:
                console.print(f"[red]Navigation failed: {e}[/red]")
                self._task_status = "failed"
                self._task_final_url = url
                self._print_summary()
                self.close()
                return
        else:
            try:
                self._initial_url = self.browser.get_url()
            except Exception:
                self._initial_url = ""

        self._run_loop(task)
        self._print_summary()
        self.close()

    def close(self) -> None:
        """Clean shutdown."""
        self.browser.close()

    def _run_loop(self, task: str) -> None:
        """Main automation loop."""
        max_turns = self.cfg.orchestrator.max_turns
        consecutive_failures = 0
        last_url = ""
        action_feedback: list[str] = []

        for turn in range(1, max_turns + 1):
            self._task_turns = turn
            if self._shutdown_requested:
                console.print("\n[yellow]⏹️ Shutdown requested[/yellow]")
                break

            console.print(f"\n[bold cyan]Turn {turn}/{max_turns}[/bold cyan]")

            url = ""
            title = ""

            try:
                # 1. Get page state (instant JS eval, no screenshot)
                console.print("  📋 Getting page state...")
                elements = self.browser.get_interactive_elements()
                url = self.browser.get_url() or ""
                title = self.browser.get_title() or ""
                element_count = len(elements)

                # Build numbered element list
                element_list = self._format_elements(elements)

                # 2. Check if task is complete via URL/content detection
                if turn > 1 and last_url and self._is_task_complete(task, url, last_url):
                    console.print("\n[bold green]✅ Task complete![/bold green]")
                    self._task_status = "complete"
                    self._task_final_url = url
                    break

                # Detect same-URL loop (allow 3 turns for multi-step tasks)
                if url == last_url:
                    consecutive_failures += 1
                    if consecutive_failures >= 4:
                        console.print(
                            "[yellow]  ⚠️ Stuck on same URL. Falling back to Vision mode.[/yellow]"
                        )
                        return self._fallback_to_vision(task, url, title)
                else:
                    consecutive_failures = 0
                last_url = url

                console.print(f"  📍 {url} — {title}")
                console.print(f"  📋 Found {element_count} interactive elements")

                # 3. Build prompt with action feedback
                feedback_text = ""
                if action_feedback:
                    feedback_text = (
                        "PREVIOUS ACTION RESULTS:\n"
                        + "\n".join(f"  - {f}" for f in action_feedback)
                        + "\n"
                    )
                    action_feedback = []  # Clear after showing

                prompt = LOCATOR_USER_PROMPT.format(
                    task=task,
                    url=url,
                    title=title,
                    element_list=element_list,
                    feedback_text=feedback_text,
                )

                # 4. Get actions from Vision API (text-only, fast)
                console.print("  🧠 Planning actions...")
                result = self.vision.analyze_page(
                    url=url,
                    title=title,
                    elements=elements,
                    task=task,
                    system_prompt=LOCATOR_SYSTEM_PROMPT,
                    prompt_override=prompt,
                )

                # 5. Execute actions using indexed CSS selectors
                actions = result.get("actions", [])
                done = result.get("done", False)
                reasoning = result.get("reasoning", "")

                console.print(f"  💡 [dim]{reasoning}[/dim]")

                if actions:
                    console.print(f"  ⚡ Executing {len(actions)} action(s)...")
                    success_count, feedback = self._execute_locator_actions(
                        actions, elements
                    )
                    action_feedback = feedback
                    console.print(f"  ✅ {success_count}/{len(actions)} succeeded")

                    self._task_total_actions += len(actions)
                    self._task_succeeded_actions += success_count
                    self._task_failed_actions += len(actions) - success_count

                    # Same-action loop detection
                    action_key = json.dumps(actions, sort_keys=True)
                    if action_key == self._last_action_key:
                        self._same_action_count += 1
                        if self._same_action_count >= 3:
                            console.print(
                                "[yellow]  ⚠️ Same action repeated 3x — resetting context[/yellow]"
                            )
                            self._same_action_count = 0
                            action_feedback.append(
                                "⚠️ Same action repeated — try a different approach"
                            )
                    else:
                        self._last_action_key = action_key
                        self._same_action_count = 0

                    if success_count > 0:
                        consecutive_failures = 0
                else:
                    console.print(
                        "[yellow]  ⚠️ No actions returned from model[/yellow]"
                    )
                    consecutive_failures += 1
                    action_feedback.append(
                        "⚠️ No actions returned — try again with different element references"
                    )

                # 6. Check done flag from model
                if done and self._is_task_complete(task, url, last_url or url):
                    console.print("\n[bold green]✅ Task complete![/bold green]")
                    self._task_status = "complete"
                    self._task_final_url = url
                    break

            except Exception as e:
                console.print(f"  ❌ [red]Error:[/red] {e}")
                self._error_count += 1
                consecutive_failures += 1
                action_feedback.append(f"❌ Error: {e}")

                if not self.browser.is_alive():
                    console.print("[yellow]  ⚠️ Browser connection lost[/yellow]")
                    self._task_status = "browser_crashed"
                    break

            if turn == max_turns:
                console.print("\n[bold yellow]⏱️ Max turns reached[/bold yellow]")
                self._task_status = "max_turns_reached"
                self._task_final_url = url

    def _format_elements(self, elements: list[dict], max_count: int = 40) -> str:
        """Format interactive elements as numbered list with CSS selectors."""
        if not elements:
            return "  (no interactive elements found)"

        lines = []
        for i, el in enumerate(elements[:max_count], 1):
            role = el.get("role", "")
            name = el.get("name", "")
            el_type = el.get("type", "")
            selector = el.get("selector", "")
            href = el.get("href", "")

            # Build description
            parts = []
            if role:
                parts.append(f"role={role}")
            if name:
                short_name = name[:50] + "..." if len(name) > 50 else name
                parts.append(f'"{short_name}"')
            if el_type:
                parts.append(f"type={el_type}")
            if href and "/watch" in href:
                parts.append("🎥 video link")
            if selector:
                parts.append(f"→ {selector}")

            desc = " ".join(parts) if parts else "unknown"
            lines.append(f"  [{i}] {desc}")

        if len(elements) > max_count:
            lines.append(f"  ... and {len(elements) - max_count} more")

        return "\n".join(lines)

    def _execute_locator_actions(
        self, actions: list[dict], elements: list[dict]
    ) -> tuple[int, list[str]]:
        """Execute actions using indexed element references.

        Returns (success_count, feedback_list).
        """
        success = 0
        feedback: list[str] = []

        for action in actions:
            act = action.get("action", "")
            element_idx = action.get("element")

            # Resolve element index to CSS selector
            selector: str | None = None
            el_info = ""
            if element_idx is not None and 1 <= element_idx <= len(elements):
                el = elements[element_idx - 1]
                selector = el.get("selector") or el.get("css")
                role = el.get("role", "")
                name = el.get("name", "")
                el_info = f'element [{element_idx}] ({role}: "{name}")'
            else:
                el_info = f'element index {element_idx} (out of range 1-{len(elements)})'

            try:
                match act:
                    case "click":
                        if selector:
                            self.browser._page.click(selector, timeout=30000)
                            success += 1
                            feedback.append(f"✅ Clicked {el_info}")
                            try:
                                self.browser._page.wait_for_load_state(
                                    "domcontentloaded", timeout=10000
                                )
                            except Exception:
                                pass
                        else:
                            # Fallback: try to find element by text/href
                            feedback.append(f"❌ No selector for {el_info}")

                    case "click_first_video":
                        # Special action: find and click the first video result
                        # Looks for links with /watch in href
                        video_clicked = self._click_first_video()
                        if video_clicked:
                            success += 1
                            feedback.append("✅ Clicked first video result")
                        else:
                            feedback.append("❌ No video found on page")

                    case "fill":
                        text = action.get("text", "")
                        if selector:
                            self.browser._page.fill(selector, text, timeout=30000)
                            success += 1
                            feedback.append(f"✅ Filled {el_info} with: {text[:40]}")
                        else:
                            feedback.append(f"❌ No selector for {el_info}")

                    case "press":
                        key = action.get("key", "Enter")
                        self.browser._page.keyboard.press(key)
                        success += 1
                        feedback.append(f"✅ Pressed {key}")
                        if key == "Enter":
                            try:
                                self.browser._page.wait_for_load_state(
                                    "domcontentloaded", timeout=10000
                                )
                            except Exception:
                                pass

                    case "scroll":
                        direction = action.get("direction", "down")
                        amount = action.get("amount", 500)
                        self.browser.scroll(direction, amount)
                        success += 1
                        feedback.append(f"✅ Scrolled {direction} by {amount}px")

                    case "navigate":
                        nav_url = action.get("url", "")
                        if nav_url.startswith(("http://", "https://")):
                            self.browser.open(nav_url)
                            success += 1
                            feedback.append(f"✅ Navigated to {nav_url[:60]}")

                    case "wait":
                        try:
                            self.browser._page.wait_for_load_state(
                                "domcontentloaded", timeout=10000
                            )
                            success += 1
                            feedback.append("✅ Waited for page load")
                        except Exception:
                            feedback.append("⚠️ Wait timed out")

                    case "type":
                        text = action.get("text", "")
                        if selector:
                            self.browser._page.click(selector, timeout=10000)
                            self.browser._page.keyboard.type(text)
                            success += 1
                            feedback.append(f"✅ Typed: {text[:40]}")
                        else:
                            feedback.append(f"❌ No selector for {el_info}")

                    case _:
                        feedback.append(f"❌ Unknown action: {act}")

            except Exception as e:
                logger.debug(f"Action failed: {action} - {e}")
                feedback.append(f"❌ Failed {el_info}: {str(e)[:80]}")

        return success, feedback

    def _click_first_video(self) -> bool:
        """Find and click the first video result on a search results page.

        Looks for <a> elements with /watch in href that are visible.
        """
        try:
            # Find all video links and click the first visible one
            result = self.browser._page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href*="/watch"]'));
                for (const link of links) {
                    const rect = link.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 20) {
                        // Check it's not in the sidebar/header (main content area)
                        if (rect.top > 100) {
                            return { href: link.href, text: link.textContent?.trim().slice(0, 80) };
                        }
                    }
                }
                return null;
            }""")

            if result:
                self.browser._page.click(f'a[href*="/watch"]:has-text("{result.get("text", "")[:30]}")', timeout=15000)
                try:
                    self.browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                return True

            # Fallback: click any /watch link
            self.browser._page.locator('a[href*="/watch"]').first.click(timeout=15000)
            try:
                self.browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.debug(f"_click_first_video failed: {e}")
            return False

    def _is_task_complete(self, task: str, current_url: str, previous_url: str) -> bool:
        """Detect task completion by checking URL state changes.

        Smart detection based on task keywords:
        - If task mentions 'click video' or 'watch', need /watch URL (tracked via _visited_watch_url)
        - If task mentions 'search', only complete when search results loaded
        """
        if not current_url or not previous_url:
            return False

        task_lower = task.lower()

        # Track if we ever visit a /watch URL (YouTube redirects back to /)
        if "/watch" in current_url:
            self._visited_watch_url = True

        # Task asks to click/watch a video
        if any(kw in task_lower for kw in ["click", "watch", "first video", "open"]):
            # If we ever visited /watch, task is done (YouTube redirects back)
            if self._visited_watch_url:
                # But only if we're now on a different page from the initial search
                if current_url != previous_url or self._visited_watch_url:
                    return True
            # Still on search results — not done yet
            if "/results" in current_url:
                return False
            # Direct /watch URL
            if "/watch" in current_url:
                return True

        # Task mentions search — check if search results loaded
        if "search" in task_lower:
            if "/results" in current_url or "search" in current_url.lower():
                return True
            if "/watch" in current_url:
                return True

        # Generic: URL changed significantly
        try:
            parsed_current = urlparse(current_url)
            parsed_previous = urlparse(previous_url)

            if parsed_current.path != parsed_previous.path:
                return True
            if parsed_current.query != parsed_previous.query and parsed_current.query:
                return True
        except Exception:
            pass

        return False

    def _fallback_to_vision(self, task: str, url: str, title: str) -> None:
        """Fallback to Vision-based approach when locators fail."""
        console.print("[yellow]  🔄 Falling back to Vision API...[/yellow]")
        try:
            shot_path = f"/tmp/vision-browser-fallback-{int(time.time())}.png"
            shot = self.browser.screenshot(shot_path)
            element_list = "\n".join(shot.get("legend", [])[:20])

            from vision_browser.fast_orchestrator import (
                ACTION_SCHEMA,
                USER_PROMPT,
            )

            prompt = USER_PROMPT.format(
                task=task,
                url=url,
                title=title,
                element_list=element_list,
            )

            result = self.vision.analyze(shot_path, prompt, schema=ACTION_SCHEMA)
            actions = result.get("actions", [])

            if actions:
                console.print(f"  ⚡ Executing {len(actions)} action(s) via Vision API...")
                executed = self.browser.execute_batch(actions)
                console.print(f"  ✅ {executed}/{len(actions)} succeeded")
        except Exception as e:
            logger.debug(f"Vision fallback failed: {e}")

    def _print_summary(self) -> None:
        """Print task summary."""
        elapsed = (
            time.monotonic() - self._task_start_time if self._task_start_time else 0
        )
        status_icon = {"complete": "✅", "failed": "❌"}.get(
            self._task_status, "⏱️"
        )

        lines = [
            "",
            "── Task Summary " + "─" * 30,
            f"  Status: {status_icon} {self._task_status}",
            f"  Turns: {self._task_turns}",
            f"  Actions: {self._task_total_actions} ({self._task_succeeded_actions} succeeded, {self._task_failed_actions} failed)",
            f"  Time: {elapsed:.1f}s",
        ]
        if self._task_final_url:
            lines.append(f"  Final URL: {self._task_final_url}")
        lines.append("─" * 50)

        for line in lines:
            console.print(line)

    def get_task_summary(self) -> dict:
        """Return task execution summary."""
        elapsed = (
            time.monotonic() - self._task_start_time if self._task_start_time else 0
        )
        return {
            "status": self._task_status,
            "turns": self._task_turns,
            "total_actions": self._task_total_actions,
            "succeeded_actions": self._task_succeeded_actions,
            "failed_actions": self._task_failed_actions,
            "elapsed_seconds": round(elapsed, 1),
            "final_url": self._task_final_url,
        }
