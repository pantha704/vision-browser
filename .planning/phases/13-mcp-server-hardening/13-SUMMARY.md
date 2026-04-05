# Phase 13 Summary: MCP Server Hardening

## Status: COMPLETE

## Changes Made

### MCP-01: Health Check Tool
- Added `HEALTH_TOOL` with `health` name
- Returns status (ok/degraded/error), state, tools list, uptime, error count
- Health tool excludes itself from tools list

### MCP-02: Error Recovery
- All tool handlers wrapped in try/except in `call_tool()`
- Exceptions caught and converted to structured error responses
- No unhandled exceptions propagate to MCP clients

### MCP-03: Connection State Tracking
- Added `ConnectionState` enum: CONNECTED, DISCONNECTED, RECOVERING, DEGRADED
- State initialized based on orchestrator presence
- `_update_state()` transitions based on consecutive error count:
  - 0 errors: CONNECTED
  - 1-2 errors: RECOVERING
  - 3-4 errors: DEGRADED
  - 5+: stays DEGRADED
- Success resets to CONNECTED

### MCP-04: Structured Error Responses
- `_structured_error()` returns consistent format:
  - `success: false`, `error`, `error_type`, `retry_after`, `suggestion`
- RateLimitError: retry_after=5
- TimeoutError: retry_after=2
- VisionAPIError: retry_after=3
- BrowserError: suggestion to check browser

### Refactoring
- Replaced per-handler `if not orchestrator` checks with `_require_orchestrator()` helper
- Handlers now raise exceptions instead of returning error dicts
- Error recovery wrapper converts to structured responses

## Tests
- 17 new tests in `test_mcp_server_hardening.py` (all pass)
- 2 existing tests updated for new tool count (all pass)
- Total: 215 tests passing

## Files Modified
- `/home/panther/Desktop/projects/vision-browser/src/vision_browser/mcp_server.py`
- `/home/panther/Desktop/projects/vision-browser/tests/test_milestone2.py`
- `/home/panther/Desktop/projects/vision-browser/tests/test_mcp_server_hardening.py` (new)
