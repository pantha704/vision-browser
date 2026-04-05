"""MCP Server for Vision Browser — browser automation via Model Context Protocol.

Exposes browser automation as MCP tools compatible with Claude, Cursor,
VS Code, and other MCP clients.

Tools:
- vision_browser_navigate: Navigate to a URL
- vision_browser_screenshot: Take a screenshot of the current page
- vision_browser_get_elements: Get interactive elements with their indices
- vision_browser_click: Click an element by index
- vision_browser_fill: Fill an input field by index
- vision_browser_press: Press a keyboard key
- vision_browser_scroll: Scroll the page
- vision_browser_execute: Execute a high-level natural language task
- vision_browser_health: Check server health and connection status
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vision_browser.config import AppConfig
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.vision import VisionClient

logger = logging.getLogger(__name__)

# ── Server Instance ────────────────────────────────────────────────────

mcp = FastMCP(
    name="vision-browser",
    instructions="Browser automation with Playwright + AI vision. Use navigate() to go to URLs, get_elements() to see interactive elements, then click/fill to interact. Or use execute() for high-level natural language tasks.",
)

# ── Browser State (global, managed by server lifecycle) ────────────────

_browser: PlaywrightBrowser | None = None
_vision: VisionClient | None = None
_cfg: AppConfig | None = None
_element_cache: list[dict[str, Any]] = []
_server_start_time: float = 0.0


def _get_browser() -> PlaywrightBrowser:
    """Get or create browser instance."""
    global _browser, _cfg
    if _browser is None:
        _cfg = AppConfig()
        _cfg.browser.cdp_url = "http://localhost:9222"
        _browser = PlaywrightBrowser(_cfg.browser)
    return _browser


def _get_vision() -> VisionClient:
    """Get or create vision client with orchestrator config."""
    global _vision, _cfg
    if _vision is None:
        if _cfg is None:
            _cfg = AppConfig()
        _vision = VisionClient(
            _cfg.vision,
            {
                "retry_attempts": _cfg.orchestrator.retry_attempts,
                "retry_backoff_base": _cfg.orchestrator.retry_backoff_base,
                "rate_limit_delay": _cfg.orchestrator.rate_limit_delay,
            },
        )
    return _vision


# ── Tool: Health ───────────────────────────────────────────────────────

@mcp.tool()
def vision_browser_health() -> dict:
    """Check server health and browser connection status.

    Returns:
        Dictionary with server uptime, browser connection status, and version.
    """
    global _browser, _server_start_time
    if _server_start_time == 0.0:
        _server_start_time = time.monotonic()
    uptime = time.monotonic() - _server_start_time
    browser_ok = False
    url = ""
    title = ""

    if _browser is not None:
        try:
            browser_ok = _browser.is_alive()
            if browser_ok:
                url = _browser.get_url()
                title = _browser.get_title()
        except Exception:
            browser_ok = False

    return {
        "status": "healthy" if browser_ok else "disconnected",
        "version": "0.7.0",
        "uptime_seconds": round(uptime, 1),
        "browser_connected": browser_ok,
        "current_url": url,
        "current_title": title,
    }


# ── Tool: Navigate ─────────────────────────────────────────────────────

@mcp.tool()
def vision_browser_navigate(url: str) -> dict:
    """Navigate the browser to a URL.

    Args:
        url: The URL to navigate to (must start with http:// or https://).

    Returns:
        Dictionary with navigation result including final URL and page title.

    Example:
        vision_browser_navigate(url="https://www.google.com")
    """
    global _element_cache
    _element_cache = []

    browser = _get_browser()

    if not url.lower().startswith(("http://", "https://")):
        return {
            "success": False,
            "error": "URL must start with http:// or https://",
            "suggestion": f"Try: https://{url}",
        }

    try:
        browser.open(url)
        page_url = browser.get_url()
        page_title = browser.get_title()
        elements = browser.get_interactive_elements()
        _element_cache = elements

        return {
            "success": True,
            "url": page_url,
            "title": page_title,
            "interactive_elements": len(elements),
            "message": f"Navigated to {page_url}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Check the URL and try again. Ensure the browser is running.",
        }


# ── Tool: Get Elements ─────────────────────────────────────────────────

@mcp.tool()
def vision_browser_get_elements() -> dict:
    """Get all interactive elements on the current page.

    Returns a numbered list of interactive elements with their CSS selectors,
    roles, and visible text. Use the element index with click/fill tools.

    Returns:
        Dictionary with current URL, title, and numbered element list.

    Example:
        # Returns elements like:
        # [1] role=searchbox "Search" -> input#search
        # [2] role=button "Google Search" -> button
    """
    global _element_cache
    browser = _get_browser()

    try:
        url = browser.get_url()
        title = browser.get_title()
        elements = browser.get_interactive_elements()
        _element_cache = elements

        # Format elements as numbered list
        element_list = []
        for i, el in enumerate(elements[:50], 1):
            role = el.get("role", "")
            name = el.get("name", "")
            selector = el.get("selector", "")
            href = el.get("href", "")

            item = {
                "index": i,
                "role": role,
                "name": name[:60] if name else "",
                "selector": selector,
            }
            if href and "/watch" in href:
                item["type"] = "video_link"
            element_list.append(item)

        if len(elements) > 50:
            element_list.append({"note": f"... and {len(elements) - 50} more"})

        return {
            "success": True,
            "url": url,
            "title": title,
            "total_elements": len(elements),
            "elements": element_list,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Ensure the browser is connected and a page is loaded.",
        }


# ── Tool: Click ────────────────────────────────────────────────────────

@mcp.tool()
def vision_browser_click(element: int) -> dict:
    """Click an interactive element by its index number.

    First call vision_browser_get_elements to see available elements and their indices.

    Args:
        element: The index number of the element to click (1-based, from get_elements).

    Returns:
        Dictionary with click result including new URL and title if navigation occurred.

    Example:
        # After get_elements shows: [3] role=link "About" -> a.about-link
        vision_browser_click(element=3)
    """
    global _element_cache
    browser = _get_browser()

    if element < 1 or element > len(_element_cache):
        return {
            "success": False,
            "error": f"Element index {element} out of range (1-{len(_element_cache)})",
            "suggestion": "Call vision_browser_get_elements first to see available elements.",
        }

    el = _element_cache[element - 1]
    selector = el.get("selector", "")

    if not selector:
        return {
            "success": False,
            "error": f"Element {element} has no CSS selector",
            "element_info": el,
            "suggestion": "Try a different element or refresh with get_elements.",
        }

    try:
        browser._page.click(selector, timeout=30000)
        try:
            browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        # Refresh element cache after navigation
        url = browser.get_url()
        title = browser.get_title()
        _element_cache = browser.get_interactive_elements()

        return {
            "success": True,
            "clicked": f"Element {element} ({el.get('role', '')}: {el.get('name', '')[:40]})",
            "url": url,
            "title": title,
            "new_elements_available": len(_element_cache),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:200],
            "element_info": el,
            "suggestion": f"Element {element} may not be clickable. Try a different element or call get_elements to refresh.",
        }


# ── Tool: Fill ─────────────────────────────────────────────────────────

@mcp.tool()
def vision_browser_fill(element: int, text: str) -> dict:
    """Fill an input field with text by its index number.

    First call vision_browser_get_elements to see available input elements.

    Args:
        element: The index number of the input element to fill (1-based).
        text: The text to type into the input field.

    Returns:
        Dictionary with fill result.

    Example:
        # After get_elements shows: [1] role=searchbox "Search" -> input#search
        vision_browser_fill(element=1, text="Python tutorial")
    """
    global _element_cache
    browser = _get_browser()

    if element < 1 or element > len(_element_cache):
        return {
            "success": False,
            "error": f"Element index {element} out of range (1-{len(_element_cache)})",
            "suggestion": "Call vision_browser_get_elements first to see available elements.",
        }

    el = _element_cache[element - 1]
    selector = el.get("selector", "")

    if not selector:
        return {
            "success": False,
            "error": f"Element {element} has no CSS selector",
            "suggestion": "Try a different element or refresh with get_elements.",
        }

    try:
        browser._page.fill(selector, text, timeout=30000)
        return {
            "success": True,
            "filled": f"Element {element} with: {text[:50]}",
            "message": "Text entered. Press Enter (vision_browser_press) to submit if needed.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:200],
            "element_info": el,
            "suggestion": f"Element {element} may not be a text input. Try a different element.",
        }


# ── Tool: Press ────────────────────────────────────────────────────────

_ALLOWED_KEYS = {
    "Enter", "Tab", "Escape", "Backspace", "Delete",
    "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
    "Home", "End", "PageUp", "PageDown", " ",
    "Control+a", "Control+c", "Control+v", "Control+x", "Control+z",
}


@mcp.tool()
def vision_browser_press(key: str) -> dict:
    """Press a keyboard key.

    Common keys: Enter, Tab, Escape, Backspace, Delete, ArrowLeft, ArrowRight,
    ArrowUp, ArrowDown, Home, End, PageUp, PageDown.
    Also supports: Control+a, Control+c, Control+v, Control+x, Control+z.

    Args:
        key: The key to press.

    Returns:
        Dictionary with press result including new URL if navigation occurred.

    Example:
        vision_browser_press(key="Enter")  # Submit a form
        vision_browser_press(key="Control+c")  # Copy
    """
    global _element_cache
    browser = _get_browser()

    if key not in _ALLOWED_KEYS:
        return {
            "success": False,
            "error": f"Key '{key}' not allowed",
            "allowed_keys": sorted(_ALLOWED_KEYS),
            "suggestion": "Use one of the allowed keys listed above.",
        }

    try:
        browser._page.keyboard.press(key)
        if key == "Enter":
            try:
                browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

        # Refresh element cache after potential navigation
        url = browser.get_url()
        title = browser.get_title()
        _element_cache = browser.get_interactive_elements()

        return {
            "success": True,
            "key_pressed": key,
            "url": url,
            "title": title,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Check if the page is responsive and try again.",
        }


# ── Tool: Scroll ───────────────────────────────────────────────────────

@mcp.tool()
def vision_browser_scroll(direction: str = "down", amount: int = 500) -> dict:
    """Scroll the page up or down.

    Args:
        direction: "up" or "down" (default: "down").
        amount: Number of pixels to scroll (default: 500).

    Returns:
        Dictionary with scroll result.

    Example:
        vision_browser_scroll(direction="down", amount=800)
    """
    global _element_cache
    browser = _get_browser()

    if direction not in ("up", "down"):
        return {
            "success": False,
            "error": f"Direction must be 'up' or 'down', got '{direction}'",
            "suggestion": "Use direction='down' to scroll down, direction='up' to scroll up.",
        }

    try:
        browser.scroll(direction, amount)
        # Refresh elements after scroll (new elements may be visible)
        _element_cache = browser.get_interactive_elements()

        return {
            "success": True,
            "scrolled": f"{direction} by {amount}px",
            "new_elements_available": len(_element_cache),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Check if the page is responsive and try again.",
        }


# ── Tool: Screenshot ───────────────────────────────────────────────────

@mcp.tool()
def vision_browser_screenshot(full_page: bool = False) -> dict:
    """Take a screenshot of the current page.

    For AI clients that support image display, the screenshot will be shown.
    For text-only clients, returns page state information.

    Args:
        full_page: Whether to capture the full scrollable page (default: False, captures viewport).

    Returns:
        Dictionary with screenshot path and page state.
    """
    import tempfile

    browser = _get_browser()

    try:
        shot_path = Path(tempfile.gettempdir()) / f"vision-browser-mcp-{int(time.time())}.png"
        browser._page.screenshot(path=str(shot_path), full_page=full_page)

        url = browser.get_url()
        title = browser.get_title()

        return {
            "success": True,
            "screenshot_path": str(shot_path),
            "url": url,
            "title": title,
            "full_page": full_page,
            "message": "Screenshot saved. If your client supports images, it should be displayed. Otherwise, see the page details above.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "Check if the browser is running and the page is loaded.",
        }


# ── Tool: Execute Task (High-Level) ────────────────────────────────────

@mcp.tool()
def vision_browser_execute(task: str) -> dict:
    """Execute a high-level natural language task using AI reasoning.

    This is the most powerful tool — describe what you want to accomplish
    in natural language and the AI will plan and execute it automatically.

    Args:
        task: Natural language description of what to accomplish.
            Examples:
            - "Search for 'Python tutorial' on Google"
            - "Go to GitHub and find the top Python repositories"
            - "Fill the login form with user@example.com and password123"

    Returns:
        Dictionary with task execution result including status, turns taken,
        actions performed, and final page state.

    Note:
        This requires NVIDIA API key (NVIDIA_API_KEY environment variable).
        The task may take 10-60 seconds depending on complexity.
    """
    browser = _get_browser()
    vision = _get_vision()

    try:
        url = browser.get_url()
        title = browser.get_title()

        # Get elements for context
        elements = browser.get_interactive_elements()

        # Build prompt for text-only analysis
        element_lines = []
        for i, el in enumerate(elements[:30], 1):
            role = el.get("role", "")
            name = el.get("name", "")
            if name:
                element_lines.append(f"  [{i}] role={role}, name={name}")
            else:
                element_lines.append(f"  [{i}] role={role}")

        element_text = "\n".join(element_lines) if element_lines else "  (none)"

        system_prompt = """\
You are a browser automation agent. Analyze the page state and task, then return actions as JSON.

AVAILABLE ACTIONS:
- click: Click element by index (e.g., {"action": "click", "element": 5})
- fill: Fill input by index with text (e.g., {"action": "fill", "element": 3, "text": "hello"})
- press: Press a key (e.g., {"action": "press", "key": "Enter"})
- scroll: Scroll page (e.g., {"action": "scroll", "direction": "down"})
- navigate: Go to a URL (e.g., {"action": "navigate", "url": "https://example.com"})

RULES:
1. Use the ELEMENT NUMBER to reference elements.
2. Return ONLY valid JSON.
3. Set "done" to true ONLY when task is complete.

RESPONSE FORMAT:
{"actions": [{"action": "fill", "element": 3, "text": "query"}], "done": false, "reasoning": "why"}
"""

        user_prompt = (
            f"TASK: {task}\n\n"
            f"CURRENT PAGE:\n"
            f"URL: {url}\n"
            f"TITLE: {title}\n\n"
            f"INTERACTIVE ELEMENTS:\n{element_text}\n\n"
            f"Return ONLY JSON with actions to accomplish the task."
        )

        result = vision.analyze_page(
            url=url,
            title=title,
            elements=elements,
            task=task,
            system_prompt=system_prompt,
            prompt_override=user_prompt,
        )

        actions = result.get("actions", [])
        done = result.get("done", False)
        reasoning = result.get("reasoning", "")

        # Execute actions
        success_count = 0
        action_results = []
        for action in actions:
            act = action.get("action", "")
            element_idx = action.get("element")

            try:
                if act == "click" and element_idx:
                    if 1 <= element_idx <= len(elements):
                        selector = elements[element_idx - 1].get("selector")
                        if selector:
                            browser._page.click(selector, timeout=30000)
                            success_count += 1
                            action_results.append(f"✅ Clicked element {element_idx}")
                            try:
                                browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
                            except Exception:
                                pass
                        else:
                            action_results.append(f"❌ Element {element_idx} has no selector")
                    else:
                        action_results.append(f"❌ Element {element_idx} out of range")

                elif act == "fill" and element_idx:
                    if 1 <= element_idx <= len(elements):
                        selector = elements[element_idx - 1].get("selector")
                        text = action.get("text", "")
                        if selector:
                            browser._page.fill(selector, text, timeout=30000)
                            success_count += 1
                            action_results.append(f"✅ Filled element {element_idx} with: {text[:40]}")
                        else:
                            action_results.append(f"❌ Element {element_idx} has no selector")
                    else:
                        action_results.append(f"❌ Element {element_idx} out of range")

                elif act == "press":
                    key = action.get("key", "Enter")
                    browser._page.keyboard.press(key)
                    success_count += 1
                    action_results.append(f"✅ Pressed {key}")
                    if key == "Enter":
                        try:
                            browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
                        except Exception:
                            pass

                elif act == "scroll":
                    direction = action.get("direction", "down")
                    browser.scroll(direction)
                    success_count += 1
                    action_results.append(f"✅ Scrolled {direction}")

                elif act == "navigate":
                    nav_url = action.get("url", "")
                    if nav_url.startswith(("http://", "https://")):
                        browser.open(nav_url)
                        success_count += 1
                        action_results.append(f"✅ Navigated to {nav_url}")

                else:
                    action_results.append(f"⚠️ Unknown action: {act}")

            except Exception as e:
                action_results.append(f"❌ Failed: {str(e)[:80]}")

        # Get final page state
        final_url = browser.get_url()
        final_title = browser.get_title()

        return {
            "success": True,
            "task": task,
            "reasoning": reasoning,
            "actions_planned": len(actions),
            "actions_succeeded": success_count,
            "actions_failed": len(actions) - success_count,
            "action_details": action_results,
            "done": done,
            "final_url": final_url,
            "final_title": final_title,
        }

    except Exception as e:
        return {
            "success": False,
            "task": task,
            "error": str(e),
            "suggestion": "Check that NVIDIA_API_KEY is set and the browser is running.",
        }


# ── Server Entry Point ─────────────────────────────────────────────────

def main() -> None:
    """Run the MCP server via stdio."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol, stderr for logs
    )

    mcp.run()


if __name__ == "__main__":
    main()
