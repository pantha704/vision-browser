"""Locator-based orchestrator using Playwright semantic locators.

Uses indexed elements with CSS selectors so the model references
elements by number (e.g., click: 5) instead of guessing strategies.
Includes action result feedback for the next turn.
"""

from __future__ import annotations

import json
import logging
import os
import time
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel

from vision_browser.config import AppConfig
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.vision import VisionClient

logger = logging.getLogger(__name__)
console = Console()


def _capture_debug_screenshot(browser: PlaywrightBrowser, debug_dir: str, label: str) -> str | None:
    """Capture a debug screenshot with timestamp and label."""
    if not debug_dir:
        return None
    try:
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time())
        path = os.path.join(debug_dir, f"{timestamp}_{label}.png")
        browser._page.screenshot(path=path, full_page=False)
        url = browser.get_url() or ""
        logger.debug(f"Debug screenshot: {path} (URL: {url})")
        console.print(f"    📸 Screenshot: {os.path.basename(path)}")
        return path
    except Exception as e:
        logger.debug(f"Screenshot failed: {e}")
        return None

# System prompt — model references elements by INDEX number
LOCATOR_SYSTEM_PROMPT = """\
You are a browser automation agent. The page state is provided as a numbered list of interactive elements with their CSS selectors, roles, and visible text.

TASK FORMAT:
- Elements are numbered [1], [2], [3], etc.
- Each element shows: role, visible text/label, and a CSS selector.

AVAILABLE ACTIONS:
- click: Click element by index (e.g., {"action": "click", "element": 5})
- fill: Fill input by index with text (e.g., {"action": "fill", "element": 3, "text": "hello"})
- click_first_video: Click the first video result on a search page (e.g., {"action": "click_first_video"})
- press: Press a key (e.g., {"action": "press", "key": "Enter"})
- scroll: Scroll page (e.g., {"action": "scroll", "direction": "down", "amount": 500})
- navigate: Go to a URL (e.g., {"action": "navigate", "url": "https://example.com"})
- wait: Wait for page to load (e.g., {"action": "wait"})
- type: Type text into element by index (e.g., {"action": "type", "element": 3, "text": "hello"})

RULES:
1. Use the ELEMENT NUMBER to reference elements — do NOT guess selectors.
2. To search: fill the search input index, then press Enter.
3. To click a VIDEO on search results: use "click_first_video" action — do NOT use regular click.
4. To click a NON-video link: use regular click with element number.
5. Return ONLY valid JSON. No markdown, no explanation.
6. Set "done" to true ONLY when the task is fully complete.

RESPONSE FORMAT:
{"actions": [{"action": "fill", "element": 3, "text": "query"}, {"action": "press", "key": "Enter"}, {"action": "click_first_video"}], "done": false, "reasoning": "why"}
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

# Allowed keyboard keys — same as playwright_browser.py
_ALLOWED_KEYS = frozenset({
    "Enter", "Tab", "Escape", "Backspace", "Delete",
    "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
    "Home", "End", "PageUp", "PageDown", " ",
    "Control+a", "Control+c", "Control+v", "Control+x", "Control+z",
})


class LocatorOrchestrator:
    """Fast orchestrator using Playwright indexed elements.

    Strategy:
    1. Extract all interactive elements with CSS selectors (instant, JS eval)
    2. Build numbered element list for model prompt
    3. Model returns actions referencing element by index
    4. Execute via CSS selector directly (no Vision API for finding elements)
    5. Report success/failure back to model next turn
    """

    def __init__(self, cfg: AppConfig, debug: bool = False):
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
        self.debug = debug
        self._debug_dir = "/tmp/vision-browser-debug"
        self._action_count = 0
        self._shutdown_requested = False
        self._error_count = 0
        self._last_action_key = ""
        self._same_action_count = 0
        self._initial_url: str = ""

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
        # Track distinct failure modes separately
        no_action_turns = 0  # Model returned no actions
        stuck_turns = 0  # Same URL, no progress
        action_feedback: list[str] = []
        # Track if we ever hit a /watch URL for video tasks
        visited_watch_url: bool = False

        for turn in range(1, max_turns + 1):
            self._task_turns = turn
            if self._shutdown_requested:
                console.print("\n[yellow]⏹️ Shutdown requested[/yellow]")
                break

            console.print(f"\n[bold cyan]Turn {turn}/{max_turns}[/bold cyan]")

            url = ""
            title = ""
            elements: list[dict] = []

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
                if turn > 1 and self._is_task_complete(
                    task, url, elements, visited_watch_url
                ):
                    console.print("\n[bold green]✅ Task complete![/bold green]")
                    self._task_status = "complete"
                    self._task_final_url = url
                    break

                # 3. Detect failure modes
                if url and url == self._task_final_url:
                    # Still on same page — but task_final_url is only set at end
                    pass

                if elements:
                    # Page has elements — reset stuck counter
                    stuck_turns = 0
                else:
                    stuck_turns += 1
                    if stuck_turns >= 4:
                        console.print(
                            "[yellow]  ⚠️ Page has no interactive elements for 4 turns. Falling back.[/yellow]"
                        )
                        self._fallback_to_vision(task, url, title)
                        break

                console.print(f"  📍 {url} — {title}")
                console.print(f"  📋 Found {element_count} interactive elements")

                # Track /watch visits for video tasks
                if "/watch" in url:
                    visited_watch_url = True

                # 4. Build prompt with action feedback
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

                # 5. Get actions from Vision API (text-only, fast)
                console.print("  🧠 Planning actions...")
                result = self.vision.analyze_page(
                    url=url,
                    title=title,
                    elements=elements,
                    task=task,
                    system_prompt=LOCATOR_SYSTEM_PROMPT,
                    prompt_override=prompt,
                )

                # Validate response shape
                actions = result.get("actions", [])
                if not isinstance(actions, list):
                    actions = []
                    action_feedback.append(
                        "⚠️ Model returned invalid actions (not a list)"
                    )
                done = bool(result.get("done", False))
                reasoning = result.get("reasoning", "")

                console.print(f"  💡 [dim]{reasoning}[/dim]")

                if actions:
                    console.print(f"  ⚡ Executing {len(actions)} action(s)...")
                    success_count, feedback = self._execute_locator_actions(
                        actions, elements
                    )
                    action_feedback = feedback
                    console.print(f"  ✅ {success_count}/{len(actions)} succeeded")

                    # Refresh URL after actions (navigation may have changed it)
                    url = self.browser.get_url() or url
                    title = self.browser.get_title() or title

                    # Debug: capture screenshot after actions
                    if self.debug:
                        _capture_debug_screenshot(
                            self.browser, self._debug_dir, "after_actions"
                        )

                    self._task_total_actions += len(actions)
                    self._task_succeeded_actions += success_count
                    self._task_failed_actions += len(actions) - success_count

                    # Same-action loop detection
                    action_key = json.dumps(actions)
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
                        no_action_turns = 0
                else:
                    console.print(
                        "[yellow]  ⚠️ No actions returned from model[/yellow]"
                    )
                    no_action_turns += 1
                    action_feedback.append(
                        "⚠️ No actions returned — try again with different element references"
                    )
                    if no_action_turns >= 3:
                        console.print(
                            "[yellow]  ⚠️ Model returned no actions 3 turns in a row. Falling back.[/yellow]"
                        )
                        self._fallback_to_vision(task, url, title)
                        break

                # 6. Check done flag from model (with URL verification)
                if done and self._is_task_complete(
                    task, url, elements, visited_watch_url
                ):
                    console.print("\n[bold green]✅ Task complete![/bold green]")
                    self._task_status = "complete"
                    self._task_final_url = url
                    break

                # Save current URL for next turn's completion check
                self._task_final_url = url

            except Exception as e:
                console.print(f"  ❌ [red]Error:[/red] {e}")
                self._error_count += 1
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

            parts = []
            if role:
                parts.append(f"role={role}")
            if name:
                short_name = name[:50] + "..." if len(name) > 50 else name
                parts.append(f'"{short_name}"')
            if el_type:
                parts.append(f"type={el_type}")
            if href and "/watch" in href:
                parts.append("video link")
            if selector:
                parts.append(f"-> {selector}")

            desc = " ".join(parts) if parts else "unknown"
            lines.append(f"  [{i}] {desc}")

        if len(elements) > max_count:
            lines.append(f"  ... and {len(elements) - max_count} more")

        return "\n".join(lines)

    def _execute_locator_actions(
        self, actions: list[dict], elements: list[dict]
    ) -> tuple[int, list[str]]:
        """Execute actions using indexed element references.

        After each navigation action, re-resolves element indices against
        the current DOM to handle stale selectors.

        Returns (success_count, feedback_list).
        """
        success = 0
        feedback: list[str] = []
        # Working copy of elements — refreshed after navigation
        current_elements = list(elements)

        for action in actions:
            act = action.get("action", "")
            element_idx = action.get("element")

            # Resolve element index to CSS selector
            selector: str | None = None
            el_info = ""
            if element_idx is not None and 1 <= element_idx <= len(current_elements):
                el = current_elements[element_idx - 1]
                selector = el.get("selector") or el.get("css")
                role = el.get("role", "")
                name = el.get("name", "")
                el_info = f"element [{element_idx}] ({role}: {name})"
            elif element_idx is not None:
                el_info = f"element index {element_idx} (out of range 1-{len(current_elements)})"

            try:
                match act:
                    case "click":
                        if selector:
                            logger.debug(f"Clicking: {selector}")
                            console.print(f"    [dim]click -> {selector}[/dim]")
                            self.browser._page.click(selector, timeout=30000)
                            success += 1
                            feedback.append(f"OK Clicked {el_info}")
                            self._wait_for_load()
                            # Refresh elements after potential navigation
                            current_elements = self.browser.get_interactive_elements()
                        else:
                            feedback.append(f"FAIL No selector for {el_info}")

                    case "click_first_video":
                        video_clicked = self._click_first_video()
                        if video_clicked:
                            success += 1
                            feedback.append("OK Clicked first video result")
                            self._wait_for_load()
                            current_elements = self.browser.get_interactive_elements()
                        else:
                            feedback.append("FAIL No video found on page")

                    case "fill":
                        text = action.get("text", "")
                        if selector:
                            logger.debug(f"Filling: {selector} with: {text[:40]}")
                            console.print(f"    [dim]fill -> {selector} = {text[:40]}[/dim]")
                            self.browser._page.fill(selector, text, timeout=30000)
                            success += 1
                            feedback.append(f"OK Filled {el_info}")
                        else:
                            feedback.append(f"FAIL No selector for {el_info}")

                    case "press":
                        key = action.get("key", "Enter")
                        if key not in _ALLOWED_KEYS:
                            feedback.append(f"FAIL Key '{key}' not allowed")
                            continue
                        logger.debug(f"Pressing: {key}")
                        console.print(f"    [dim]press -> {key}[/dim]")
                        self.browser._page.keyboard.press(key)
                        success += 1
                        feedback.append(f"OK Pressed {key}")
                        if key == "Enter":
                            # Wait for navigation to complete before next action
                            self._wait_for_load()
                            current_elements = self.browser.get_interactive_elements()
                            # Log URL after navigation for debugging
                            after_url = self.browser.get_url() or ""
                            logger.debug(f"After Enter wait, URL: {after_url}")
                            console.print(f"    [dim]After wait, URL: {after_url}[/dim]")

                    case "scroll":
                        direction = action.get("direction", "down")
                        amount = action.get("amount", 500)
                        self.browser.scroll(direction, amount)
                        success += 1
                        feedback.append(f"OK Scrolled {direction} by {amount}px")
                        current_elements = self.browser.get_interactive_elements()

                    case "navigate":
                        nav_url = action.get("url", "")
                        # Case-insensitive URL scheme check (C1: security)
                        if nav_url.lower().startswith(("http://", "https://")):
                            self.browser.open(nav_url)
                            success += 1
                            feedback.append(f"OK Navigated to {nav_url[:60]}")
                            self._wait_for_load()
                            current_elements = self.browser.get_interactive_elements()
                        else:
                            feedback.append(f"FAIL Invalid URL: {nav_url[:60]}")

                    case "wait":
                        try:
                            self.browser._page.wait_for_load_state(
                                "domcontentloaded", timeout=10000
                            )
                            success += 1
                            feedback.append("OK Waited for page load")
                        except Exception:
                            feedback.append("WARN Wait timed out")

                    case "type":
                        text = action.get("text", "")
                        if selector:
                            self.browser._page.click(selector, timeout=10000)
                            self.browser._page.keyboard.type(text)
                            success += 1
                            feedback.append(f"OK Typed into {el_info}")
                        else:
                            feedback.append(f"FAIL No selector for {el_info}")

                    case _:
                        feedback.append(f"FAIL Unknown action: {act}")

            except Exception as e:
                logger.warning(f"Action failed: {action.get('action')} with selector={selector} - {e}")
                feedback.append(f"FAIL {el_info}: {str(e)[:80]}")

        return success, feedback

    def _wait_for_load(self) -> None:
        """Wait for DOM content to load after navigation actions.

        For SPA navigation (like YouTube search), also waits for URL to change
        to an expected pattern (e.g., /results for search, /watch for video).
        """
        current_url = self.browser.get_url() or ""
        try:
            self.browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        # For SPA navigation, wait for URL to actually change
        if current_url:
            try:
                self.browser._page.wait_for_function(
                    f"() => location.href !== {json.dumps(current_url)}",
                    timeout=10000,
                )
            except Exception:
                pass

        # For YouTube search: wait for /results URL specifically
        if "youtube.com" in current_url:
            try:
                self.browser._page.wait_for_function(
                    "() => location.href.includes('/results') || location.href.includes('/watch')",
                    timeout=10000,
                )
            except Exception:
                pass
            # YouTube SPA needs extra time to render search results after URL changes
            try:
                self.browser._page.wait_for_timeout(3000)
            except Exception:
                pass

        # Settle delay for JavaScript-rendered content
        try:
            self.browser._page.wait_for_timeout(1500)
        except Exception:
            pass

    def _click_first_video(self) -> bool:
        """Find and click the first video result on a search results page.

        Prioritizes YouTube search result videos (ytd-video-renderer) over
        sidebar/featured videos.
        """
        try:
            result = self.browser._page.evaluate("""() => {
                // Try search result videos first (ytd-video-renderer is the search result container)
                const searchLinks = document.querySelectorAll(
                    'ytd-video-renderer a#video-title[href*="/watch"]'
                );
                for (const link of searchLinks) {
                    const rect = link.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 20 && rect.top > 100) {
                        return { href: link.href, text: link.textContent?.trim().slice(0, 80) };
                    }
                }
                // Fallback: any /watch link with larger size (likely a main content video)
                const allLinks = document.querySelectorAll('a[href*="/watch"]');
                for (const link of allLinks) {
                    const rect = link.getBoundingClientRect();
                    if (rect.width > 80 && rect.height > 30 && rect.top > 100) {
                        return { href: link.href, text: link.textContent?.trim().slice(0, 80) };
                    }
                }
                return null;
            }""")

            if result:
                # Clean up text: remove newlines, extra spaces, truncate
                raw_text = result.get("text", "")
                clean_text = " ".join(raw_text.split())[:40]
                logger.debug(f"Clicking video: {clean_text}")
                console.print(f"    [dim]click_first_video -> {clean_text}[/dim]")
                # Navigate directly to video URL (more reliable than clicking)
                href = result.get("href", "")
                if href:
                    # Convert relative URL to absolute if needed
                    if href.startswith("/"):
                        base_url = self.browser.get_url()
                        from urllib.parse import urljoin
                        href = urljoin(base_url, href)
                    self.browser.open(href)
                    self._wait_for_load()
                    return True

            # Fallback: try clicking any /watch link
            try:
                self.browser._page.locator('a[href*="/watch"]').first.click(timeout=15000)
                self._wait_for_load()
                return True
            except Exception:
                return False
        except Exception as e:
            logger.debug(f"_click_first_video failed: {e}")
            return False

    def _is_task_complete(
        self,
        task: str,
        current_url: str,
        elements: list[dict],
        visited_watch_url: bool,
    ) -> bool:
        """Detect task completion by checking URL state changes.

        Args:
            task: The original task description
            current_url: Current page URL
            elements: Current interactive elements (checked for emptiness)
            visited_watch_url: Whether we ever visited a /watch URL
        """
        if not current_url:
            return False

        task_lower = task.lower()

        # Task asks to click/watch a video
        if any(kw in task_lower for kw in ["click", "watch", "first video"]):
            if "/watch" in current_url:
                return True
            if visited_watch_url and current_url != self._initial_url:
                # We visited /watch and are now on a different page = done
                # (YouTube redirects /watch back to / or search results)
                return True
            if "/results" in current_url:
                return False  # Still on search results

        # Task mentions search
        if "search" in task_lower:
            if "/results" in current_url or "search" in current_url.lower():
                return True
            if "/watch" in current_url:
                return True

        # Generic: URL changed significantly from initial
        if self._initial_url and current_url != self._initial_url:
            try:
                parsed_current = urlparse(current_url)
                parsed_initial = urlparse(self._initial_url)
                if parsed_current.path != parsed_initial.path:
                    return True
                if parsed_current.query != parsed_initial.query and parsed_current.query:
                    return True
            except Exception:
                pass

        return False

    def _fallback_to_vision(self, task: str, url: str, title: str) -> None:
        """Fallback to Vision-based approach when locators fail."""
        console.print("[yellow]  Falling back to Vision API...[/yellow]")
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
                console.print(
                    f"  Executing {len(actions)} action(s) via Vision API..."
                )
                executed = self.browser.execute_batch(actions)
                console.print(f"  {executed}/{len(actions)} succeeded")
                # Update task status since fallback ran
                self._task_final_url = self.browser.get_url() or url
                if executed > 0:
                    self._task_status = "complete"
            else:
                self._task_status = "max_turns_reached"
        except Exception as e:
            logger.debug(f"Vision fallback failed: {e}")
            self._task_status = "max_turns_reached"

    def _print_summary(self) -> None:
        """Print task summary."""
        elapsed = (
            time.monotonic() - self._task_start_time if self._task_start_time else 0
        )
        status_icon = {"complete": "OK", "failed": "FAIL"}.get(
            self._task_status, "TIMEOUT"
        )

        lines = [
            "",
            "-- Task Summary " + "-" * 30,
            f"  Status: {status_icon} {self._task_status}",
            f"  Turns: {self._task_turns}",
            f"  Actions: {self._task_total_actions} ({self._task_succeeded_actions} succeeded, {self._task_failed_actions} failed)",
            f"  Time: {elapsed:.1f}s",
        ]
        if self._task_final_url:
            lines.append(f"  Final URL: {self._task_final_url}")
        lines.append("-" * 50)

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
