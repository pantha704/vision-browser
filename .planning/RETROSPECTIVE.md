# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.6 — Developer Experience & Reliability

**Shipped:** 2026-04-05
**Phases:** 5 | **Plans:** 6

### What Was Built
- HTTP mock infrastructure with pytest-httpx (8 mock builders, 10 reusable fixtures)
- Model JSON compliance with `ModelResponseError`, regex extraction, progressive retry
- Differential screenshot integration in orchestrator flow (auto-capture, configurable threshold, cleanup)
- MCP server hardening (health tool, error recovery, connection state tracking, structured errors with retry_after)
- CLI polish (Rich progress indicators, readable errors, task summaries, graceful fallback)
- 222 tests passing with 93%+ coverage on core modules

### What Worked
- Parallel phase execution was effective — phases 12, 13, 14 could be completed independently
- Phase-level summaries (single SUMMARY.md per phase) kept tracking clean
- pytest-httpx over patch("httpx.post") was the right call — caught real bugs in error handling
- Discovering and fixing the HTTPError .response AttributeError during test migration — real production bug prevented
- Using "approve all" gates for complete-milestone saved significant time with clear phase boundaries

### What Was Inefficient
- REQUIREMENTS.md traceability table was never updated during development (all 20 REQ-IDs showed "Not started")
- Phase 11 had 2 plans but only 1 phase-level summary — some per-plan detail was lost
- No retrospective was created for v0.5 milestone

### Patterns Established
- pytest-httpx fixtures in conftest.py with autouse — reusable across all test files
- Phase-level SUMMARY.md (not per-plan) as the single summary source
- Progressive retry pattern for model compliance failures
- Structured error responses with retry_after hints across all layers
- Health check tool pattern for server resilience

### Key Lessons
1. Test infrastructure investments compound — mock infrastructure enabled all subsequent phases to be tested deterministically
2. Error handling code is the hardest to test — the HTTPError .response bug was only found because we mocked real-world failure modes
3. Traceability tables need per-phase updates — manual updates at milestone completion are error-prone and lose fidelity
4. Single-phase summaries with per-plan details work better than one monolithic summary

### Cost Observations
- Model mix: primarily sonnet for execution, haiku for verification
- Sessions: ~15 hours of continuous work
- Notable: 77 files changed, 7,376 insertions — significant code addition driven by test infrastructure and hardening

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v0.4 | 2 | 2 | Initial milestone |
| v0.5 | 9 | 9 | Ecosystem expansion (MCP, WebSocket, multi-browser) |
| v0.6 | 5 | 6 | Developer experience — fewer phases, deeper hardening |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v0.5 | 151+ | ~80% core | MCP server, WebSocket, multi-browser |
| v0.6 | 222 | 93% core | Mock infra, ModelResponseError, error recovery, CLI polish |

### Top Lessons (Verified Across Milestones)

1. Infrastructure-first pays dividends — mock infra (v0.6) and test coverage (v0.5) enabled rapid, confident development in all subsequent phases
2. Error handling requires dedicated attention — HTTPError bug (v0.6) and MCP error recovery (v0.6) both required separate phases
3. Traceability needs automation — both v0.5 and v0.6 had incomplete REQUIREMENTS.md traceability at milestone completion
