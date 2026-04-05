"""Tests for Milestone 2 modules: MCP, WebSocket, MultiBrowser, SessionPool."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from vision_browser.mcp_server import (
    ALL_TOOLS,
    CLICK_TOOL,
    FILL_TOOL,
    NAVIGATE_TOOL,
    SCREENSHOT_TOOL,
    MCPServer,
    get_mcp_resource,
)
from vision_browser.websocket_preview import WebSocketPreview
from vision_browser.multi_browser import (
    MultiBrowserManager,
)
from vision_browser.session_pool import BrowserSession, SessionPool


def _run_async(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


# ── MCP Server Tests ───────────────────────────────────────────────

class TestMCPTools:
    def test_navigate_tool_schema(self):
        """Navigate tool has correct schema."""
        d = NAVIGATE_TOOL.to_dict()
        assert d["name"] == "navigate"
        assert "url" in d["inputSchema"]["required"]

    def test_screenshot_tool_schema(self):
        """Screenshot tool has correct schema."""
        d = SCREENSHOT_TOOL.to_dict()
        assert d["name"] == "screenshot"
        assert d["inputSchema"]["properties"]["full_page"]["default"] is False

    def test_click_tool_schema(self):
        """Click tool has correct schema."""
        d = CLICK_TOOL.to_dict()
        assert d["name"] == "click"
        assert "element" in d["inputSchema"]["required"]

    def test_fill_tool_schema(self):
        """Fill tool has correct schema."""
        d = FILL_TOOL.to_dict()
        assert d["name"] == "fill"
        assert "element" in d["inputSchema"]["required"]
        assert "text" in d["inputSchema"]["required"]

    def test_all_tools_count(self):
        """All expected tools are defined."""
        assert len(ALL_TOOLS) == 7  # 6 original + health


class TestMCPServer:
    def test_list_tools(self):
        """Server lists all tools."""
        server = MCPServer()
        tools = server.list_tools()
        assert len(tools) == 7  # 6 original + health
        names = [t["name"] for t in tools]
        assert "navigate" in names
        assert "screenshot" in names
        assert "health" in names

    def test_call_unknown_tool(self):
        """Unknown tool returns error."""
        server = MCPServer()
        result = _run_async(server.call_tool("nonexistent", {}))
        assert "error" in result

    def test_call_tool_no_orchestrator(self):
        """Tool call without orchestrator returns error."""
        server = MCPServer()
        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert "error" in result

    def test_call_navigate(self):
        """Navigate tool calls browser.open."""
        server = MCPServer()
        mock_orchestrator = MagicMock()
        mock_orchestrator.browser.open.return_value = None
        server._orchestrator = mock_orchestrator

        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert result["success"] is True
        mock_orchestrator.browser.open.assert_called_once_with("https://example.com")

    def test_call_click(self):
        """Click tool calls browser.click."""
        server = MCPServer()
        mock_orchestrator = MagicMock()
        mock_orchestrator.browser.click.return_value = None
        server._orchestrator = mock_orchestrator

        result = _run_async(server.call_tool("click", {"element": 5}))
        assert result["success"] is True
        mock_orchestrator.browser.click.assert_called_once_with(5)

    def test_call_fill(self):
        """Fill tool calls browser.fill."""
        server = MCPServer()
        mock_orchestrator = MagicMock()
        mock_orchestrator.browser.fill.return_value = None
        server._orchestrator = mock_orchestrator

        result = _run_async(server.call_tool("fill", {"element": 3, "text": "hello"}))
        assert result["success"] is True
        mock_orchestrator.browser.fill.assert_called_once_with(3, "hello")

    def test_get_mcp_resource(self):
        """MCP resource describes current page."""
        resource = get_mcp_resource()
        assert resource["uri"] == "vision-browser://current-page"
        assert "browser page state" in resource["description"].lower()


# ── WebSocket Preview Tests ────────────────────────────────────────

class TestWebSocketPreview:
    def test_init_defaults(self):
        """Default port and interval."""
        preview = WebSocketPreview()
        assert preview.port == 8765
        assert preview.interval_ms == 1000

    def test_init_custom(self):
        """Custom port and interval."""
        preview = WebSocketPreview(port=9000, interval_ms=500)
        assert preview.port == 9000
        assert preview.interval_ms == 500

    def test_broadcast(self):
        """Broadcast sends to all clients."""
        preview = WebSocketPreview()
        messages = []
        preview.connect(lambda msg: messages.append(msg))
        preview.connect(lambda msg: messages.append(msg))

        count = preview.broadcast("test", {"key": "value"})
        assert count == 2
        assert len(messages) == 2
        assert '"event": "test"' in messages[0]

    def test_connect_disconnect(self):
        """Connect and disconnect clients."""
        preview = WebSocketPreview()
        def _noop(msg):  # noqa: ARG001
            pass
        preview.connect(_noop)
        assert preview.client_count == 1
        preview.disconnect(_noop)
        assert preview.client_count == 0

    def test_send_screenshot_missing_file(self):
        """Screenshot send handles missing file."""
        preview = WebSocketPreview()
        result = preview.send_screenshot("/nonexistent/file.png")
        assert result == 0

    def test_send_navigation(self):
        """Navigation event broadcast."""
        preview = WebSocketPreview()
        messages = []
        preview.connect(lambda msg: messages.append(msg))
        preview.send_navigation("https://example.com", "Example")
        assert len(messages) == 1
        assert '"navigate"' in messages[0]

    def test_send_error(self):
        """Error event broadcast."""
        preview = WebSocketPreview()
        messages = []
        preview.connect(lambda msg: messages.append(msg))
        preview.send_error("Something went wrong")
        assert len(messages) == 1
        assert '"error"' in messages[0]

    def test_generate_dashboard(self):
        """Dashboard HTML is generated."""
        preview = WebSocketPreview(port=8765)
        html = preview.generate_dashboard_html()
        assert "Vision Browser Live Preview" in html
        assert "ws://localhost:8765" in html


# ── Multi-Browser Tests ────────────────────────────────────────────

class TestMultiBrowserManager:
    def test_invalid_engine(self):
        """Invalid engine raises error."""
        with pytest.raises(ValueError, match="Invalid engine"):
            MultiBrowserManager(engine="opera")

    def test_valid_engines(self):
        """Valid engines accepted."""
        for engine in ["chromium", "firefox", "webkit"]:
            mgr = MultiBrowserManager(engine=engine)
            assert mgr.engine == engine

    def test_cdp_firefox_not_allowed(self):
        """CDP connection only allowed for Chromium."""
        mgr = MultiBrowserManager(engine="firefox")
        with pytest.raises(ValueError, match="CDP connection only supported"):
            mgr.connect_cdp("http://localhost:9222")

    def test_available_engines_returns_dict(self):
        """Available engines returns dict."""
        result = MultiBrowserManager.available_engines()
        assert isinstance(result, dict)
        # At minimum, returns entries for all known engines
        assert "chromium" in result
        assert "firefox" in result
        assert "webkit" in result


# ── Session Pool Tests ─────────────────────────────────────────────

class TestSessionPool:
    def test_init_default(self):
        """Default max sessions."""
        pool = SessionPool()
        assert pool.max_sessions == 5

    def test_init_custom(self):
        """Custom max sessions."""
        pool = SessionPool(max_sessions=10)
        assert pool.max_sessions == 10

    def test_empty_pool(self):
        """Empty pool has no active sessions."""
        pool = SessionPool()
        assert pool.session_count == 0
        assert pool.active_sessions == []
        assert pool.get_session_status() == []

    def test_get_nonexistent_session(self):
        """Get returns None for nonexistent session."""
        pool = SessionPool()
        assert pool.get_session("nonexistent") is None

    def test_close_nonexistent_session(self):
        """Close returns False for nonexistent session."""
        pool = SessionPool()
        assert pool.close_session("nonexistent") is False

    def test_close_all_empty_pool(self):
        """Close all on empty pool does not raise."""
        pool = SessionPool()
        pool.close_all()  # Should not raise

    def test_max_sessions_error(self):
        """Creating sessions beyond limit raises error."""
        pool = SessionPool(max_sessions=1)
        # Can't create real sessions without Playwright
        # But we can verify the check works
        pool._sessions["fake-1"] = BrowserSession(name="s1", is_active=True)

        with pytest.raises(RuntimeError, match="Max sessions"):
            pool.create_session(name="s2")
