"""MCP Server Mode -- expose vision-browser as an MCP server."""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """MCP server connection state."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECOVERING = "recovering"
    DEGRADED = "degraded"


class MCPTool:
    """An MCP tool definition."""

    def __init__(self, name: str, description: str, input_schema: dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


NAVIGATE_TOOL = MCPTool(
    name="navigate",
    description="Navigate to a URL in the browser",
    input_schema={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "URL to navigate to"}},
        "required": ["url"],
    },
)

SCREENSHOT_TOOL = MCPTool(
    name="screenshot",
    description="Take a screenshot of the current page",
    input_schema={
        "type": "object",
        "properties": {
            "full_page": {"type": "boolean", "description": "Capture full page including below-fold content", "default": False}
        },
    },
)

CLICK_TOOL = MCPTool(
    name="click",
    description="Click an element by badge number",
    input_schema={
        "type": "object",
        "properties": {"element": {"type": "integer", "description": "Badge number of element to click"}},
        "required": ["element"],
    },
)

FILL_TOOL = MCPTool(
    name="fill",
    description="Fill an input field with text",
    input_schema={
        "type": "object",
        "properties": {
            "element": {"type": "integer", "description": "Badge number of input element"},
            "text": {"type": "string", "description": "Text to fill"},
        },
        "required": ["element", "text"],
    },
)

EXTRACT_TOOL = MCPTool(
    name="extract",
    description="Extract text content matching a CSS selector",
    input_schema={
        "type": "object",
        "properties": {"selector": {"type": "string", "description": "CSS selector"}},
        "required": ["selector"],
    },
)

EXECUTE_TOOL = MCPTool(
    name="execute",
    description="Execute a browser automation task described in natural language",
    input_schema={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Natural language description of what to do"}
        },
        "required": ["task"],
    },
)

HEALTH_TOOL = MCPTool(
    name="health",
    description="Check server health and connection status",
    input_schema={
        "type": "object",
        "properties": {},
    },
)

ALL_TOOLS = [NAVIGATE_TOOL, SCREENSHOT_TOOL, CLICK_TOOL, FILL_TOOL, EXTRACT_TOOL, EXECUTE_TOOL, HEALTH_TOOL]


class MCPServer:
    """MCP server for vision-browser capabilities.

    Exposes browser automation as MCP tools compatible with Claude,
    Cursor, and other MCP clients.
    """

    def __init__(self, orchestrator=None):
        self._orchestrator = orchestrator
        self._tools = list(ALL_TOOLS)
        self._state = ConnectionState.DISCONNECTED if orchestrator is None else ConnectionState.CONNECTED
        self._consecutive_errors = 0
        self._start_time = time.monotonic()

    def _structured_error(self, error: Exception, context: str = "") -> dict:
        """Create a structured error response with retry hints."""
        from vision_browser.exceptions import (
            VisionAPIError,
            BrowserError,
            BrowserNotInstalledError,
            RateLimitError,
            TimeoutError,
        )

        error_type = type(error).__name__
        suggestion = "Please try again."

        if isinstance(error, (BrowserNotInstalledError, BrowserError)):
            suggestion = "Check if the browser is running and accessible."
            retry_after = None
        elif isinstance(error, RateLimitError):
            suggestion = "Rate limited. Wait before retrying."
            retry_after = 5
        elif isinstance(error, TimeoutError):
            suggestion = "Request timed out. Check network connectivity."
            retry_after = 2
        elif isinstance(error, VisionAPIError):
            suggestion = "Model API error. Wait a moment and retry."
            retry_after = 3
        else:
            retry_after = None
            if context:
                suggestion = f"An unexpected error occurred: {context}"

        return {
            "success": False,
            "error": str(error),
            "error_type": error_type,
            "retry_after": retry_after,
            "suggestion": suggestion,
        }

    def list_tools(self) -> list[dict]:
        """Return all available MCP tools."""
        return [t.to_dict() for t in self._tools]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Execute an MCP tool by name with error recovery."""
        handlers = {
            "navigate": self._handle_navigate,
            "screenshot": self._handle_screenshot,
            "click": self._handle_click,
            "fill": self._handle_fill,
            "extract": self._handle_extract,
            "execute": self._handle_execute,
            "health": self._handle_health,
        }
        handler = handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}
        try:
            result = await handler(arguments)
            self._consecutive_errors = 0  # Reset on success
            self._update_state()
            return result
        except Exception as e:
            self._consecutive_errors += 1
            self._update_state()
            logger.error(f"Tool {name} failed: {e}")
            return self._structured_error(e, context=f"Tool '{name}' failed")

    def _update_state(self) -> None:
        """Update connection state based on error count."""
        if self._consecutive_errors == 0:
            self._state = ConnectionState.CONNECTED
        elif self._consecutive_errors < 3:
            self._state = ConnectionState.RECOVERING
        elif self._consecutive_errors < 5:
            self._state = ConnectionState.DEGRADED
        # Beyond 5, stay DEGRADED

    async def _handle_health(self, args: dict) -> dict:
        """Return server health and status."""
        uptime = time.monotonic() - self._start_time
        tool_names = [t.name for t in self._tools if t.name != "health"]

        if self._state == ConnectionState.CONNECTED:
            status = "ok"
        elif self._state == ConnectionState.RECOVERING:
            status = "degraded"
        else:
            status = "error"

        return {
            "status": status,
            "state": self._state.value,
            "tools_available": tool_names,
            "uptime_seconds": round(uptime, 2),
            "consecutive_errors": self._consecutive_errors,
            "orchestrator_connected": self._orchestrator is not None,
        }

    async def _handle_navigate(self, args: dict) -> dict:
        self._require_orchestrator()
        self._orchestrator.browser.open(args["url"])
        return {"success": True, "url": args["url"]}

    async def _handle_screenshot(self, args: dict) -> dict:
        self._require_orchestrator()
        path = "/tmp/vision-browser-mcp-screenshot.png"
        result = self._orchestrator.browser.screenshot(path, full_page=args.get("full_page", False))
        return {"success": True, "path": path, "url": result.get("url"), "title": result.get("title")}

    async def _handle_click(self, args: dict) -> dict:
        self._require_orchestrator()
        self._orchestrator.browser.click(args["element"])
        return {"success": True, "clicked": args["element"]}

    async def _handle_fill(self, args: dict) -> dict:
        self._require_orchestrator()
        self._orchestrator.browser.fill(args["element"], args["text"])
        return {"success": True, "filled": args["element"]}

    async def _handle_extract(self, args: dict) -> dict:
        self._require_orchestrator()
        text = self._orchestrator.browser._page.query_selector(args["selector"]).inner_text()
        return {"success": True, "text": text}

    async def _handle_execute(self, args: dict) -> dict:
        self._require_orchestrator()
        # Delegate to the orchestrator's vision-driven automation
        self._orchestrator.run(args["task"])
        return {"success": True, "task": args["task"]}

    def _require_orchestrator(self) -> None:
        """Raise an error if no orchestrator is connected."""
        if self._orchestrator is None:
            raise RuntimeError("No orchestrator connected. Start the server with a browser session.")


def get_mcp_resource() -> dict:
    """Return the MCP resource describing current page state."""
    return {
        "uri": "vision-browser://current-page",
        "mimeType": "application/json",
        "description": "Current browser page state (URL, title, elements)",
    }
