#!/usr/bin/env python3
"""
MCP Server for Vision Browser.

Provides browser automation via Playwright + AI reasoning tools.
Connect to a running Brave browser via CDP (Chrome DevTools Protocol).

Usage:
    # Start Brave with remote debugging first:
    brave-browser --remote-debugging-port=9222 --no-sandbox &

    # Then run this MCP server:
    uv run vision-browser-mcp

MCP Client Configuration (e.g., Claude Desktop, Cursor):
    {
      "mcpServers": {
        "vision-browser": {
          "command": "uv",
          "args": ["run", "vision-browser-mcp"],
          "cwd": "/path/to/vision-browser",
          "env": {
            "NVIDIA_API_KEY": "nvapi-..."
          }
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, ConfigDict, Field

from vision_browser.config import AppConfig
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.vision import VisionClient

logger = logging.getLogger(__name__)

# ── Server ─────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="vision_browser_mcp",
    instructions=(
        "Browser automation with Playwright + AI vision. "
        "Use vision_browser_navigate to go to URLs, "
        "vision_browser_get_elements to see interactive elements, "
        "then vision_browser_click or vision_browser_fill to interact. "
        "Or use vision_browser_execute for high-level natural language tasks."
    ),
)

# ── Lifespan ───────────────────────────────────────────────────────────


class BrowserState(BaseModel):
    """Shared browser state managed by the lifespan."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    browser: Optional[PlaywrightBrowser] = None
    vision: Optional[VisionClient] = None
    element_cache: List[Dict[str, Any]] = []
    started_at: float = 0.0
    config: Optional[AppConfig] = None


@asynccontextmanager
async def app_lifespan() -> AsyncIterator[Dict[str, Any]]:
    """Manage browser instance across the server lifetime."""
    state = BrowserState()
    state.started_at = time.monotonic()

    try:
        cfg = AppConfig()
        cfg.browser.cdp_url = os.environ.get(
            "VISION_BROWSER_CDP_URL", "http://localhost:9222"
        )
        state.config = cfg
        state.browser = PlaywrightBrowser(cfg.browser)
        state.vision = VisionClient(
            cfg.vision,
            {
                "retry_attempts": cfg.orchestrator.retry_attempts,
                "retry_backoff_base": cfg.orchestrator.retry_backoff_base,
                "rate_limit_delay": cfg.orchestrator.rate_limit_delay,
            },
        )
        logger.info("Browser connected via CDP")
    except Exception as e:
        logger.error(f"Failed to connect browser: {e}")
        state.browser = None

    state_dict = {"state": state}
    try:
        yield state_dict
    finally:
        # Cleanup on shutdown
        if state.browser is not None:
            try:
                state.browser.close()
                logger.info("Browser closed")
            except Exception as e:
                logger.debug(f"Browser close error: {e}")


mcp = FastMCP(
    name="vision_browser_mcp",
    instructions=(
        "Browser automation with Playwright + AI reasoning. "
        "Navigate pages, find and click elements, fill forms, scroll, "
        "and execute high-level tasks using natural language."
    ),
    lifespan=app_lifespan,
)


# ── Input Models ───────────────────────────────────────────────────────


class NavigateInput(BaseModel):
    """Input for navigation operations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(
        ...,
        description="URL to navigate to (must start with http:// or https://)",
        min_length=8,
        max_length=2000,
        examples=["https://www.google.com", "https://youtube.com"],
    )


class ClickInput(BaseModel):
    """Input for click operations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    element: int = Field(
        ...,
        description="Element index to click (1-based, from vision_browser_get_elements)",
        ge=1,
        le=1000,
        examples=[1, 3, 5],
    )


