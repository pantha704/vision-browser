# Architecture Research — v0.6 Integration Points

## Overview

How v0.6 features integrate with the existing architecture. Focus on integration points, new vs. modified components, data flow changes, and suggested build order.

## Existing Architecture (Unchanged Foundation)

```
CLI → Config → FastOrchestrator → Playwright CDP
                      ↓
              VisionClient → NIM API
                      ↓
              DesktopController → Badge Injection → DOM Actions
```

Plus the v0.5 additions:
- `MCPServer` — wraps FastOrchestrator, exposes 6 tools via MCP
- `WebSocketPreview` — streams browser state to HTML dashboard
- `MultiBrowserManager` — unified API across browser engines
- `SessionPool` — concurrent session management
- `diff_screenshot` — standalone differential screenshot module
- `session` — persistent session management

## v0.6 Integration Points

### 1. Model JSON Compliance (MODIFIES VisionClient)

**Current flow:**
```
VisionClient.query() → NIM API → raw response → json.loads() → dict
```

**New flow:**
```
VisionClient.query() → NIM API → raw response → validate_json() → Pydantic model
                                                    ↓ (fail)
                                           extract_json() → retry (2x) → error
```

**Changes:**
- `VisionClient._parse_response()` — add validation pipeline
- `VisionClient` — add retry loop with progressive prompt hardening
- `Exceptions` — add `ModelResponseError` for structured error reporting
- **No new files** — all changes in existing `vision_client.py`

**Data flow changes:**
- Response parsing now has 3 stages: validate → extract → retry
- Error responses now include schema context and raw response

### 2. Differential Screenshot Integration (MODIFIES FastOrchestrator)

**Current flow:**
```
FastOrchestrator.execute(action) → perform action → return result
```

**New flow:**
```
FastOrchestrator.execute(action) → screenshot before → perform action → screenshot after → diff → store diff → return result
```

**Changes:**
- `FastOrchestrator` — import `diff_screenshot`, add auto-capture logic
- `Config` — add `auto_diff_screenshots` flag, `diff_threshold` setting
- **No new files** — integration in existing `fast_orchestrator.py`

**Data flow changes:**
- Each action now produces an optional `diff_result` in the execution result
- Diff images are stored alongside session state

### 3. MCP Server Hardening (MODIFIES MCPServer)

**Changes:**
- `MCPServer` — add health check tool, error recovery wrappers
- `MCPServer` — add connection state tracking
- Add `mcp_tools/` directory for additional tools (optional)

**New components:**
- `MCPServer._health_check()` — internal health monitoring
- `MCPServer._handle_error()` — centralized error handling
- Optional: `wait_for_element`, `get_page_info` tools

**Data flow changes:**
- All tool handlers now wrapped in error recovery layer
- Health state exposed via new MCP tool

### 4. CLI Improvements (MODIFIES cli.py)

**Changes:**
- `cli.py` — replace `print()` with `rich.Console`
- Add `rich.Progress` for task execution feedback
- Add error message formatting
- Add task summary report

**No new files** — all changes in existing `cli.py`

**Data flow changes:**
- CLI output now structured (progress events → formatted display)
- Error handling produces formatted output instead of tracebacks

### 5. Test Coverage (NEW files)

**New test files:**
- `tests/test_vision_client.py` — mock NIM responses, test parsing
- `tests/test_desktop_controller.py` — test badge injection, selectors
- `tests/test_cli.py` — test CLI argument parsing, output formatting

**No production code changes** — only test additions

## Suggested Build Order

1. **Test mocks setup** — Create mock infrastructure for NIM API responses (enables all other work)
2. **Model JSON compliance** — Highest risk, affects all downstream components. Do first so other work has reliable foundation.
3. **Differential screenshot integration** — Low risk, well-scoped, can be done in parallel with MCP work
4. **MCP server hardening** — Medium risk, depends on model compliance being stable
5. **CLI improvements** — Low risk, cosmetic changes, can be done anytime
6. **Test coverage completion** — Ongoing, should be done alongside each phase

## Architecture Decisions to Document

1. **JSON validation pipeline** — validate → extract → retry pattern, with max 2 retries
2. **Diff screenshot opt-in** — auto-capture disabled by default, enabled via config flag
3. **MCP error handling** — all tools return structured errors, never raise exceptions to clients
4. **Rich as optional dependency** — CLI falls back to basic output if Rich not installed
5. **Test isolation** — unit tests mock all external dependencies (NIM API, Playwright)
