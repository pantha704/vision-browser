"""Playwright-based browser controller with persistent CDP connection."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    sync_playwright,
)

from vision_browser.config import BrowserConfig
from vision_browser.exceptions import (
    ActionExecutionError,
    BrowserError,
    BrowserNotInstalledError,
    TimeoutError,
)

logger = logging.getLogger(__name__)

# Allowed keyboard keys
_ALLOWED_KEYS = frozenset({
    "Enter", "Tab", "Escape", "Backspace", "Delete", "ArrowLeft", "ArrowRight",
    "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown", " ",
    "Control+a", "Control+c", "Control+v", "Control+x", "Control+z",
})

# Navigation timeouts
_NAV_TIMEOUT = 60_000
_ACTION_TIMEOUT = 30_000

# Badge injection script (loaded from file)
_INJECT_SCRIPT = Path(__file__).parent / "inject.js"


class PlaywrightBrowser:
    """Persistent browser controller via Playwright + CDP."""

    def __init__(self, cfg: BrowserConfig | None = None):
        self.cfg = cfg or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._badge_map: dict[int, str] = {}  # badge_num -> selector
        self._badge_cache: list[dict] = []  # Raw badge data
        self._connect()

    def _connect(self) -> None:
        """Connect to browser via CDP or launch new instance."""
        self._playwright = sync_playwright().start()
        
        if self.cfg.cdp_url:
            # Connect to existing browser (e.g., Brave with --remote-debugging-port)
            try:
                self._browser = self._playwright.chromium.connect_over_cdp(
                    self.cfg.cdp_url,
                    timeout=self.cfg.timeout_ms,
                )
                logger.info(f"Connected to existing browser via CDP: {self.cfg.cdp_url}")
                
                # Use first context and page
                contexts = self._browser.contexts
                if contexts:
                    self._context = contexts[0]
                    pages = self._context.pages
                    if pages:
                        self._page = pages[0]
                    else:
                        self._page = self._context.new_page()
                else:
                    self._context = self._browser.new_context()
                    self._page = self._context.new_page()
                    
            except Exception as e:
                raise BrowserError(f"Failed to connect to CDP at {self.cfg.cdp_url}: {e}") from e
        else:
            # Launch new browser
            launch_args = {
                "headless": True,
                "timeout": self.cfg.timeout_ms,
            }
            # Add --no-sandbox for Linux
            launch_args["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]
            
            try:
                self._browser = self._playwright.chromium.launch(**launch_args)
                self._context = self._browser.new_context(
                    viewport={"width": self.cfg.viewport[0], "height": self.cfg.viewport[1]},
                )
                self._page = self._context.new_page()
                logger.info("Launched new headless browser")
            except Exception as e:
                raise BrowserError(f"Failed to launch browser: {e}") from e

    def open(self, url: str) -> None:
        """Navigate to URL."""
        if not url.startswith(("http://", "https://")):
            raise ActionExecutionError(f"Only http/https URLs allowed: {url[:80]}")
        
        try:
            self._page.goto(url, wait_until="networkidle", timeout=_NAV_TIMEOUT)
            # Clear badge cache after navigation
            self._badge_map = {}
            self._badge_cache = []
        except PlaywrightError as e:
            raise BrowserError(f"Navigation failed: {e}") from e

    def close(self) -> None:
        """Close browser. Skip if using CDP (user controls the browser)."""
        if self.cfg.cdp_url:
            return
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

    def screenshot(self, path: str, *, full_page: bool = False) -> dict[str, Any]:
        """Take screenshot. Returns path and element badges."""
        try:
            self._page.screenshot(path=path, full_page=full_page)
            
            # Extract badges and a11y tree
            result = self._inject_badges()
            result["path"] = path
            return result
        except PlaywrightError as e:
            raise BrowserError(f"Screenshot failed: {e}") from e

    def _inject_badges(self) -> dict:
        """Inject badge overlay and extract element mapping."""
        try:
            script = _INJECT_SCRIPT.read_text()
            result = self._page.evaluate(script)
            
            # Store badge mapping
            self._badge_cache = result.get("badges", [])
            self._badge_map = {b["num"]: b["selector"] for b in self._badge_cache}
            
            return {
                "refs": self._badge_map,
                "legend": [f'  [{b["num"]}] {b["selector"]} ({b["a11y"]})' for b in self._badge_cache],
                "a11y_tree": result.get("a11yTree", ""),
                "url": result.get("url", ""),
                "title": result.get("title", ""),
            }
        except PlaywrightError as e:
            logger.warning(f"Badge injection failed: {e}")
            return {"refs": {}, "legend": [], "a11y_tree": "", "url": "", "title": ""}

    def click(self, ref: str | int) -> None:
        """Click element by badge number or selector."""
        selector = self._resolve_ref(ref)
        try:
            self._page.click(selector, timeout=_ACTION_TIMEOUT)
        except PlaywrightError as e:
            # Try direct CSS selector if badge resolution failed
            if isinstance(ref, str) and ref.startswith("@"):
                raise ActionExecutionError(f"Click failed on {ref}: {e}") from e
            raise BrowserError(f"Click failed: {e}") from e

    def fill(self, ref: str | int, text: str) -> None:
        """Fill input element with text."""
        if len(text) > 5000:
            raise ActionExecutionError("Text too long (>5000 chars)")
        
        selector = self._resolve_ref(ref)
        try:
            self._page.click(selector, timeout=_ACTION_TIMEOUT)
            self._page.fill(selector, text, timeout=_ACTION_TIMEOUT)
        except PlaywrightError as e:
            raise ActionExecutionError(f"Fill failed on {ref}: {e}") from e

    def press(self, key: str) -> None:
        """Press keyboard key."""
        if key not in _ALLOWED_KEYS:
            raise ActionExecutionError(f"Disallowed key: {key!r}")
        
        try:
            self._page.keyboard.press(key)
        except PlaywrightError as e:
            raise ActionExecutionError(f"Key press failed: {e}") from e

    def scroll(self, direction: str = "down", amount: int = 500) -> None:
        """Scroll page."""
        try:
            if direction == "down":
                self._page.evaluate(f"window.scrollBy(0, {amount})")
            else:
                self._page.evaluate(f"window.scrollBy(0, -{amount})")
        except PlaywrightError as e:
            raise BrowserError(f"Scroll failed: {e}") from e

    def wait(self, *args: str) -> None:
        """Wait for element or network idle."""
        try:
            if args and args[0] == "--load":
                self._page.wait_for_load_state("networkidle", timeout=_ACTION_TIMEOUT)
            elif args:
                selector = args[0]
                self._page.wait_for_selector(selector, timeout=_ACTION_TIMEOUT)
        except PlaywrightError as e:
            raise TimeoutError(f"Wait failed: {e}") from e

    def get_title(self) -> str:
        """Get page title."""
        return self._page.title()

    def get_url(self) -> str:
        """Get current URL."""
        return self._page.url

    def execute_batch(self, actions: list[dict]) -> int:
        """Execute multiple actions. Returns count of successes."""
        success = 0
        for action in actions:
            try:
                act = action.get("action", "")
                element = action.get("element")
                
                match act:
                    case "click":
                        self.click(element)
                    case "fill" | "type":
                        self.fill(element, action.get("text", ""))
                    case "press" | "key":
                        self.press(action.get("key", "Enter"))
                    case "scroll":
                        self.scroll(
                            action.get("direction", "down"),
                            action.get("amount", 500),
                        )
                    case "wait":
                        self.wait("--load", "networkidle")
                    case "navigate" | "open":
                        url = action.get("url", "")
                        if url.startswith(("http://", "https://")):
                            self.open(url)
                    case _:
                        logger.warning(f"Unknown action: {act}")
                        continue
                
                success += 1
                
                # Wait for DOM to settle after actions that change it
                if act in ("click", "navigate", "open"):
                    try:
                        self.wait("--load", "networkidle")
                    except Exception:
                        pass
                
            except Exception as e:
                logger.debug(f"Action failed: {action} - {e}")
                continue
        
        return success

    def _resolve_ref(self, ref: str | int) -> str:
        """Resolve badge number or @ref to CSS selector."""
        if isinstance(ref, int):
            if ref in self._badge_map:
                return self._badge_map[ref]
            raise ActionExecutionError(f"Badge {ref} not found in current page")
        
        if isinstance(ref, str):
            # Handle @e5 format
            if ref.startswith("@e"):
                num = int(ref[2:])
                if num in self._badge_map:
                    return self._badge_map[num]
                raise ActionExecutionError(f"Badge {num} not found")
            # Direct CSS selector
            return ref
        
        raise ActionExecutionError(f"Invalid ref: {ref}")

    def is_alive(self) -> bool:
        """Check if browser is still responsive."""
        try:
            self._page.evaluate("1")
            return True
        except Exception:
            return False
