"""Playwright-based browser controller with persistent CDP connection."""

from __future__ import annotations

import logging
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
                "headless": True,
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
                logger.info("Launched new headless browser")
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
            # Never close CDP-connected browser — user owns it
            logger.debug("CDP mode: skipping browser close (user controls Brave)")
            return

        # Save session before closing owned browser
        self.save_session()

        # Close each resource independently to prevent leaks on partial failure
        if self._page:
            try:
                self._page.close()
            except Exception as e:
                logger.debug(f"Page close error: {e}")
        if self._context:
            try:
                self._context.close()
            except Exception as e:
                logger.debug(f"Context close error: {e}")
        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                logger.debug(f"Browser close error: {e}")
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.debug(f"Playwright stop error: {e}")

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
            return False
        try:
            self._page.evaluate("1")
            return True
        except Exception:
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
        """Get list of all interactive elements via JavaScript evaluation.

        Returns list of dicts with role, name, selector, and metadata.
        Elements are ordered by visual position (top-to-bottom, left-to-right)
        so the model can reference "first video" meaningfully.
        """
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
                    if (el.id) return `#${el.id}`;

                    let sel = el.tagName.toLowerCase();

                    // Add class if unique
                    if (el.classList.length > 0) {
                        const classes = Array.from(el.classList)
                            .filter(c => !c.startsWith('css-') && !c.startsWith('yt-') && c.length < 20)
                            .slice(0, 2)
                            .map(c => CSS.escape(c))
                            .join('.');
                        if (classes) sel += `.${classes}`;
                    }

                    // Add nth-child if needed for uniqueness
                    const parent = el.parentElement;
                    if (parent) {
                        const siblings = Array.from(parent.children)
                            .filter(s => s.tagName === el.tagName);
                        if (siblings.length > 1) {
                            const idx = siblings.indexOf(el) + 1;
                            sel += `:nth-of-type(${idx})`;
                        }
                    }

                    return sel;
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

                function getVisualPosition(el) {
                    const rect = el.getBoundingClientRect();
                    return {
                        top: rect.top,
                        left: rect.left,
                        y: Math.round(rect.top),
                        x: Math.round(rect.left)
                    };
                }

                allElements.forEach((el) => {
                    if (!isVisible(el)) return;
                    if (seen.has(el)) return;
                    seen.add(el);

                    const role = el.getAttribute('role') ||
                                 el.tagName.toLowerCase() ||
                                 'unknown';
                    const name = el.getAttribute('aria-label') ||
                                 el.getAttribute('aria-labelledby') ||
                                 el.getAttribute('placeholder') ||
                                 el.getAttribute('title') ||
                                 el.getAttribute('alt') ||
                                 el.textContent?.trim().slice(0, 80) ||
                                 el.id ||
                                 '';

                    const sel = generateSelector(el);
                    const pos = getVisualPosition(el);

                    result.push({
                        role: role,
                        name: name,
                        tagName: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || '',
                        id: el.id || '',
                        selector: sel,
                        href: el.getAttribute('href') || '',
                        _visualY: pos.y,
                        _visualX: pos.x
                    });
                });

                // Sort by visual position (top-to-bottom, then left-to-right)
                result.sort((a, b) => {
                    // Group elements within 20px vertically
                    const rowDiff = Math.abs(a._visualY - b._visualY);
                    if (rowDiff < 20) return a._visualX - b._visualX;
                    return a._visualY - b._visualY;
                });

                // Remove visual position metadata from output
                return result.slice(0, 80).map(el => {
                    const { _visualY, _visualX, ...rest } = el;
                    return rest;
                });
            }""")
            return elements or []
        except Exception as e:
            logger.debug(f"Failed to get interactive elements: {e}")
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