class FillInput(BaseModel):
    """Input for fill operations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    element: int = Field(
        ...,
        description="Element index to fill (1-based, from vision_browser_get_elements)",
        ge=1,
        le=1000,
        examples=[1, 2],
    )
    text: str = Field(
        ...,
        description="Text to enter into the input field",
        min_length=0,
        max_length=5000,
        examples=["search query", "user@example.com"],
    )


class PressInput(BaseModel):
    """Input for keyboard operations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    key: str = Field(
        ...,
        description=(
            "Key to press. Allowed: Enter, Tab, Escape, Backspace, Delete, "
            "ArrowLeft, ArrowRight, ArrowUp, ArrowDown, Home, End, PageUp, "
            "PageDown, Space, Control+a, Control+c, Control+v, Control+x, Control+z"
        ),
        examples=["Enter", "Tab", "Control+c"],
    )


class ScrollInput(BaseModel):
    """Input for scroll operations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    direction: str = Field(
        default="down",
        description="Scroll direction: 'up' or 'down'",
        examples=["down", "up"],
    )
    amount: int = Field(
        default=500,
        description="Pixels to scroll",
        ge=50,
        le=5000,
        examples=[300, 500, 800],
    )


class ScreenshotInput(BaseModel):
    """Input for screenshot operations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_page: bool = Field(
        default=False,
        description="Whether to capture the full scrollable page (false = viewport only)",
        examples=[True, False],
    )


class ExecuteInput(BaseModel):
    """Input for high-level task execution."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task: str = Field(
        ...,
        description=(
            "Natural language description of what to accomplish. "
            "Examples: 'Search for Python tutorials on YouTube', "
            "'Fill the login form with user@example.com and password123'"
        ),
        min_length=5,
        max_length=2000,
        examples=[
            "Search for 'machine learning' on Google",
            "Find the latest news about AI on Hacker News",
        ],
    )


# ── Allowed Keys ───────────────────────────────────────────────────────

_ALLOWED_KEYS = frozenset({
    "Enter", "Tab", "Escape", "Backspace", "Delete",
    "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
    "Home", "End", "PageUp", "PageDown", " ",
    "Control+a", "Control+c", "Control+v", "Control+x", "Control+z",
})


# ── Shared Helpers ─────────────────────────────────────────────────────


def _get_state(ctx: Context) -> BrowserState:
    """Extract browser state from context."""
    return ctx.request_context.lifespan_state["state"]


def _refresh_elements(state: BrowserState) -> List[Dict[str, Any]]:
    """Refresh the element cache and return the list."""
    if state.browser is None:
        return []
    state.element_cache = state.browser.get_interactive_elements()
    return state.element_cache


def _format_elements(
    elements: List[Dict[str, Any]], max_count: int = 50
) -> str:
    """Format elements as a numbered list for display."""
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
            short = name[:50] + "..." if len(name) > 50 else name
            parts.append(f'"{short}"')
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


def _wait_for_load(browser: PlaywrightBrowser) -> None:
    """Wait for DOM content to load after navigation actions."""
    try:
        browser._page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass


# ── Tool: Health ───────────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_health",
    annotations={
        "title": "Check Browser Health",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def vision_browser_health() -> str:
    """Check server health and browser connection status.

    Returns JSON with server uptime, browser status, current URL, and title.
    Use this to verify the browser is connected before running other tools.

    Returns:
        str: JSON with health status:
        {
            "status": "healthy" | "disconnected",
            "uptime_seconds": float,
            "browser_connected": bool,
            "current_url": str,
            "current_title": str
        }
    """
    state = _get_state(ctx=None)  # type: ignore
    uptime = time.monotonic() - state.started_at

    browser_ok = False
    url = ""
    title = ""

    if state.browser is not None:
        try:
            browser_ok = state.browser.is_alive()
            if browser_ok:
                url = state.browser.get_url()
                title = state.browser.get_title()
        except Exception:
            browser_ok = False

    result = {
        "status": "healthy" if browser_ok else "disconnected",
        "version": "0.7.0",
        "uptime_seconds": round(uptime, 1),
        "browser_connected": browser_ok,
        "current_url": url,
        "current_title": title,
    }
    return json.dumps(result, indent=2)


# ── Tool: Navigate ─────────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_navigate",
    annotations={
        "title": "Navigate to URL",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def vision_browser_navigate(params: NavigateInput) -> str:
    """Navigate the browser to a URL.

    Opens the specified URL and waits for the page to load.
    After navigation, use vision_browser_get_elements to see available elements.

    Args:
        params.url: Full URL starting with http:// or https://

    Returns:
        str: JSON with navigation result:
        {
            "success": bool,
            "url": str (final URL after redirects),
            "title": str,
            "interactive_elements": int (count of available elements)
        }

    Examples:
        - Go to Google: url="https://www.google.com"
        - Go to YouTube: url="https://youtube.com"
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})

    url = params.url
    if not url.lower().startswith(("http://", "https://")):
        return json.dumps({
            "success": False,
            "error": "URL must start with http:// or https://",
            "suggestion": f"Try: https://{url}",
        })

    try:
        state.browser.open(url)
        elements = _refresh_elements(state)
        result = {
            "success": True,
            "url": state.browser.get_url(),
            "title": state.browser.get_title(),
            "interactive_elements": len(elements),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)[:200],
            "suggestion": "Check the URL and ensure the browser is running.",
        })


