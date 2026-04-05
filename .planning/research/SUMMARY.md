# Research Summary — v0.6 Developer Experience & Reliability

## Overview

Synthesis of research findings for v0.6: model JSON compliance, differential screenshot integration, MCP server hardening, CLI improvements, and test coverage completion.

## Stack Additions

| Addition | Type | Justification |
|----------|------|---------------|
| `rich` (v13.x) | New dependency | Industry-standard CLI formatting, progress bars, spinners |
| Pydantic `model_validate_json()` | Existing dependency | Already installed, now used rigorously for JSON validation |
| `pytest-asyncio` | Test dependency | Required for async WebSocket tests |
| `pytest-httpx` or `responses` | Test dependency | HTTP mocking for NIM API unit tests |

**No other new dependencies needed.** The existing stack (Playwright, Pydantic, NIM API, MCP SDK) is sufficient.

## Feature Table Stakes

### Model JSON Compliance (Highest Priority)
- Validate every model response as JSON before use
- Extract JSON from mixed responses (markdown code blocks, prose-wrapped)
- Retry with progressively stricter prompts (max 2 retries)
- Return structured errors on persistent failure

### Differential Screenshot Integration
- Auto-capture before/after each action (opt-in via config)
- Configurable diff thresholds to skip identical frames
- Store diffs with task context for debugging

### MCP Server Hardening
- Health check tool for client verification
- Error recovery wrappers on all tools
- Connection state tracking

### CLI Improvements
- Real-time progress indicators (spinners, progress bars)
- Human-readable error messages with suggested fixes
- Task summary report on completion

### Test Coverage
- VisionClient tests with mocked NIM responses
- DesktopController tests for badge injection and selectors
- Integration tests for common user flows

## Architecture Summary

**Mostly modifications, few new files:**
- `vision_client.py` — JSON validation pipeline (validate → extract → retry)
- `fast_orchestrator.py` — diff screenshot auto-capture
- `mcp_server.py` — health check, error recovery
- `cli.py` — Rich integration, progress indicators
- `tests/test_vision_client.py` — new test file
- `tests/test_desktop_controller.py` — new test file
- `tests/test_cli.py` — new test file

**No new production modules needed.** All changes integrate into existing files.

## Build Order

1. Test mocks setup (enables all other work)
2. Model JSON compliance (highest risk, affects all downstream)
3. Differential screenshot integration (low risk, well-scoped)
4. MCP server hardening (medium risk, depends on model stability)
5. CLI improvements (low risk, cosmetic)
6. Test coverage completion (ongoing, alongside each phase)

## Watch Out For

1. **Over-engineering JSON parsing** — Keep it simple: validate, extract (one regex), retry (2x), error. If parsing is complex, the prompt is wrong.
2. **Performance regression from auto-screenshots** — Make opt-in default, set cleanup limits, benchmark each action.
3. **MCP backward compatibility** — Keep response shapes identical, test with existing clients.
4. **Rich as optional dependency** — Graceful fallback to basic output.
5. **Scope creep** — "Developer experience" is broad. Stay focused on the 5 defined categories.
6. **Compounding latency** — All features should be non-blocking. Benchmark each change.

## Key Decisions Recommended

1. **JSON validation pipeline:** validate → extract (one regex) → retry (2x max with progressive prompts) → structured error
2. **Diff screenshots:** opt-in via config, disabled by default, auto-cleanup after N diffs
3. **MCP errors:** all tools return structured errors, never raise to clients
4. **Rich:** optional dependency with graceful fallback
5. **Tests:** mock at HTTP level, use realistic (including malformed) responses
