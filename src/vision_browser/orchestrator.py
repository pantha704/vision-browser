"""Main orchestrator — loops: screenshot → vision → execute → repeat."""

from __future__ import annotations

import logging
import signal
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from vision_browser.browser import AgentBrowser
from vision_browser.config import AppConfig
from vision_browser.desktop import DesktopController
from vision_browser.vision import VisionClient

logger = logging.getLogger(__name__)
console = Console()

# System prompt: role definition + JSON schema
SYSTEM_PROMPT = """\
You are a browser automation agent. You control a browser by returning JSON actions.

RULES:
1. Only use element numbers that appear in the element list below.
2. Element numbers NOT in the list DO NOT EXIST. Do not invent them.
3. Return ONLY valid JSON. No markdown, no explanation, no code blocks.
4. Set "done": true ONLY when the task is fully accomplished and the result is visible.
5. Before setting "done": true, verify: the requested information/action is complete and visible on screen.

JSON SCHEMA:
{
    "actions": [
        {"action": "click", "element": 3},
        {"action": "fill", "element": 5, "text": "search query"},
        {"action": "press", "key": "Enter"},
        {"action": "scroll", "direction": "down", "amount": 500}
    ],
    "done": false,
    "reasoning": "One sentence explaining what you are doing"
}

VALID ACTIONS: click, fill, select, press, scroll, wait, navigate
"""

BROWSER_PROMPT = """\
TASK: {task}

CURRENT PAGE: {url}
PAGE TITLE: {title}

AVAILABLE ELEMENTS:
{element_list}

INSTRUCTIONS:
- If the URL contains "/search?", you are on search RESULTS. Click the most relevant result link. Do NOT use the search bar.
- If on a search engine homepage: use "fill" action to type the search query into the search bar element, THEN use "press" action with key "Enter". Two separate actions.
- Do NOT just click the search bar. Use "fill" to type into it.
- Only use element numbers from the list above.
- Max 2 actions per turn.

RESPONSE FORMAT (JSON only, no markdown):
{{"actions": [{{"action": "fill", "element": 23, "text": "my query"}}, {{"action": "press", "key": "Enter"}}], "done": false, "reasoning": "why"}}

Return ONLY the JSON object.
"""

DESKTOP_PROMPT = """\
You are a desktop automation agent. Analyze the screenshot and return the next action.

TASK: {task}

Return ONLY valid JSON:
{{
    "action": "click" | "type" | "key" | "scroll",
    "x": 100,
    "y": 200,
    "text": "text to type",
    "key": "Return",
    "direction": "down",
    "done": false,
    "reasoning": "One sentence explaining what you are doing"
}}

Return JSON only.
"""

SCREENSHOT_PATH = Path("/tmp/vision-browser-screenshot.png")