# ── Tool: Get Elements ─────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_get_elements",
    annotations={
        "title": "Get Interactive Elements",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def vision_browser_get_elements() -> str:
    """Get all interactive elements on the current page.

    Returns a numbered list of elements with their roles, text, and CSS selectors.
    Use the element index (1-based) with vision_browser_click or vision_browser_fill.

    Call this BEFORE clicking or filling to see what elements are available.
    Elements are ordered by visual position (top-to-bottom, left-to-right).

    Returns:
        str: Markdown list of elements with index, role, name, and selector.
        Or JSON error if browser is not connected.

    Example output:
        ## Page: Google (https://www.google.com/)
        Found 15 interactive elements

        | # | Role | Name | Selector |
        |---|------|------|----------|
        | 1 | searchbox | "Search" | textarea[name="q"] |
        | 2 | button | "Google Search" | button[name="btnK"] |
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"error": "Browser not connected"})

    try:
        url = state.browser.get_url()
        title = state.browser.get_title()
        elements = _refresh_elements(state)

        lines = [
            f"## Page: {title} ({url})",
            f"Found {len(elements)} interactive elements",
            "",
            "| # | Role | Name | Selector |",
            "|---|------|------|----------|",
        ]

        for i, el in enumerate(elements[:50], 1):
            role = el.get("role", "")
            name = el.get("name", "")[:50]
            selector = el.get("selector", "")
            lines.append(f"| {i} | {role} | {name} | {selector} |")

        if len(elements) > 50:
            lines.append(f"\n... and {len(elements) - 50} more elements")

        return "\n".join(lines)
    except Exception as e:
        return json.dumps({
            "error": str(e)[:200],
            "suggestion": "Ensure a page is loaded and the browser is running.",
        })


# ── Tool: Click ────────────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_click",
    annotations={
        "title": "Click Element",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def vision_browser_click(params: ClickInput) -> str:
    """Click an interactive element by its index number.

    First call vision_browser_get_elements to see available elements.
    After clicking, the page may navigate — call vision_browser_get_elements
    again to see the new page's elements.

    Args:
        params.element: 1-based index from vision_browser_get_elements

    Returns:
        str: JSON with click result:
        {
            "success": bool,
            "clicked": str (element description),
            "url": str (current URL after click),
            "title": str,
            "new_elements_available": int
        }

    Examples:
        - Click element #3: element=3
        - Click search button after finding it: element=2
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})

    if params.element < 1 or params.element > len(state.element_cache):
        return json.dumps({
            "success": False,
            "error": f"Element {params.element} out of range (1-{len(state.element_cache)})",
            "suggestion": "Call vision_browser_get_elements first to see available elements.",
        })

    el = state.element_cache[params.element - 1]
    selector = el.get("selector", "")

    if not selector:
        return json.dumps({
            "success": False,
            "error": f"Element {params.element} has no CSS selector",
            "element": el,
            "suggestion": "Try a different element or refresh with get_elements.",
        })

    try:
        state.browser._page.click(selector, timeout=30000)
        _wait_for_load(state.browser)
        elements = _refresh_elements(state)

        return json.dumps({
            "success": True,
            "clicked": f"Element {params.element} ({el.get('role', '')}: {el.get('name', '')[:40]})",
            "url": state.browser.get_url(),
            "title": state.browser.get_title(),
            "new_elements_available": len(elements),
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)[:200],
            "element": el,
            "suggestion": f"Element {params.element} may not be clickable. Refresh with get_elements.",
        })


