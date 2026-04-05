"""Multi-browser support -- Firefox and Safari/WebKit via Playwright."""

from __future__ import annotations

import logging
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    sync_playwright,
)

logger = logging.getLogger(__name__)

# Browser engine types
BROWSER_CHROMIUM = "chromium"
BROWSER_FIREFOX = "firefox"
BROWSER_WEBKIT = "webkit"

VALID_ENGINES = {BROWSER_CHROMIUM, BROWSER_FIREFOX, BROWSER_WEBKIT}


class MultiBrowserManager:
    """Manages multiple browser engine support via Playwright.

    Supports Chromium (default), Firefox, and WebKit (Safari).
    Each engine has different capabilities and limitations.
    """

    def __init__(self, engine: str = BROWSER_CHROMIUM):
        """Initialize multi-browser manager.

        Args:
            engine: Browser engine to use (chromium, firefox, webkit).
        """
        if engine not in VALID_ENGINES:
            raise ValueError(
                f"Invalid engine: {engine}. Must be one of {VALID_ENGINES}"
            )
        self.engine = engine
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def launch(self, headless: bool = True, **kwargs: Any) -> None:
        """Launch the selected browser engine.

        Args:
            headless: Run in headless mode.
            **kwargs: Additional launch options passed to Playwright.
        """
        self._playwright = sync_playwright().start()

        launch_kwargs = {"headless": headless}
        if headless:
            # Add sandbox args for Linux
            launch_kwargs["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]
        launch_kwargs.update(kwargs)

        launcher = getattr(self._playwright, self.engine)

        try:
            self._browser = launcher.launch(**launch_kwargs)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            logger.info(f"Launched {self.engine} (headless={headless})")
        except Exception as e:
            raise RuntimeError(f"Failed to launch {self.engine}: {e}") from e

    def connect_cdp(self, cdp_url: str) -> None:
        """Connect to an existing browser via CDP (Chromium only).

        Args:
            cdp_url: Chrome DevTools Protocol URL.
        """
        if self.engine != BROWSER_CHROMIUM:
            raise ValueError(
                f"CDP connection only supported for Chromium, not {self.engine}"
            )

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else self._context.new_page()
                )
            else:
                self._context = self._browser.new_context()
                self._page = self._context.new_page()
            logger.info(f"Connected to Chromium via CDP: {cdp_url}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect via CDP: {e}") from e

    def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        if not self._page:
            raise RuntimeError("Browser not launched")
        self._page.goto(url, wait_until="networkidle")

    def screenshot(self, path: str) -> dict:
        """Take a screenshot."""
        if not self._page:
            raise RuntimeError("Browser not launched")
        self._page.screenshot(path=path)
        return {
            "path": path,
            "url": self._page.url,
            "title": self._page.title(),
        }

    def close(self) -> None:
        """Close the browser."""
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

    @property
    def is_connected(self) -> bool:
        """Check if browser is connected."""
        return self._browser is not None and self._page is not None

    @staticmethod
    def available_engines() -> dict[str, bool]:
        """Check which browser engines are available.

        Returns:
            Dict mapping engine names to availability status.
        """
        available = {}
        try:
            pw = sync_playwright().start()
            for engine in VALID_ENGINES:
                try:
                    browser = getattr(pw, engine).launch(headless=True)
                    browser.close()
                    available[engine] = True
                except Exception:
                    available[engine] = False
            pw.stop()
        except Exception:
            for engine in VALID_ENGINES:
                available[engine] = False
        return available
