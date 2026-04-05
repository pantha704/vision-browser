"""Tests for MCP Server Hardening — health, error recovery, state tracking."""

from __future__ import annotations

import asyncio

import pytest

from vision_browser.mcp_server import (
    ALL_TOOLS,
    ConnectionState,
    MCPServer,
)


def _run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class TestHealthTool:
    """Test MCP-01: Health check tool."""

    def test_health_tool_in_all_tools(self):
        """Health tool should be listed in ALL_TOOLS."""
        names = [t.name for t in ALL_TOOLS]
        assert "health" in names

    def test_health_returns_ok_when_connected(self):
        """Health check returns 'ok' when orchestrator is connected."""
        from unittest.mock import MagicMock
        server = MCPServer(orchestrator=MagicMock())
        result = _run_async(server.call_tool("health", {}))
        assert result["status"] == "ok"
        assert result["state"] == "connected"
        assert result["orchestrator_connected"] is True
        assert "tools_available" in result
        assert "uptime_seconds" in result

    def test_health_returns_error_when_disconnected(self):
        """Health check returns 'error' when no orchestrator."""
        server = MCPServer()
        result = _run_async(server.call_tool("health", {}))
        assert result["status"] == "error"
        assert result["state"] == "disconnected"
        assert result["orchestrator_connected"] is False

    def test_health_lists_all_other_tools(self):
        """Health tool lists all other tools (excluding itself)."""
        from unittest.mock import MagicMock
        server = MCPServer(orchestrator=MagicMock())
        result = _run_async(server.call_tool("health", {}))
        tools = result["tools_available"]
        assert "navigate" in tools
        assert "screenshot" in tools
        assert "click" in tools
        assert "fill" in tools
        assert "extract" in tools
        assert "execute" in tools
        assert "health" not in tools  # health doesn't list itself


class TestErrorRecovery:
    """Test MCP-02: All tools wrapped in error recovery."""

    def test_tool_error_returns_structured_error(self):
        """When a tool raises an exception, call_tool returns structured error."""
        server = MCPServer()
        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert result["success"] is False
        assert "error" in result
        assert "error_type" in result
        assert "suggestion" in result

    def test_structured_error_has_retry_after_for_rate_limit(self):
        """RateLimitError should include retry_after."""
        from unittest.mock import MagicMock
        from vision_browser.exceptions import RateLimitError

        server = MCPServer(orchestrator=MagicMock())
        server._orchestrator.browser.open.side_effect = RateLimitError("rate limited")

        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert result["success"] is False
        assert result["retry_after"] is not None
        assert result["retry_after"] > 0

    def test_structured_error_has_retry_after_for_vision_api(self):
        """VisionAPIError should include retry_after."""
        from unittest.mock import MagicMock
        from vision_browser.exceptions import VisionAPIError

        server = MCPServer(orchestrator=MagicMock())
        server._orchestrator.browser.open.side_effect = VisionAPIError("model error")

        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert result["success"] is False
        assert result["retry_after"] == 3

    def test_browser_error_suggestion(self):
        """BrowserError should suggest checking browser."""
        from unittest.mock import MagicMock
        from vision_browser.exceptions import BrowserError

        server = MCPServer(orchestrator=MagicMock())
        server._orchestrator.browser.open.side_effect = BrowserError("browser crashed")

        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert result["success"] is False
        assert "browser" in result["suggestion"].lower()


class TestConnectionState:
    """Test MCP-03: Connection state tracking."""

    def test_initial_state_connected(self):
        """Server with orchestrator starts in CONNECTED state."""
        from unittest.mock import MagicMock
        server = MCPServer(orchestrator=MagicMock())
        assert server._state == ConnectionState.CONNECTED

    def test_initial_state_disconnected(self):
        """Server without orchestrator starts in DISCONNECTED state."""
        server = MCPServer()
        assert server._state == ConnectionState.DISCONNECTED

    def test_state_transitions_to_recovering_on_error(self):
        """First error transitions to RECOVERING."""
        server = MCPServer()
        _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert server._state == ConnectionState.RECOVERING

    def test_state_transitions_to_degraded_on_repeated_errors(self):
        """3+ consecutive errors transitions to DEGRADED."""
        server = MCPServer()
        for _ in range(3):
            _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert server._state == ConnectionState.DEGRADED

    def test_state_resets_on_success(self):
        """Success after errors resets to CONNECTED."""
        from unittest.mock import MagicMock
        server = MCPServer()
        # Cause 2 errors
        _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert server._state == ConnectionState.RECOVERING

        # Attach orchestrator and succeed
        server._orchestrator = MagicMock()
        server._orchestrator.browser.open.return_value = None
        _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert server._state == ConnectionState.CONNECTED


class TestBackwardCompatibility:
    """Test that existing tool behavior is unchanged for success cases."""

    def test_navigate_success_shape(self):
        """Navigate tool returns same shape as before."""
        from unittest.mock import MagicMock
        server = MCPServer(orchestrator=MagicMock())
        server._orchestrator.browser.open.return_value = None
        result = _run_async(server.call_tool("navigate", {"url": "https://example.com"}))
        assert result["success"] is True
        assert "url" in result

    def test_click_success_shape(self):
        """Click tool returns same shape as before."""
        from unittest.mock import MagicMock
        server = MCPServer(orchestrator=MagicMock())
        server._orchestrator.browser.click.return_value = None
        result = _run_async(server.call_tool("click", {"element": 5}))
        assert result["success"] is True
        assert "clicked" in result

    def test_fill_success_shape(self):
        """Fill tool returns same shape as before."""
        from unittest.mock import MagicMock
        server = MCPServer(orchestrator=MagicMock())
        server._orchestrator.browser.fill.return_value = None
        result = _run_async(server.call_tool("fill", {"element": 3, "text": "hello"}))
        assert result["success"] is True
        assert "filled" in result

    def test_list_tools_count(self):
        """Server now has 7 tools (6 + health)."""
        server = MCPServer()
        tools = server.list_tools()
        assert len(tools) == 7