# ── Tool: Fill ─────────────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_fill",
    annotations={
        "title": "Fill Input Field",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def vision_browser_fill(params: FillInput) -> str:
    """Fill an input field with text by its index number.

    First call vision_browser_get_elements to find input elements
    (look for role=searchbox, role=textbox, or role=combobox).

    After filling, you may need to call vision_browser_press with key="Enter"
    to submit the form.

    Args:
        params.element: 1-based index from vision_browser_get_elements
        params.text: Text to enter (max 5000 chars)

    Returns:
        str: JSON with fill result:
        {
            "success": bool,
            "filled": str,
            "message": str
        }

    Examples:
        - Fill search box: element=1, text="Python tutorial"
        - Fill email field: element=3, text="user@example.com"
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})

    if params.element < 1 or params.element > len(state.element_cache):
        return json.dumps({
            "success": False,
            "error": f"Element {params.element} out of range (1-{len(state.element_cache)})",
            "suggestion": "Call vision_browser_get_elements first.",
        })

    el = state.element_cache[params.element - 1]
    selector = el.get("selector", "")

    if not selector:
        return json.dumps({
            "success": False,
            "error": f"Element {params.element} has no CSS selector",
            "suggestion": "Try a different element or refresh with get_elements.",
        })

    try:
        state.browser._page.fill(selector, params.text, timeout=30000)
        return json.dumps({
            "success": True,
            "filled": f"Element {params.element} ({el.get('role', '')}) with: {params.text[:50]}",
            "message": "Text entered. Use vision_browser_press(key='Enter') to submit if needed.",
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)[:200],
            "element": el,
            "suggestion": f"Element {params.element} may not be a text input.",
        })


# ── Tool: Press ────────────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_press",
    annotations={
        "title": "Press Keyboard Key",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def vision_browser_press(params: PressInput) -> str:
    """Press a keyboard key.

    Common keys: Enter (submit forms), Tab (navigate fields),
    Escape (close dialogs), Backspace, Delete, Arrow keys.
    Also: Control+a/c/v/x/z for select all, copy, paste, cut, undo.

    Args:
        params.key: Key to press

    Returns:
        str: JSON with result including current URL and title.

    Examples:
        - Submit form: key="Enter"
        - Move to next field: key="Tab"
        - Copy selected text: key="Control+c"
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})

    if params.key not in _ALLOWED_KEYS:
        allowed = sorted(_ALLOWED_KEYS)
        return json.dumps({
            "success": False,
            "error": f"Key '{params.key}' not allowed",
            "allowed_keys": allowed,
            "suggestion": "Use one of the allowed keys listed above.",
        })

    try:
        state.browser._page.keyboard.press(params.key)
        if params.key == "Enter":
            _wait_for_load(state.browser)
        elements = _refresh_elements(state)

        return json.dumps({
            "success": True,
            "key_pressed": params.key,
            "url": state.browser.get_url(),
            "title": state.browser.get_title(),
            "elements_available": len(elements),
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)[:200],
            "suggestion": "Check if the page is responsive.",
        })


