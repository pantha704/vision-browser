# Vision Browser

## What This Is

**Fast vision-driven browser automation** using **Playwright + NVIDIA NIM Llama 3.2 90B Vision**.

Navigate, search, fill forms, and extract data from any website using natural language commands. 10x faster than CLI-based approaches with DOM-validated element refs for 80-95% accuracy.

**Core value:** Automate any web task by describing it in plain English — no selectors, no scripts, no coding.

---

## Context

- **Status:** MVP shipped — core architecture working, 34 tests passing
- **Repository:** https://github.com/pantha704/vision-browser
- **Type:** Python library + CLI tool
- **License:** MIT
- **Author:** pantha704

### Technical Stack

- **Runtime:** Python 3.14
- **Browser:** Playwright (persistent CDP connection to Brave/Chrome)
- **Vision AI:** NVIDIA NIM Llama 3.2 90B Vision (primary), Groq (fallback)
- **Legacy:** agent-browser CLI wrapper (preserved as fallback)
- **Testing:** pytest (34 tests: 22 core + 12 Playwright)

### Architecture

```
Playwright CDP → Badge Injection (200ms) → Vision Model → DOM Execution (50ms)
```

- `FastOrchestrator` (Playwright) — new, fast mode (~2-5s/turn)
- `Orchestrator` (agent-browser CLI) — legacy mode (~30-60s/turn)
- Both share `VisionClient`, `Config`, `Exceptions`

### What's Working

- ✅ Playwright CDP connection to existing Brave browser
- ✅ Badge overlay injection with CSS selector generation
- ✅ A11y tree extraction for model context
- ✅ NIM Vision API integration with retry/backoff
- ✅ Structured logging (JSON to file + human-readable console)
- ✅ Pydantic config models with validation
- ✅ Custom exception hierarchy
- ✅ 34 unit tests passing

### Known Gaps

- 6 testing coverage gaps (FastOrchestrator, VisionClient, CLI, inject.js, DesktopController, legacy Orchestrator)
- Model JSON compliance (NIM returns prose ~50% — partially mitigated by schema enforcement)
- No differential screenshots (sends full image every turn)
- No MCP server mode or WebSocket live preview

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
- ✓ 34 unit tests passing — existing

### Active

- [ ] Differential screenshots (changed regions only)
- [ ] MCP server mode for AI agent ecosystems
- [ ] WebSocket live preview for debugging
- [ ] Persistent session/cookie management
- [ ] Full test coverage (6 gaps identified)
- [ ] Differential screenshots to reduce bandwidth + API cost

### Out of Scope

- [ ] Multi-browser support (Firefox, Safari) — Playwright supports but out of scope for v1
- [ ] Mobile device emulation — desktop-only for now
- [ ] Video recording — screenshots only
- [ ] Distributed/cluster automation — single browser session only

---

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Playwright over agent-browser CLI | 10x faster (no subprocess overhead), persistent CDP connection | FastOrchestrator is primary mode |
| NVIDIA NIM over Groq primary | Groq vision models decommissioned on current account | NIM primary, Groq fallback |
| Badge injection + CSS selectors | DOM-validated refs eliminate model hallucination | 80-95% accuracy vs 40-60% |
| Dual orchestrator pattern | Preserve working legacy mode during transition | Both modes available via --fast flag |
| MIT License | Maximum adoption for developer tool | Published on GitHub |

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

*Last updated: 2026-04-05 after GSD initialization*