class Orchestrator:
    """Main automation loop with graceful shutdown and crash recovery."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.vision = VisionClient(cfg.vision, {
            "retry_attempts": cfg.orchestrator.retry_attempts,
            "retry_backoff_base": cfg.orchestrator.retry_backoff_base,
            "rate_limit_delay": cfg.orchestrator.rate_limit_delay,
        })
        self.browser = AgentBrowser(cfg.browser)
        self.desktop = DesktopController(cfg.desktop)
        self._shutdown_requested = False
        self._last_url = ""
        self._register_signals()

    def _register_signals(self) -> None:
        """Register signal handlers for graceful shutdown."""
        def _handler(signum: int, _frame: object) -> None:
            logger.info(f"Signal {signum} received, shutting down gracefully")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def run(self, task: str, url: str | None = None, desktop_mode: bool = False) -> None:
        """Execute the automation loop."""
        console.print(Panel(f"[bold green]Task:[/bold green] {task}", title="Vision Browser"))

        if self._shutdown_requested:
            console.print("[yellow]Shutdown requested before start, exiting[/yellow]")
            return

        if desktop_mode:
            self._run_desktop(task)
        else:
            if url:
                console.print(f"[dim]→ Navigating to {url}[/dim]")
                try:
                    self.browser.open(url)
                    self.browser.wait("--load", "networkidle")
                except Exception as e:
                    logger.warning(f"Navigation wait failed: {e}")
                    # Continue anyway — page may have loaded partially
            self._run_browser(task)

    def _run_browser(self, task: str) -> None:
        """Browser automation loop with crash recovery."""
        max_turns = self.cfg.orchestrator.max_turns
        max_elements = self.cfg.orchestrator.max_prompt_elements
        consecutive_failures = 0
        last_url = ""
        same_url_count = 0

        for turn in range(1, max_turns + 1):
            if self._shutdown_requested:
                console.print("\n[yellow]⏹️ Shutdown requested[/yellow]")
                break

            console.print(f"\n[bold cyan]Turn {turn}/{max_turns}[/bold cyan]")

            try:
                # 1. Screenshot with annotated badges
                console.print("  📸 Capturing annotated screenshot...")
                shot_result = self.browser.screenshot(str(SCREENSHOT_PATH), annotate=True)
                element_refs: dict[int, str] = shot_result.get("refs", {})
                element_legend: list[str] = shot_result.get("legend", [])

                # 2. Get page context
                url = self.browser.get_url()
                title = self.browser.get_title()
                self._last_url = url

                # Detect same-URL loop
                if url == last_url:
                    same_url_count += 1
                else:
                    same_url_count = 0
                last_url = url

                if same_url_count >= 2:
                    console.print(f"[yellow]  ⚠️ Stuck on same URL for {same_url_count} turns. Forcing new strategy.[/yellow]")
                    consecutive_failures = max(consecutive_failures, 2)
                console.print(f"  📍 {url} — {title}")

                # 3. Build compact element list from annotation legend (with roles)
                element_list = self._build_element_list_from_legend(
                    element_legend, max_elements
                )

                # 4. Send to vision model with JSON retry
                console.print("  🧠 Sending to vision model...")
                prompt = BROWSER_PROMPT.format(
                    task=task, url=url, title=title, element_list=element_list
                )
                result = self._analyze_with_json_retry(
                    str(SCREENSHOT_PATH), prompt, system_prompt=SYSTEM_PROMPT
                )

                # 5. Parse and execute — validate refs
                actions = result.get("actions", [])
                done = result.get("done", False)
                reasoning = result.get("reasoning", "")

                console.print(f"  💡 [dim]{reasoning}[/dim]")

                if actions:
                    valid_actions, skipped = self._validate_actions(
                        actions, element_refs
                    )
                    for s in skipped:
                        console.print(f"  ⚠️ {s}")

                    # Fallback: if model keeps hallucinating refs, try semantic click
                    if not valid_actions and skipped and consecutive_failures >= 2:
                        # Strategy 1: Auto-fill search bar if on Google homepage
                        if "/search" not in url and "google" in url.lower():
                            fallback_worked = False
                            # Find the combobox (search bar) element
                            for num, ref in sorted(element_refs.items()):
                                if "combobox" in ref.lower() or "search" in ref.lower():
                                    try:
                                        # Extract query from task
                                        import re
                                        query_match = re.search(r"['\"]([^'\"]+)['\"]", task)
                                        query = query_match.group(1) if query_match else task[:50]
                                        console.print(f"[yellow]  🔄 Auto-filling search with: {query}[/yellow]")
                                        self.browser.fill(ref, query)
                                        self.browser.press("Enter")
                                        consecutive_failures = 0
                                        fallback_worked = True
                                        break
                                    except Exception as fe:
                                        logger.debug(f"Auto-fill failed: {fe}")

                            if not fallback_worked:
                                console.print("[yellow]  🔄 No combobox found for auto-fill.[/yellow]")

                        if not fallback_worked:
                            # Strategy 2: Click first link element by badge
                            console.print("[yellow]  🔄 Semantic click failed. Falling back: clicking first link.[/yellow]")
                            for num, ref in sorted(element_refs.items()):
                                try:
                                    self.browser.click(ref)
                                    consecutive_failures = 0
                                    console.print(f"  ✅ Clicked {ref}")
                                    break
                                except Exception:
                                    continue

                    if valid_actions:
                        # Limit to 1 action after failures to avoid DOM staleness
                        if consecutive_failures > 0:
                            valid_actions = valid_actions[:1]
                        console.print(f"  ⚡ Executing {len(valid_actions)} action(s)...")
                        executed = self.browser.execute_batch(valid_actions)
                        console.print(f"  ✅ {executed} actions succeeded")

                        if executed > 0:
                            consecutive_failures = 0
                            try:
                                self.browser.wait("--load", "networkidle")
                            except Exception:
                                pass
                        else:
                            consecutive_failures += 1

                if done:
                    # Verification step
                    if self._verify_completion(task, turn, max_turns):
                        console.print("\n[bold green]✅ Task complete![/bold green]")
                        break
                    else:
                        console.print("[yellow]  ⚠️ Task not verified, continuing...[/yellow]")
                        done = False  # Reset, keep looping

            except Exception as e:
                logger.error(f"Turn {turn} failed: {e}")
                console.print(f"  ❌ [red]Error on turn {turn}:[/red] {e}")
                # Try to recover: check if browser is still alive
                if not self._browser_alive():
                    if self.browser.cfg.cdp_url:
                        console.print("[yellow]  ⚠️ Brave CDP connection lost. Please restart Brave with --remote-debugging-port=9222[/yellow]")
                        break
                    console.print("[yellow]  🔄 Browser crashed, attempting recovery...[/yellow]")
                    try:
                        self.browser.close()
                    except Exception:
                        pass
                    if url := self._last_url:
                        try:
                            self.browser.open(url)
                            console.print(f"  🔄 Restored to {url}")
                        except Exception as recover_err:
                            console.print(f"  ❌ Recovery failed: {recover_err}")
                            break

            if turn == max_turns:
                console.print("\n[bold yellow]⏱️ Max turns reached[/bold yellow]")

    def _run_desktop(self, task: str) -> None:
        """Desktop automation loop (slower, coordinate-based)."""
        max_turns = self.cfg.orchestrator.max_turns

        for turn in range(1, max_turns + 1):
            if self._shutdown_requested:
                console.print("\n[yellow]⏹️ Shutdown requested[/yellow]")
                break

            console.print(f"\n[bold cyan]Turn {turn}/{max_turns}[/bold cyan]")

            try:
                console.print("  📸 Capturing desktop screenshot...")
                self.desktop.screenshot(str(SCREENSHOT_PATH))

                console.print("  🧠 Sending to vision model...")
                prompt = DESKTOP_PROMPT.format(task=task)
                result = self.vision.analyze(str(SCREENSHOT_PATH), prompt)

                action = result.get("action", "")
                done = result.get("done", False)
                reasoning = result.get("reasoning", "")

                console.print(f"  💡 [dim]{reasoning}[/dim]")

                match action:
                    case "click":
                        x, y = result.get("x", 0), result.get("y", 0)
                        console.print(f"  🖱️ Clicking ({x}, {y})")
                        self.desktop.click(x, y)
                    case "type":
                        text = result.get("text", "")
                        console.print(f"  ⌨️ Typing: {text[:50]}...")
                        self.desktop.type_text(text)
                    case "key":
                        key = result.get("key", "")
                        console.print(f"  ⌨️ Pressing: {key}")
                        self.desktop.press_key(key)
                    case "scroll":
                        self.desktop.scroll(result.get("direction", "down"))

                if done:
                    console.print("\n[bold green]✅ Task complete![/bold green]")
                    break

            except Exception as e:
                logger.error(f"Desktop turn {turn} failed: {e}")
                console.print(f"  ❌ [red]Error on turn {turn}:[/red] {e}")

            if turn == max_turns:
                console.print("\n[bold yellow]⏱️ Max turns reached[/bold yellow]")

    # ── Helpers ─────────────────────────────────────────────────────

    def _analyze_with_json_retry(
        self, image_path: str, prompt: str, system_prompt: str = ""
    ) -> dict:
        """Send to vision model and retry if JSON wasn't returned."""
        result = self.vision.analyze(image_path, prompt)

        # Check if we got valid JSON (not the fallback wrapper)
        if "actions" in result and isinstance(result.get("actions"), list):
            return result

        # Model returned prose — retry with a strict re-prompt
        console.print("  🔄 [yellow]Model returned prose, retrying with strict JSON prompt...[/yellow]")
        retry_prompt = (
            "Your previous response was not valid JSON. "
            "You MUST respond with ONLY a JSON object. "
            "No explanation, no markdown, no code blocks.\n\n"
            "RESPONSE FORMAT: "
            '{"actions": [{"action": "click", "element": 3}], "done": false, "reasoning": "doing X"}\n\n'
            f"Original task: {prompt[:200]}\n\n"
            "Return ONLY the JSON object now."
        )
        result = self.vision.analyze(image_path, retry_prompt)
        return result

    def _build_element_list_from_legend(
        self, legend: list[str], max_elements: int
    ) -> str:
        """Build a descriptive element list from the annotation legend (includes roles)."""
        if not legend:
            return "  (no interactive elements found)"

        elements = legend[:max_elements]
        if len(legend) > max_elements:
            elements.append(f"  ... and {len(legend) - max_elements} more elements")

        return "\n".join(elements)

    def _validate_actions(
        self,
        actions: list[dict],
        valid_refs: dict[int, str],
    ) -> tuple[list[dict], list[str]]:
        """Validate actions against available refs. Returns (valid, skipped_messages)."""
        valid: list[dict] = []
        skipped: list[str] = []

        for action in actions:
            element = action.get("element")
            if isinstance(element, int) and element not in valid_refs:
                skipped.append(
                    f"Skipping: element {element} not found "
                    f"(valid: {sorted(valid_refs.keys())[:10]}...)"
                )
                continue
            valid.append(action)

        return valid, skipped

    def _verify_completion(
        self, task: str, turn: int, max_turns: int
    ) -> bool:
        """Take one more screenshot and verify the task is actually done."""
        try:
            shot = self.browser.screenshot(str(SCREENSHOT_PATH), annotate=True)
            url = self.browser.get_url()
            title = self.browser.get_title()
            element_list = self._build_element_list_from_legend(
                shot.get("legend", []),
                self.cfg.orchestrator.max_prompt_elements,
            )
            verify_prompt = (
                f"The task was: {task}\n"
                f"Current page: {url} — {title}\n"
                f"Elements available: {element_list}\n\n"
                f"Is the task actually complete? Return ONLY JSON: "
                f'{{"complete": true/false, "reasoning": "why"}}'
            )
            result = self.vision.analyze(str(SCREENSHOT_PATH), verify_prompt)
            is_complete = result.get("complete", False)
            logger.info(f"Verification: complete={is_complete}, reason={result.get('reasoning')}")
            return bool(is_complete)
        except Exception as e:
            logger.warning(f"Verification failed, accepting completion: {e}")
            return True  # Don't block completion on verification failure

    def _browser_alive(self) -> bool:
        """Check if the browser is still responsive."""
        try:
            self.browser.get_url()
            return True
        except Exception:
            return False