# ── Tool: Scroll ───────────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_scroll",
    annotations={
        "title": "Scroll Page",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def vision_browser_scroll(params: ScrollInput) -> str:
    """Scroll the page up or down.

    Useful for loading more content on infinite-scroll pages
    or navigating long forms.

    Args:
        params.direction: "up" or "down" (default: "down")
        params.amount: Pixels to scroll (default: 500, range: 50-5000)

    Returns:
        str: JSON with scroll result and count of newly visible elements.

    Examples:
        - Scroll down 500px: direction="down", amount=500
        - Scroll up 300px: direction="up", amount=300
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})

    if params.direction not in ("up", "down"):
        return json.dumps({
            "success": False,
            "error": "Direction must be 'up' or 'down'",
            "suggestion": "Use direction='down' or direction='up'.",
        })

    try:
        state.browser.scroll(params.direction, params.amount)
        elements = _refresh_elements(state)

        return json.dumps({
            "success": True,
            "scrolled": f"{params.direction} by {params.amount}px",
            "elements_available": len(elements),
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)[:200],
            "suggestion": "Check if the page is responsive.",
        })


# ── Tool: Screenshot ───────────────────────────────────────────────────


@mcp.tool(
    name="vision_browser_screenshot",
    annotations={
        "title": "Take Screenshot",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def vision_browser_screenshot(params: ScreenshotInput) -> str:
    """Take a screenshot of the current page.

    For AI clients that support images, the screenshot will be displayed.
    For text-only clients, returns page state information.

    Args:
        params.full_page: Capture full scrollable page (default: false = viewport)

    Returns:
        str: JSON with screenshot info and page state.

    Examples:
        - Viewport screenshot: full_page=false
        - Full page screenshot: full_page=true
    """
    import tempfile

    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})

    try:
        shot_path = os.path.join(
            tempfile.gettempdir(), f"vision-browser-mcp-{int(time.time())}.png"
        )
        state.browser._page.screenshot(path=shot_path, full_page=params.full_page)

        url = state.browser.get_url()
        title = state.browser.get_title()

        return json.dumps({
            "success": True,
            "screenshot_path": shot_path,
            "url": url,
            "title": title,
            "full_page": params.full_page,
            "message": (
                "Screenshot saved. If your client supports images, "
                "it should be displayed above."
            ),
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)[:200],
            "suggestion": "Check if the browser is running.",
        })


# ── Tool: Execute (High-Level AI Task) ─────────────────────────────────


@mcp.tool(
    name="vision_browser_execute",
    annotations={
        "title": "Execute High-Level Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def vision_browser_execute(params: ExecuteInput) -> str:
    """Execute a high-level natural language task using AI reasoning.

    This is the most powerful tool — describe what you want to accomplish
    in natural language and the AI will plan and execute it automatically.

    The AI will:
    1. Analyze the current page state
    2. Plan a sequence of actions
    3. Execute them via Playwright
    4. Return results

    Requires NVIDIA API key (NVIDIA_API_KEY environment variable).

    Args:
        params.task: Natural language task description

    Returns:
        str: JSON with task execution results including actions taken,
        success count, and final page state.

    Examples:
        - "Search for 'Python tutorial' on Google"
        - "Go to GitHub and find trending Python repos"
        - "Fill the login form with user@example.com and password123"
    """
    state = _get_state(ctx=None)  # type: ignore

    if state.browser is None:
        return json.dumps({"success": False, "error": "Browser not connected"})
    if state.vision is None:
        return json.dumps({
            "success": False,
            "error": "Vision client not initialized",
            "suggestion": "Set NVIDIA_API_KEY environment variable.",
        })

    try:
        url = state.browser.get_url()
        title = state.browser.get_title()
        elements = state.browser.get_interactive_elements()

        # Build element text for prompt
        el_lines = []
        for i, el in enumerate(elements[:30], 1):
            role = el.get("role", "")
            name = el.get("name", "")
            if name:
                el_lines.append(f"  [{i}] role={role}, name={name}")
            else:
                el_lines.append(f"  [{i}] role={role}")
        el_text = "\n".join(el_lines) if el_lines else "  (none)"

        system_prompt = (
            "You are a browser automation agent. Analyze the page state "
            "and task, then return actions as JSON.\n\n"
            "ACTIONS: click, fill, press, scroll, navigate, wait\n"
            "Reference elements by index number, e.g., {\"action\": \"fill\", "
            "\"element\": 3, \"text\": \"query\"}\n"
            "Set done=true ONLY when task is complete.\n\n"
            "FORMAT: {\"actions\": [...], \"done\": false, \"reasoning\": \"...\"}"
        )

        user_prompt = (
            f"TASK: {params.task}\n\n"
            f"PAGE: {url} — {title}\n\n"
            f"ELEMENTS:\n{el_text}\n\n"
            f"Return ONLY JSON with actions."
        )

        result = state.vision.analyze_page(
            url=url,
            title=title,
            elements=elements,
            task=params.task,
            system_prompt=system_prompt,
            prompt_override=user_prompt,
        )

        actions = result.get("actions", [])
        if not isinstance(actions, list):
            actions = []

        # Execute actions
        success_count = 0
        action_results = []
        for action in actions:
            act = action.get("action", "")
            idx = action.get("element")

            try:
                if act == "click" and idx and 1 <= idx <= len(elements):
                    sel = elements[idx - 1].get("selector")
                    if sel:
                        state.browser._page.click(sel, timeout=30000)
                        _wait_for_load(state.browser)
                        success_count += 1
                        action_results.append(f"OK Clicked element {idx}")
                    else:
                        action_results.append(f"FAIL Element {idx} no selector")

                elif act == "fill" and idx and 1 <= idx <= len(elements):
                    sel = elements[idx - 1].get("selector")
                    text = action.get("text", "")
                    if sel:
                        state.browser._page.fill(sel, text, timeout=30000)
                        success_count += 1
                        action_results.append(f"OK Filled element {idx}")
                    else:
                        action_results.append(f"FAIL Element {idx} no selector")

                elif act == "press":
                    key = action.get("key", "Enter")
                    if key in _ALLOWED_KEYS:
                        state.browser._page.keyboard.press(key)
                        success_count += 1
                        action_results.append(f"OK Pressed {key}")
                        if key == "Enter":
                            _wait_for_load(state.browser)

                elif act == "scroll":
                    direction = action.get("direction", "down")
                    state.browser.scroll(direction)
                    success_count += 1
                    action_results.append(f"OK Scrolled {direction}")

                elif act == "navigate":
                    nav_url = action.get("url", "")
                    if nav_url.lower().startswith(("http://", "https://")):
                        state.browser.open(nav_url)
                        _wait_for_load(state.browser)
                        success_count += 1
                        action_results.append(f"OK Navigated to {nav_url}")

                else:
                    action_results.append(f"SKIP Unknown action: {act}")

            except Exception as e:
                action_results.append(f"FAIL {str(e)[:80]}")

        final_url = state.browser.get_url()
        final_title = state.browser.get_title()

        return json.dumps({
            "success": True,
            "task": params.task,
            "reasoning": result.get("reasoning", ""),
            "actions_planned": len(actions),
            "actions_succeeded": success_count,
            "action_details": action_results,
            "done": result.get("done", False),
            "final_url": final_url,
            "final_title": final_title,
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "task": params.task,
            "error": str(e)[:200],
            "suggestion": "Check NVIDIA_API_KEY and browser connection.",
        })


# ── Entry Point ────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server via stdio."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    mcp.run()


if __name__ == "__main__":
    main()
