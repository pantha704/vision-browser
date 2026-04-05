# Vision Browser

## What This Is

**Fast vision-driven browser automation** using **Playwright + NVIDIA NIM Llama 3.2 90B Vision**.

Navigate, search, fill forms, and extract data from any website using natural language commands. 10x faster than CLI-based approaches with DOM-validated element refs for 80-95% accuracy. Now with MCP server mode, WebSocket live preview, multi-browser support, and concurrent session management.

**Core value:** Automate any web task by describing it in plain English — no selectors, no scripts, no coding.

---

## Context

- **Status:** v0.5 shipped — full ecosystem with MCP, WebSocket, multi-browser, sessions
- **Repository:** https://github.com/pantha704/vision-browser
- **Type:** Python library + CLI tool
- **License:** MIT
- **Author:** pantha704

### Technical Stack

- **Runtime:** Python 3.14
- **Browser:** Playwright (CDP for Chromium, standard for Firefox/WebKit)
- **Vision AI:** NVIDIA NIM Llama 3.2 90B Vision (primary), Groq (fallback)
- **Legacy:** agent-browser CLI wrapper (preserved as fallback)
- **Testing:** pytest (66+ tests across all modules)
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
- ✅ 66+ unit tests passing
- ✅ MCP server with 6 tools (navigate, screenshot, click, fill, extract, execute)
- ✅ WebSocket live preview with HTML dashboard
- ✅ Multi-browser support (Chromium, Firefox, WebKit)
- ✅ Concurrent session pool with isolation
- ✅ Differential screenshots (binary + pixel-level diffing)
- ✅ Persistent session management (cookies, storage)

### Known Gaps

- Model JSON compliance (NIM returns prose ~50% — partially mitigated by schema enforcement)
- Phase 2.0 (VisionClient + DesktopController tests) completed without formal SUMMARY.md

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

### Active

- [ ] Full test coverage — Phase 2.0 gap (VisionClient + DesktopController tests)
- [ ] Model JSON compliance improvement
- [ ] Next milestone features (TBD)

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

*Last updated: 2026-04-05 after v0.5 Ecosystem Integration milestone*
