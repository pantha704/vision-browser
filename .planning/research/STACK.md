# Stack Research — Model Compliance, CLI UX, MCP Hardening, Test Coverage

## Overview

Research on stack additions/changes needed for v0.6: model JSON compliance, differential screenshot integration, MCP server hardening, CLI improvements, and test coverage completion.

## Existing Stack (No Changes Needed)

- **Playwright CDP** — Stable, well-tested, no changes needed
- **NVIDIA NIM Llama 3.2 90B Vision** — Primary vision model, keep as-is
- **Groq** — Fallback vision model, keep as-is
- **Pydantic** — Config models, already well-integrated
- **MCP SDK** — Already installed and working

## New Stack Additions

### 1. Structured Output Enforcement

**Problem:** NIM returns prose ~50% of the time instead of valid JSON.

**Options evaluated:**

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| JSON schema enforcement (Pydantic `model_validate_json`) | Already have Pydantic, catches invalid JSON | Still fails on prose responses | ✓ Primary — wrap model responses in try/except with Pydantic validation |
| Response parsing with regex extraction | Handles markdown code blocks, prose-wrapped JSON | Fragile, model-dependent | ✓ Secondary — extract JSON blocks from mixed responses |
| Retry with explicit JSON prompt | Improves compliance rate | Adds latency, cost | ✓ Tertiary — retry up to 2x with progressively stricter prompts |
| Function calling / tool use | Guaranteed structured output | Requires model support, NIM may not support it | ✗ Not supported by NIM Llama 3.2 90B Vision |

**Recommended stack:**
- **Pydantic `model_validate_json()`** with `strict=True` — validate all model responses
- **JSON extraction regex** — `r'```(?:json)?\s*([\s\S]*?)```|(\{[\s\S]*\})'` to extract JSON from mixed responses
- **Progressive prompt hardening** — on first failure, add "You MUST respond with ONLY valid JSON, no explanation" prefix; on second failure, add explicit JSON schema example

### 2. CLI Progress Indicators

**Problem:** CLI lacks real-time feedback during task execution.

**Options evaluated:**

| Library | Pros | Cons | Recommendation |
|---------|------|------|----------------|
| `rich` | Beautiful output, progress bars, spinners, tables | Adds dependency (~2MB) | ✓ Best choice — rich is industry standard |
| `tqdm` | Lightweight, simple progress bars | Less flexible for complex CLI output | ✗ Limited use case |
| `alive-progress` | Animated spinners, good for CLI | Less mature, fewer features | ✗ rich is superior |

**Recommended:** `rich` (v13.x) — provides `Progress`, `Spinner`, `Console`, and `Table` for comprehensive CLI improvements.

### 3. MCP Connection Lifecycle

**Problem:** MCP server lacks error recovery and connection management.

**Approach:**
- Implement SSE transport health checks with configurable interval (default 30s)
- Add reconnection logic with exponential backoff (1s, 2s, 4s, 8s max)
- Implement graceful degradation when vision model is unavailable (return error with retry-after header)
- Add connection state tracking (connected, disconnected, reconnecting) for health endpoint

### 4. Test Coverage Tools

**Existing:** pytest already in use.

**Additions:**
- `pytest-cov` — for coverage reporting (already likely present, verify)
- `pytest-asyncio` — for async test support (needed for WebSocket tests)
- `responses` or `pytest-httpx` — for mocking HTTP calls to NIM API in unit tests

## What NOT to Add

- **Alternative vision models** — NIM + Groq fallback is sufficient for v0.6
- **Database/persistence layer** — session state is file-based, adequate for scope
- **GUI framework** — CLI + MCP + WebSocket dashboard is the right abstraction
- **Distributed computing** — single-browser scope is intentional

## Integration Points

1. **Pydantic validation** wraps `VisionClient._parse_response()` — minimal change, high impact
2. **Rich integration** in `cli.py` — replaces `print()` calls, adds progress bars for task steps
3. **MCP health checks** in `mcp_server.py` — new `/health` tool endpoint
4. **Screenshot integration** in `FastOrchestrator.execute()` — capture before/after each action
5. **Test mocks** — mock NIM responses for deterministic unit tests

## Rationale Summary

The stack additions are minimal and focused:
- **Pydantic** is already a dependency — we're using it more rigorously
- **Rich** is the only new dependency — well-maintained, 15M+ weekly downloads
- **MCP improvements** are architectural, not stack changes
- **Test additions** are pytest plugins — familiar ecosystem
