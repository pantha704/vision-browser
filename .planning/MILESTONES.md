# Milestones

## v0.6 Developer Experience & Reliability (In Progress)

**Goal:** Harden the platform by closing known gaps, integrating existing modules into the core flow, and improving developer experience for production readiness.

**Target features:**
- Model JSON compliance — structured output enforcement, retry strategies, fallback chains
- Differential screenshot integration — auto-capture in orchestrator execution flow
- MCP server hardening — error recovery, connection lifecycle, additional tools
- CLI improvements — progress indicators, better error messages, task reporting
- Test coverage completion — close remaining gaps in VisionClient + DesktopController

---

## v0.5 Ecosystem Integration (Shipped: 2026-04-05)

**Phases completed:** 9 phases, 9 plans, 66 tasks

**Key accomplishments:**

1. **Comprehensive test coverage** — 45 tests passing across FastOrchestrator, CLI, prompts, and schema validation (~80% coverage on core modules)
2. **MCP Server Mode** — Full MCP server with 6 tools (navigate, screenshot, click, fill, extract, execute) compatible with Claude, Cursor, and other MCP clients
3. **WebSocket Live Preview** — Real-time streaming of browser state with HTML dashboard for live debugging and monitoring
4. **Multi-Browser Support** — Unified API across Chromium, Firefox, and WebKit (Safari) engines with CDP restriction handling
5. **Concurrent Multi-Browser Sessions** — Session pool with configurable concurrency, isolation, and clean shutdown
6. **Differential Screenshots** — Binary and pixel-level diffing with configurable thresholds to reduce bandwidth and API costs
7. **Persistent Session Management** — Save/restore cookies and storage state across runs with CLI integration
8. **Polish & Documentation** — Structured logging, robust error handling, and comprehensive developer docs

---
