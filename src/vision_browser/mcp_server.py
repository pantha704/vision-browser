"""MCP Server Mode -- expose vision-browser as an MCP server."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


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

ALL_TOOLS = [NAVIGATE_TOOL, SCREENSHOT_TOOL, CLICK_TOOL, FILL_TOOL, EXTRACT_TOOL, EXECUTE_TOOL]


class MCPServer:
    """MCP server for vision-browser capabilities.

    Exposes browser automation as MCP tools compatible with Claude,
    Cursor, and other MCP clients.
    """

    def __init__(self, orchestrator=None):
        self._orchestrator = orchestrator
        self._tools = list(ALL_TOOLS)

    def list_tools(self) -> list[dict]:
        """Return all available MCP tools."""
        return [t.to_dict() for t in self._tools]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Execute an MCP tool by name."""
        handlers = {
            "navigate": self._handle_navigate,
            "screenshot": self._handle_screenshot,
            "click": self._handle_click,
            "fill": self._handle_fill,
            "extract": self._handle_extract,
            "execute": self._handle_execute,
        }
        handler = handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}
        try:
            return await handler(arguments)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"error": str(e)}

    async def _handle_navigate(self, args: dict) -> dict:
        if not self._orchestrator:
            return {"error": "No orchestrator connected"}
        self._orchestrator.browser.open(args["url"])
        return {"success": True, "url": args["url"]}

    async def _handle_screenshot(self, args: dict) -> dict:
        if not self._orchestrator:
            return {"error": "No orchestrator connected"}
        path = "/tmp/vision-browser-mcp-screenshot.png"
        result = self._orchestrator.browser.screenshot(path, full_page=args.get("full_page", False))
        return {"success": True, "path": path, "url": result.get("url"), "title": result.get("title")}

    async def _handle_click(self, args: dict) -> dict:
        if not self._orchestrator:
            return {"error": "No orchestrator connected"}
        self._orchestrator.browser.click(args["element"])
        return {"success": True, "clicked": args["element"]}

    async def _handle_fill(self, args: dict) -> dict:
        if not self._orchestrator:
            return {"error": "No orchestrator connected"}
        self._orchestrator.browser.fill(args["element"], args["text"])
        return {"success": True, "filled": args["element"]}

    async def _handle_extract(self, args: dict) -> dict:
        if not self._orchestrator:
            return {"error": "No orchestrator connected"}
        try:
            text = self._orchestrator.browser._page.query_selector(args["selector"]).inner_text()
            return {"success": True, "text": text}
        except Exception as e:
            return {"error": str(e)}

    async def _handle_execute(self, args: dict) -> dict:
        if not self._orchestrator:
            return {"error": "No orchestrator connected"}
        # Delegate to the orchestrator's vision-driven automation
        self._orchestrator.run(args["task"])
        return {"success": True, "task": args["task"]}


def get_mcp_resource() -> dict:
    """Return the MCP resource describing current page state."""
    return {
        "uri": "vision-browser://current-page",
        "mimeType": "application/json",
        "description": "Current browser page state (URL, title, elements)",
    }
