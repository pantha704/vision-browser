"""Playwright-based browser controller with persistent CDP connection."""

from __future__ import annotations

import logging
import re
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
    TimeoutError,
)
from vision_browser.session import SessionManager

logger = logging.getLogger(__name__)

# Allowed keyboard keys
_ALLOWED_KEYS = frozenset(
    {
        "Enter",
        "Tab",
        "Escape",
        "Backspace",
        "Delete",
        "ArrowLeft",
        "ArrowRight",
        "ArrowUp",
        "ArrowDown",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        " ",
        "Control+a",
        "Control+c",
        "Control+v",
        "Control+x",
        "Control+z",
    }
)

# Navigation timeouts
_NAV_TIMEOUT = 60_000
_ACTION_TIMEOUT = 30_000

# Badge injection script (loaded from file)
_INJECT_SCRIPT = Path(__file__).parent / "inject.js"


class PlaywrightBrowser:
    """Persistent browser controller via Playwright + CDP."""

    # Known CAPTCHA/error page indicators
    _CAPTCHA_SELECTORS = [
        "#g-recaptcha",
        ".g-recaptcha",
        "#recaptcha",
        ".h-captcha",
        "#h-captcha",
        'iframe[src*="recaptcha"]',
        'iframe[src*="hcaptcha"]',
    ]
    _ERROR_PAGE_INDICATORS = [
        "Server Not Found",
        "This site can't be reached",
        "ERR_NAME_NOT_RESOLVED",
        "ERR_CONNECTION_REFUSED",
        "ERR_CONNECTION_TIMED_OUT",
        "404 Not Found",
        "500 Internal Server Error",
        "502 Bad Gateway",
        "503 Service Unavailable",
    ]

    def __init__(self, cfg: BrowserConfig | None = None):
        self.cfg = cfg or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._badge_map: dict[int, str] = {}  # badge_num -> selector
        self._badge_cache: list[dict] = []  # Raw badge data
        self._session_manager = SessionManager() if self.cfg.session_name else None
        self._page_crashed = False
        self._connect()
        self._restore_session()
        self._setup_crash_handler()

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
                logger.info(
                    f"Connected to existing browser via CDP: {self.cfg.cdp_url}"
                )

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
                raise BrowserError(
                    f"Failed to connect to CDP at {self.cfg.cdp_url}: {e}"
                ) from e
        else:
            # Launch new browser
            launch_args = {
                "headless": self.cfg.headless,
                "timeout": self.cfg.timeout_ms,
            }
            # Add --no-sandbox for Linux
            launch_args["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]

            try:
                self._browser = self._playwright.chromium.launch(**launch_args)
                self._context = self._browser.new_context(
                    viewport={
                        "width": self.cfg.viewport[0],
                        "height": self.cfg.viewport[1],
                    },
                )
                self._page = self._context.new_page()
                
                # Apply stealth mode to remove automation fingerprints
                try:
                    from playwright_stealth import Stealth
                    stealth = Stealth()
                    stealth.apply_stealth(self._page)
                    logger.debug("Stealth mode applied to page")
                except Exception as e:
                    logger.debug(f"Stealth mode not available: {e}")
                
                mode = "headless" if self.cfg.headless else "headed (visible)"
                logger.info(f"Launched new {mode} browser")
            except Exception as e:
                raise BrowserError(f"Failed to launch browser: {e}") from e

    def open(self, url: str) -> None:
        """Navigate to URL."""
        if not url.startswith(("http://", "https://")):
            raise ActionExecutionError(f"Only http/https URLs allowed: {url[:80]}")

        try:
            # Use "load" instead of "networkidle" for heavy SPAs
            # (Instagram, X, etc. have infinite analytics connections)
            self._page.goto(url, wait_until="load", timeout=_NAV_TIMEOUT)
            # Short wait for network to settle without blocking forever
            try:
                self._page.wait_for_load_state("domcontentloaded", timeout=10_000)
            except Exception:
                pass  # Page is usable even if DOM isn't fully ready
            # Clear badge cache after navigation
            self._badge_map = {}
            self._badge_cache = []
        except PlaywrightError as e:
            raise BrowserError(f"Navigation failed: {e}") from e

    def _restore_session(self) -> None:
        """Restore session from disk if session_name is set."""
        if not self._session_manager or not self.cfg.session_name:
            return
        if self._context is None:
            return

        restored = self._session_manager.restore_session(
            self._context, self.cfg.session_name
        )
        if restored:
            logger.info(f"Restored session: {self.cfg.session_name}")
        else:
            logger.debug(f"No session found: {self.cfg.session_name}")

    def _setup_crash_handler(self) -> None:
        """Register page crash handler for crash detection."""
        if self._page is None:
            return
        try:
            self._page.on("crash", lambda page: self._on_page_crash(page))
        except Exception as e:
            logger.debug(f"Failed to setup crash handler: {e}")

    def _on_page_crash(self, page: Page) -> None:
        """Handle page crash event."""
        self._page_crashed = True
        logger.error(f"Page crashed: {page.url}")

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ):
        """Retry a function with exponential backoff for transient failures."""
        import time as _time

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return func()
            except PlaywrightError as e:
                last_error = e
                # Don't retry non-transient errors
                error_str = str(e).lower()
                if any(
                    kw in error_str
                    for kw in ["not found", "timeout", "target closed", "target crashed"]
                ):
                    if attempt < max_retries:
                        delay = backoff_base * (2**attempt)
                        logger.debug(
                            f"Transient error, retrying in {delay:.1f}s: {e}"
                        )
                        _time.sleep(delay)
                        continue
                raise
            except Exception:
                raise
        raise last_error

    def save_session(self) -> None:
        """Save current session to disk."""
        if not self._session_manager or not self.cfg.session_name:
            return
        if self._context is None:
            return

        try:
            self._session_manager.save_session(self._context, self.cfg.session_name)
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")

    def close(self) -> None:
        """Close browser. Skip if using CDP (user controls the browser)."""
        if self.cfg.cdp_url:
            # Save session before disconnecting
            self.save_session()
            # Stop Playwright subprocess (we don't close the browser — user owns it)
            if self._playwright:
                try:
                    self._playwright.stop()
                    logger.debug("CDP mode: stopped Playwright subprocess")
                except Exception as e:
                    logger.debug(f"Playwright stop error: {e}")
            return

        # Save session before closing owned browser
        self.save_session()

        # Close each resource independently to prevent leaks on partial failure
        # Order matters: page -> context -> browser -> playwright
        if self._page:
            try:
                self._page.close()
            except Exception as e:
                if "Event loop is closed" not in str(e):
                    logger.debug(f"Page close error: {e}")
            self._page = None
        if self._context:
            try:
                self._context.close()
            except Exception as e:
                if "Event loop is closed" not in str(e):
                    logger.debug(f"Context close error: {e}")
            self._context = None
        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                if "Event loop is closed" not in str(e):
                    logger.debug(f"Browser close error: {e}")
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                if "Event loop is closed" not in str(e):
                    logger.debug(f"Playwright stop error: {e}")
            self._playwright = None

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
                "legend": [
                    f"  [{b['num']}] {b['selector']} ({b['a11y']})"
                    for b in self._badge_cache
                ],
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
            # Try normal fill first
            self._page.click(selector, timeout=_ACTION_TIMEOUT)
            self._page.fill(selector, text, timeout=_ACTION_TIMEOUT)
        except PlaywrightError:
            # Normal fill failed — try stealth mode (bypasses overlay divs)
            logger.debug(f"Normal fill failed, using stealth fill for {ref}")
            self.stealth_fill(selector, text)

    def stealth_fill(self, selector: str, text: str) -> None:
        """Fill input by dispatching keyboard events directly on element.
        
        Bypasses overlay divs that intercept pointer events (common on X/Twitter).
        Types character by character with human-like timing.
        """
        import random
        
        # Focus element and clear it via JS
        self._page.evaluate(
            "(sel) => {"
            "  const el = document.querySelector(sel);"
            "  if (!el) throw new Error('Element not found');"
            "  el.focus();"
            "  if (el.value !== undefined) el.value = '';"
            "  el.dispatchEvent(new Event('input', { bubbles: true }));"
            "  el.dispatchEvent(new Event('change', { bubbles: true }));"
            "}",
            selector,
        )
        
        # Type each character with human-like delay
        for char in text:
            # Dispatch keyboard events
            self._page.evaluate(
                "({sel, char}) => {"
                "  const el = document.querySelector(sel);"
                "  if (!el) return;"
                "  el.dispatchEvent(new KeyboardEvent('keydown', { key: char, bubbles: true }));"
                "  el.dispatchEvent(new KeyboardEvent('keypress', { key: char, bubbles: true }));"
                "  el.value = (el.value || '') + char;"
                "  el.dispatchEvent(new InputEvent('input', { bubbles: true }));"
                "  el.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true }));"
                "}",
                {"sel": selector, "char": char},
            )
            # Human-like typing delay (50-150ms)
            self._page.wait_for_timeout(random.uniform(50, 150))
        
        # Final change event
        self._page.evaluate(
            "(sel) => {"
            "  const el = document.querySelector(sel);"
            "  if (el) el.dispatchEvent(new Event('change', { bubbles: true }));"
            "}",
            selector,
        )

    def press(self, key: str) -> None:
        """Press keyboard key."""
        if key not in _ALLOWED_KEYS:
            raise ActionExecutionError(f"Disallowed key: {key!r}")

        try:
            self._page.keyboard.press(key)
        except PlaywrightError as e:
            raise ActionExecutionError(f"Key press failed: {e}") from e

    def scroll(self, direction: str = "down", amount: int = 500) -> None:
        """Scroll page using native DOM scroll (avoids SPA JS conflicts)."""
        try:
            # Use smooth scroll on the document element to avoid
            # SPA infinite-scroll JS from fighting the scroll position
            if direction == "down":
                self._page.evaluate(
                    f"""() => {{
                        const el = document.documentElement;
                        el.scrollTo({{
                            top: el.scrollTop + {amount},
                            behavior: 'smooth'
                        }});
                    }}"""
                )
            else:
                self._page.evaluate(
                    f"""() => {{
                        const el = document.documentElement;
                        el.scrollTo({{
                            top: el.scrollTop - {amount},
                            behavior: 'smooth'
                        }});
                    }}"""
                )
            # Brief wait for scroll to complete
            self._page.wait_for_timeout(300)
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

                # Actions that may cause navigation/DOM changes
                navigation_actions = {"click", "navigate", "open"}
                is_navigation = act in navigation_actions

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

                # After navigation actions, wait for DOM stability
                if is_navigation:
                    try:
                        # Wait for network idle then wait for DOM to settle
                        self._page.wait_for_load_state(
                            "networkidle", timeout=_ACTION_TIMEOUT
                        )
                        # Additional small delay for JS-rendered content
                        self._page.wait_for_timeout(500)
                    except Exception as e:
                        logger.debug(f"Wait for DOM stability after {act}: {e}")

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
        if self._page_crashed:
            # Try to recover — reset flag and test
            try:
                self._page.evaluate("1")
                self._page_crashed = False  # Recovered
                logger.info("Page recovered from crash state")
                return True
            except Exception:
                return False
        try:
            self._page.evaluate("1")
            return True
        except Exception:
            return False

    def reconnect(self) -> bool:
        """Reconnect to the browser via CDP.

        Useful when the connection was lost but the browser is still running.
        Returns True if reconnection succeeded.
        """
        if not self.cfg.cdp_url:
            logger.debug("Reconnect not available in non-CDP mode")
            return False

        self._page_crashed = False
        try:
            # Reconnect browser
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.cfg.cdp_url, timeout=self.cfg.timeout_ms
            )
            # Reuse existing context/page
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

            # Restore session if configured
            self._restore_session()

            # Re-register crash handler
            self._setup_crash_handler()

            logger.info(f"Reconnected to browser via CDP: {self.cfg.cdp_url}")
            return True
        except Exception as e:
            logger.warning(f"Reconnect failed: {e}")
            return False

    def check_page_state(self) -> dict:
        """Check current page state for issues.

        Returns:
            Dictionary with page state info including:
            - crashed: Whether the page has crashed
            - has_captcha: Whether a CAPTCHA was detected
            - is_error_page: Whether the page shows an error
            - error_text: Error message if detected
            - url: Current URL
            - title: Current page title
        """
        result = {
            "crashed": self._page_crashed,
            "has_captcha": False,
            "is_error_page": False,
            "error_text": "",
            "url": "",
            "title": "",
        }

        if self._page is None:
            result["crashed"] = True
            return result

        try:
            result["url"] = self._page.url
            result["title"] = self._page.title()
        except Exception:
            result["crashed"] = True
            return result

        # Check for CAPTCHAs
        try:
            for selector in self._CAPTCHA_SELECTORS:
                if self._page.query_selector(selector):
                    result["has_captcha"] = True
                    break
        except Exception:
            pass

        # Check for error pages
        try:
            body_text = self._page.evaluate("() => document.body?.innerText || ''")
            for indicator in self._ERROR_PAGE_INDICATORS:
                if indicator in body_text:
                    result["is_error_page"] = True
                    result["error_text"] = indicator
                    break
        except Exception:
            pass

        return result

    # ── Playwright Semantic Locators (instant, no Vision API needed) ───

    def find_element(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        text: str | None = None,
        label: str | None = None,
        placeholder: str | None = None,
        test_id: str | None = None,
        css: str | None = None,
        has_text: str | None = None,
    ) -> Any | None:
        """Find element using Playwright semantic locators.
        
        Returns the first matching Playwright Locator/ElementHandle or None.
        Tries each provided strategy in order until one succeeds.
        """
        return self._make_locator(
            role=role,
            name=name,
            text=text,
            label=label,
            placeholder=placeholder,
            css=css,
            has_text=has_text,
        )

    def locator_click(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        text: str | None = None,
        label: str | None = None,
        placeholder: str | None = None,
        css: str | None = None,
        has_text: str | None = None,
        timeout: int = _ACTION_TIMEOUT,
    ) -> bool:
        """Click element found via semantic locators.
        
        Returns True if clicked, False if not found.
        """
        locator = self._make_locator(
            role=role, name=name, text=text, label=label,
            placeholder=placeholder, css=css, has_text=has_text,
        )
        if locator is None:
            return False
        try:
            locator.click(timeout=timeout)
            return True
        except PlaywrightError as e:
            logger.debug(f"locator_click failed: {e}")
            return False

    def locator_fill(
        self,
        *,
        label: str | None = None,
        placeholder: str | None = None,
        role: str | None = None,
        name: str | None = None,
        css: str | None = None,
        text: str,
        timeout: int = _ACTION_TIMEOUT,
    ) -> bool:
        """Fill input element found via semantic locators.

        Playwright's fill() already handles focusing and selecting text.
        We do NOT call click() first — it can trigger dropdowns/modals.

        Returns True if filled, False if not found.
        """
        locator = self._make_locator(
            role=role, name=name, label=label,
            placeholder=placeholder, css=css,
        )
        if locator is None:
            return False
        try:
            locator.fill(text, timeout=timeout)
            return True
        except PlaywrightError as e:
            logger.debug(f"locator_fill failed: {e}")
            return False

    def locator_get_text(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        text: str | None = None,
        css: str | None = None,
        has_text: str | None = None,
    ) -> str | None:
        """Get text content of element found via locators.
        
        Returns text or None if not found.
        """
        locator = self._make_locator(
            role=role, name=name, text=text, css=css, has_text=has_text,
        )
        if locator is None:
            return None
        try:
            return locator.first.text_content()
        except PlaywrightError:
            return None

    def locator_exists(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        text: str | None = None,
        label: str | None = None,
        placeholder: str | None = None,
        css: str | None = None,
        has_text: str | None = None,
    ) -> bool:
        """Check if element exists using semantic locators."""
        locator = self._make_locator(
            role=role, name=name, text=text, label=label,
            placeholder=placeholder, css=css, has_text=has_text,
        )
        if locator is None:
            return False
        try:
            return locator.count() > 0
        except Exception:
            return False

    def get_interactive_elements(self) -> list[dict[str, Any]]:
        """Get list of all interactive elements.

        Uses Playwright's JS evaluation to extract elements with stable CSS selectors.
        Elements are sorted by visual position (top-to-bottom, left-to-right).

        Note: Playwright's native page.accessibility API is only available in the
        async API. For the sync API, we use JS evaluation which produces equivalent
        results with proper ARIA role/name extraction.
        """
        return self._get_elements_fallback()

    def _flatten_a11y_tree(self, node: dict, result: list[dict]) -> None:
        """Recursively flatten accessibility tree nodes."""
        if not node:
            return

        # Include this node if it has a role
        if node.get("role"):
            result.append(node)

        # Recurse into children
        for child in node.get("children", []):
            self._flatten_a11y_tree(child, result)

    @staticmethod
    def _css_escape(value: str) -> str:
        """Escape a CSS identifier value (equivalent to CSS.escape)."""
        # Escape backslash, quotes, and special characters
        return re.sub(r'(["\'\\])', r"\\\1", value)

    def _generate_selector_for_node(self, node: dict) -> str | None:
        """Generate a stable CSS selector for an accessibility tree node."""
        properties = node.get("properties", {})

        # 1. ID — always unique
        node_id = properties.get("id") or properties.get("id")
        if node_id and isinstance(node_id, str) and re.match(r"^[a-zA-Z][\w-]*$", node_id):
            return f"#{self._css_escape(node_id)}"

        # 2. data-testid
        test_id = properties.get("data-testid")
        if test_id and isinstance(test_id, str):
            return f'[data-testid="{test_id}"]'

        # 3. name attribute (for form inputs)
        name_attr = properties.get("name")
        if name_attr and isinstance(name_attr, str):
            tag = node.get("tagName", "").lower() or "input"
            return f'{tag}[name="{name_attr}"]'

        # 4. aria-label
        aria_label = node.get("name", "")
        if aria_label and len(aria_label) < 100:
            tag = node.get("tagName", "").lower() or "*"
            return f'{tag}[aria-label="{aria_label}"]'

        # 5. href for links
        href = properties.get("URL") or properties.get("href")
        if href and isinstance(href, str) and len(href) < 200:
            if not href.startswith(("javascript:", "#", "mailto:")):
                return f'a[href="{href}"]'

        # 6. role-based
        role = node.get("role", "")
        if role and role not in ("generic", "text", "statictext", "inlineTextBox"):
            return f'[role="{role}"]'

        # 7. Fallback: use the node's bounding box to find the element
        bbox = node.get("bounds")
        if bbox and len(bbox) == 4 and bbox[2] > 5 and bbox[3] > 5:
            return self._selector_from_bbox(bbox)

        return None

    def _selector_from_bbox(self, bbox: list) -> str | None:
        """Find element at bounding box coordinates and return its selector."""
        try:
            x, y, w, h = bbox
            cx, cy = x + w // 2, y + h // 2
            selector = self._page.evaluate(f"""() => {{
                const el = document.elementFromPoint({cx}, {cy});
                if (!el) return null;
                // Walk up to find the first interactive element
                let current = el;
                while (current && current !== document.body) {{
                    if (current.matches('a[href], button, input, select, textarea, [role], [tabindex]:not([tabindex="-1"])')) {{
                        if (current.id) return '#' + CSS.escape(current.id);
                        const testId = current.getAttribute('data-testid');
                        if (testId) return '[data-testid="' + testId + '"]';
                        const name = current.getAttribute('name');
                        if (name) return current.tagName.toLowerCase() + '[name="' + name + '"]';
                        const href = current.getAttribute('href');
                        if (href && href.length < 200 && !href.startsWith('#') && !href.startsWith('javascript:')) {{
                            return 'a[href="' + href + '"]';
                        }}
                        return current.tagName.toLowerCase();
                    }}
                    current = current.parentElement;
                }}
                return el.id ? '#' + CSS.escape(el.id) : el.tagName.toLowerCase();
            }}""")
            return selector
        except Exception:
            return None

    def _get_element_position(self, selector: str) -> tuple[int, int]:
        """Get visual position (y, x) of element matching selector."""
        try:
            result = self._page.evaluate(
                "() => { const el = document.querySelector(arguments[0]); "
                "if (!el) return [99999, 99999]; "
                "const rect = el.getBoundingClientRect(); "
                "return [Math.round(rect.top), Math.round(rect.left)]; }",
                selector,
            )
            if result and len(result) == 2:
                return (result[0], result[1])
        except Exception:
            pass
        return (99999, 99999)

    def _get_elements_fallback(self) -> list[dict[str, Any]]:
        """Fallback JS-based element extraction when a11y API fails."""
        try:
            elements = self._page.evaluate("""() => {
                const interactiveSelectors = [
                    'a[href]', 'button', 'input:not([type="hidden"])',
                    'select', 'textarea',
                    '[role="button"]', '[role="link"]', '[role="textbox"]',
                    '[role="combobox"]', '[role="searchbox"]', '[role="tab"]',
                    '[role="menuitem"]', '[role="checkbox"]', '[role="radio"]',
                    '[role="slider"]', '[role="spinbutton"]',
                    '[tabindex]:not([tabindex="-1"])',
                    'summary', 'details'
                ];
                const selector = interactiveSelectors.join(', ');
                const allElements = document.querySelectorAll(selector);
                const result = [];
                const seen = new Set();

                function generateSelector(el) {
                    if (!el || el === document.documentElement) return 'html';
                    if (el.id && /^[a-zA-Z][\\w-]*$/.test(el.id)) {
                        return `#${CSS.escape(el.id)}`;
                    }
                    const testId = el.getAttribute('data-testid');
                    if (testId && /^[a-zA-Z][\\w-]*$/.test(testId)) {
                        return `[data-testid="${testId}"]`;
                    }
                    const name = el.getAttribute('name');
                    if (name && /^[a-zA-Z][\\w-]*$/.test(name)) {
                        return `${el.tagName.toLowerCase()}[name="${name}"]`;
                    }
                    const ariaLabel = el.getAttribute('aria-label');
                    if (ariaLabel && ariaLabel.length > 0 && ariaLabel.length < 100) {
                        return `${el.tagName.toLowerCase()}[aria-label="${ariaLabel}"]`;
                    }
                    const type = el.getAttribute('type');
                    if (el.tagName.toLowerCase() === 'input' && type) {
                        return `input[type="${type}"]`;
                    }
                    if (el.tagName.toLowerCase() === 'a') {
                        const href = el.getAttribute('href');
                        if (href && href.length < 200 &&
                            !href.startsWith('javascript:') &&
                            !href.startsWith('#') &&
                            !href.startsWith('mailto:')) {
                            return `a[href="${href}"]`;
                        }
                    }
                    return el.tagName.toLowerCase();
                }

                function isVisible(el) {
                    let current = el;
                    while (current && current !== document.documentElement) {
                        const style = window.getComputedStyle(current);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                            return false;
                        }
                        current = current.parentElement;
                    }
                    const rect = el.getBoundingClientRect();
                    return rect.width > 5 && rect.height > 5;
                }

                allElements.forEach((el) => {
                    if (!isVisible(el) || seen.has(el)) return;
                    seen.add(el);

                    const role = el.getAttribute('role') || el.tagName.toLowerCase() || 'unknown';
                    const name = el.getAttribute('aria-label') ||
                                 el.getAttribute('placeholder') ||
                                 el.getAttribute('title') ||
                                 el.textContent?.trim().slice(0, 80) || '';
                    const sel = generateSelector(el);
                    const rect = el.getBoundingClientRect();

                    result.push({
                        role, name,
                        tagName: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || '',
                        id: el.id || '',
                        selector: sel,
                        href: el.getAttribute('href') || '',
                        _y: Math.round(rect.top),
                        _x: Math.round(rect.left)
                    });
                });

                result.sort((a, b) => {
                    if (Math.abs(a._y - b._y) < 20) return a._x - b._x;
                    return a._y - b._y;
                });

                return result.slice(0, 80).map(el => {
                    const { _y, _x, ...rest } = el;
                    return rest;
                });
            }""")
            return elements or []
        except Exception as e:
            logger.debug(f"Fallback element extraction failed: {e}")
            return []

    def get_page_summary(self) -> dict[str, Any]:
        """Get quick page summary without screenshot.
        
        Returns URL, title, and interactive element count.
        """
        try:
            url = self._page.url
            title = self._page.title()
            elements = self.get_interactive_elements()
            return {
                "url": url,
                "title": title,
                "interactive_count": len(elements),
                "elements": elements[:50],  # Limit to first 50 for prompt
            }
        except Exception as e:
            logger.debug(f"Failed to get page summary: {e}")
            return {"url": "", "title": "", "interactive_count": 0, "elements": []}

    def _make_locator(self, **kwargs):
        """Create a Playwright locator from keyword arguments.
        
        Tries strategies in order of specificity and returns the first match.
        """
        
        role = kwargs.pop("role", None)
        name = kwargs.pop("name", None)
        text = kwargs.pop("text", None)
        label = kwargs.pop("label", None)
        placeholder = kwargs.pop("placeholder", None)
        test_id = kwargs.pop("test_id", None)
        css = kwargs.pop("css", None)
        has_text = kwargs.pop("has_text", None)
        
        # Build candidate locators in order of preference
        candidates = []
        
        # Most specific: role + name combination
        if role and name:
            candidates.append(self._page.get_by_role(role, name=name))
        
        # Role-based locators
        if role:
            candidates.append(self._page.get_by_role(role))
        
        # Text content matching
        if text:
            candidates.append(self._page.get_by_text(text))
        
        # Label matching for form inputs
        if label:
            candidates.append(self._page.get_by_label(label))
        
        # Placeholder text matching
        if placeholder:
            candidates.append(self._page.get_by_placeholder(placeholder))
        
        # Test ID matching
        if test_id:
            candidates.append(self._page.get_by_test_id(test_id))
        
        # Raw CSS selector as last resort
        if css:
            candidates.append(self._page.locator(css))
        
        if not candidates:
            return None
        
        # Try each candidate and return the first one that has elements
        for loc in candidates:
            if has_text:
                loc = loc.filter(has_text=has_text)
            try:
                if loc.count() > 0:
                    return loc
            except Exception:
                continue

        # No candidates matched — return None (caller handles gracefully)
        return None
