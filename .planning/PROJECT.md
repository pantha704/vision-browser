# Vision Browser

## What This Is

**Fast vision-driven browser automation** using **Playwright + NVIDIA NIM Llama 3.2 90B Vision**.

Navigate, search, fill forms, and extract data from any website using natural language commands. 10x faster than CLI-based approaches with DOM-validated element refs for 80-95% accuracy. Now with MCP server mode, WebSocket live preview, multi-browser support, and concurrent session management.

**Core value:** Automate any web task by describing it in plain English — no selectors, no scripts, no coding.

---

## Context

- **Status:** v0.6 shipped — Developer Experience & Reliability
- **Repository:** https://github.com/pantha704/vision-browser
- **Type:** Python library + CLI tool
- **License:** MIT
- **Author:** pantha704

### Technical Stack

- **Runtime:** Python 3.14
- **Browser:** Playwright (CDP for Chromium, standard for Firefox/WebKit)
- **Vision AI:** NVIDIA NIM Llama 3.2 90B Vision (primary), Groq (fallback)
- **Legacy:** agent-browser CLI wrapper (preserved as fallback)
- **Testing:** pytest (222 tests, httpx_mock fixtures, 93%+ on core modules)
- **Protocols:** MCP (Model Context Protocol), WebSocket

### Architecture

```
Playwright CDP → Badge Injection (200ms) → Vision Model → DOM Execution (50ms)
                                              ↓
                                    MCP Server / WebSocket Live Preview
```

- `FastOrchestrator` (Playwright) — primary mode (~2-5s/turn)
- `Orchestrator` (agent-browser CLI) — legacy mode (~30-60s/turn)
- `MCPServer` — 6 tools for AI agent integration
- `WebSocketPreview` — real-time browser state streaming
- `MultiBrowserManager` — unified API across Chromium/Firefox/WebKit
- `SessionPool` — concurrent multi-browser session management
- Both orchestrators share `VisionClient`, `Config`, `Exceptions`

### What's Working

- ✅ Playwright CDP connection to existing Brave browser
- ✅ Badge overlay injection with CSS selector generation
- ✅ A11y tree extraction for model context
- ✅ NIM Vision API integration with retry/backoff
- ✅ Structured logging (JSON file + console)
- ✅ Pydantic config models with validation
- ✅ Custom exception hierarchy
- ✅ **222 tests passing** across all modules (93%+ coverage on core modules)
- ✅ **HTTP mock infrastructure** — pytest-httpx with reusable fixtures for deterministic testing
- ✅ **Model JSON compliance** — `ModelResponseError`, regex extraction, progressive retry
- ✅ **MCP server with 6 tools** (navigate, screenshot, click, fill, extract, execute)
- ✅ **MCP server hardened** — health check tool, error recovery, connection state tracking
- ✅ WebSocket live preview with HTML dashboard
- ✅ Multi-browser support (Chromium, Firefox, WebKit)
- ✅ Concurrent session pool with isolation
- ✅ **Diff screenshot integration** — auto-capture in orchestrator with configurable threshold
- ✅ Persistent session management (cookies, storage)
- ✅ **CLI polish** — Rich progress indicators, readable errors, task summaries

### Known Gaps

- Model JSON compliance improved but NIM still returns prose occasionally (mitigated by retry + regex extraction)
- Overall package coverage at 56% (orchestrator.py at 12%, browser.py at 28%) due to integration-heavy modules
- No formal chaos/property-based testing yet

---

## Requirements

### Validated

- ✓ Navigate to any URL via Playwright CDP — existing
- ✓ Screenshot + badge injection with CSS selectors — existing
- ✓ Vision model inference (NIM primary, Groq fallback) — existing
- ✓ DOM execution (click, fill, press, scroll) — existing
- ✓ Task verification (post-completion check) — existing
- ✓ Retry with exponential backoff — existing
- ✓ Rate limiting between API calls — existing
- ✓ Input validation (URLs, keys, text length) — existing
- ✓ Graceful shutdown (signal handlers) — existing
- ✓ Browser crash recovery — existing
- ✓ Structured file logging (JSON, rotating) — existing
- ✓ Differential screenshots — v0.4
- ✓ Persistent session management — v0.4
- ✓ MCP server mode — v0.5
- ✓ WebSocket live preview — v0.5
- ✓ Multi-browser support (Firefox, Safari) — v0.5
- ✓ Concurrent multi-browser sessions — v0.5
- ✓ Model JSON compliance (MODEL-01 to MODEL-04) — v0.6
- ✓ Diff screenshot integration (DIFF-01 to DIFF-04) — v0.6
- ✓ MCP server hardening (MCP-01 to MCP-04) — v0.6
- ✓ CLI improvements (CLI-01 to CLI-04) — v0.6
- ✓ Test coverage (TEST-01 to TEST-04) — v0.6

### Active

- [ ] Next milestone features (TBD — v0.7 planning)
- [ ] Improve overall package coverage (orchestrator.py at 12%, browser.py at 28%)

## Current Milestone: v0.7 Production Readiness & Scale

**Goal:** Close all remaining production gaps to make vision-browser production-ready.

**Target features:**
- Wire differential screenshots to Vision API (analyze integration)
- Circuit breaker for sustained API failures
- Rate limit persistence across runs
- MCP server integration tests (end-to-end tool calls)
- Multi-browser manager browser launch integration
- Session pool concurrent execution tests
- WebSocket HTML dashboard served automatically
- Performance benchmarks and regression tracking
- Documentation site / API reference (beyond README)
- CI/CD pipeline (GitHub Actions)

### Out of Scope

- Mobile device emulation — desktop-only for now
- Video recording — screenshots only
- Distributed/cluster automation — single browser session only

---

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Playwright over agent-browser CLI | 10x faster (no subprocess overhead), persistent CDP connection | ✓ FastOrchestrator is primary mode |
| NVIDIA NIM over Groq primary | Groq vision models decommissioned on current account | ✓ NIM primary, Groq fallback works |
| Badge injection + CSS selectors | DOM-validated refs eliminate model hallucination | ✓ 80-95% accuracy vs 40-60% |
| Dual orchestrator pattern | Preserve working legacy mode during transition | ✓ Both modes available via --fast flag |
| MIT License | Maximum adoption for developer tool | ✓ Published on GitHub |
| MCP server integration | AI agent ecosystem compatibility | ✓ Works with Claude, Cursor, other MCP clients |
| Multi-engine support | Firefox + Safari via Playwright engines | ✓ Unified API, CDP restricted to Chromium |
| Session pool architecture | Independent contexts for concurrency | ✓ Isolation verified, clean shutdown |
| Differential screenshots | Reduce bandwidth and API costs | ✓ Binary fast path, PIL optional for regions |
| pytest-httpx over patch("httpx.post") | HTTP-level interception catches all httpx usage | ✓ Deterministic tests, no network needed |
| ModelResponseError for validation failures | Structured errors over silent fallbacks | ✓ Retry with stricter prompts, then fail with context |
| MCP error recovery wrapping | Per-handler try/except prevents server crashes | ✓ All tools recover gracefully |
| Rich as optional dependency | Graceful fallback for environments without Rich | ✓ CLI works with or without |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-04-05 after v0.6 milestone shipped*
