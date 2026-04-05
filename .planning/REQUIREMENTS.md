# Requirements

## Validated

Inferred from existing codebase (ARCHITECTURE.md, STACK.md, code tests):

- ✓ Navigate to any URL via Playwright CDP connection — existing
- ✓ Screenshot with badge overlay injection — existing
- ✓ Extract CSS selectors + a11y info from page elements — existing
- ✓ Vision model inference (NVIDIA NIM primary, Groq fallback) — existing
- ✓ Structured JSON output from vision model — existing
- ✓ DOM execution (click, fill, press, scroll, wait) — existing
- ✓ Action validation against available refs — existing
- ✓ Task verification (post-completion screenshot check) — existing
- ✓ Retry with exponential backoff (3 attempts) — existing
- ✓ Rate limiting between API requests — existing
- ✓ Input validation (URLs http/https only, key allowlist, text length limits) — existing
- ✓ Graceful shutdown (SIGINT/SIGTERM handlers) — existing
- ✓ Browser crash detection + auto-restart — existing
- ✓ Structured logging (JSON file + console) — existing
- ✓ Pydantic config models with validation — existing
- ✓ Custom exception hierarchy (8 classes) — existing
- ✓ Dual orchestrator mode (FastOrchestrator + legacy Orchestrator) — existing
- ✓ 34 unit tests passing — existing

## Active

- [ ] Differential screenshots (send only changed regions after first turn)
- [ ] MCP server mode for AI agent ecosystems
- [ ] WebSocket live preview for real-time monitoring
- [ ] Persistent session/cookie management across runs
- [ ] Full test coverage — 6 gaps identified:
  - FastOrchestrator (no tests)
  - VisionClient retry/fallback logic (no tests)
  - CLI argument parsing (no tests)
  - inject.js badge generation (no tests)
  - DesktopController (no tests)
  - Legacy Orchestrator (no tests)

## Out of Scope

- Multi-browser support (Firefox, Safari) — Playwright supports but deferred to v2
- Mobile device emulation — desktop-only for v1
- Video recording — screenshots only
- Distributed/cluster automation — single browser session only
- CAPTCHA solving — use authenticated browser sessions instead

---

*Last updated: 2026-04-05 — Inferred from codebase map*
