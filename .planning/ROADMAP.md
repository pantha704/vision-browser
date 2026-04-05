# Roadmap

## Milestone 1: v0.4 — Production Ready

**Goal:** Close testing gaps, add differential screenshots, stabilize for real-world use.

### Phases

- [x] **Phase 1.0: Test Coverage — FastOrchestrator + CLI + inject.js** (completed 2026-04-05)
- [x] **Phase 2.0: Test Coverage — VisionClient + DesktopController** (completed 2026-04-05)
- [x] **Phase 3.0: Differential Screenshots** (completed 2026-04-05)
- [x] **Phase 4.0: Persistent Session Management** (completed 2026-04-05)
- [x] **Phase 5.0: Polish — Logging, Error Messages, Documentation** (completed 2026-04-05)

### Phase 1.0: Test Coverage — FastOrchestrator + CLI + inject.js

**Goal:** Add comprehensive test coverage for FastOrchestrator, CLI entry point, and inject.js browser script.
**Success Criteria:**
1. All FastOrchestrator methods covered with unit tests
2. CLI command parsing and error handling tested
3. inject.js badge injection logic tested
4. Test suite passes with 80%+ coverage on these modules

### Phase 2.0: Test Coverage — VisionClient + DesktopController

**Goal:** Add test coverage for VisionClient API interactions and DesktopController integration.
**Success Criteria:**
1. VisionClient API calls mocked and tested (success, retry, error paths)
2. DesktopController state management tested
3. Config validation edge cases covered
4. All existing 34 tests still pass

### Phase 3.0: Differential Screenshots

**Goal:** Implement differential screenshot capture — send only changed regions to reduce API cost and bandwidth.
**Success Criteria:**
1. Screenshot diffing algorithm implemented
2. Only changed regions sent to vision API
3. Configurable diff threshold
4. Bandwidth savings measurable vs full screenshots

### Phase 4.0: Persistent Session Management

**Goal:** Save and restore browser sessions (cookies, localStorage, sessionStorage) across runs.
**Success Criteria:**
1. Session state exported on shutdown
2. Session state imported on startup
3. Session file format documented
4. CLI flag to enable/disable session persistence

### Phase 5.0: Polish — Logging, Error Messages, Documentation

**Goal:** Improve developer experience with better logging, clearer error messages, and comprehensive documentation.
**Success Criteria:**
1. Structured logging covers all major operations
2. Error messages actionable and user-friendly
3. README updated with full feature documentation
4. API docs for all public interfaces

---

## Milestone 2: v0.5 — Ecosystem Integration

**Goal:** MCP server mode, WebSocket live preview, multi-browser support.

### Phases

- [x] **Phase 2.1: MCP Server Mode** (completed 2026-04-05)
- [x] **Phase 2.2: WebSocket Live Preview** (completed 2026-04-05)
- [x] **Phase 2.3: Firefox + Safari Support** (completed 2026-04-05)
- [x] **Phase 2.4: Concurrent Multi-Browser Sessions** (completed 2026-04-05)

### Phase 2.1: MCP Server Mode

**Goal:** Expose vision-browser capabilities as an MCP (Model Context Protocol) server for AI agent ecosystems.
**Success Criteria:**
1. MCP server starts on configurable port
2. Tools: navigate, screenshot, click, fill, extract, execute
3. Resource: current page state
4. Compatible with Claude, Cursor, and other MCP clients

### Phase 2.2: WebSocket Live Preview

**Goal:** Real-time WebSocket streaming of browser state for live debugging and monitoring.
**Success Criteria:**
1. WebSocket server streams screenshot updates
2. Events: navigation, clicks, fills, errors
3. Configurable streaming interval
4. Simple web dashboard for live preview

### Phase 2.3: Firefox + Safari Support

**Goal:** Extend browser support beyond Chromium-based browsers to Firefox and Safari/WebKit.
**Success Criteria:**
1. Firefox launch and connection via Playwright
2. Safari/WebKit support on macOS
3. Browser-agnostic badge injection (or fallback strategy)
4. CLI flag to select browser engine

### Phase 2.4: Concurrent Multi-Browser Sessions

**Goal:** Run and orchestrate multiple browser sessions concurrently for parallel task execution.
**Success Criteria:**
1. Multiple browser instances managed independently
2. Session isolation (cookies, state, context)
3. Unified CLI interface for session management
4. Resource usage monitoring and limits

---

*Last updated: 2026-04-05*
