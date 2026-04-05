# Roadmap — v0.6 Developer Experience & Reliability

## Overview

| Metric | Value |
|--------|-------|
| Phases | 5 |
| Requirements | 20 |
| Requirements mapped | 20 (100%) |
| Previous milestone | v0.5 (ended at phase 9) |
| Starting phase | 10 |

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 10 | Test Infrastructure & Mocks | Set up mock infrastructure for deterministic NIM API tests | TEST-01 | Mocks created, realistic malformed responses included |
| 11 | Model JSON Compliance | Reliable structured output from vision model | MODEL-01, MODEL-02, MODEL-03, MODEL-04 | 95%+ JSON compliance rate on retry |
| 12 | Differential Screenshot Integration | Auto-capture diffs in orchestrator flow | DIFF-01, DIFF-02, DIFF-03, DIFF-04 | Diffs captured, stored, cleaned up automatically |
| 13 | MCP Server Hardening | Resilient MCP server with health monitoring | MCP-01, MCP-02, MCP-03, MCP-04 | Health check works, errors never crash server |
| 14 | CLI Improvements | Polished CLI with progress indicators | CLI-01, CLI-02, CLI-03, CLI-04 | Rich progress bars, readable errors, task summary |

---

## Phase 10: Test Infrastructure & Mocks

**Goal:** Set up mock infrastructure for deterministic NIM API tests, enabling all subsequent work.

**Requirements:**
- [ ] **TEST-01**: VisionClient unit tests with mocked NIM API responses (ideal and malformed)

**Success Criteria:**
1. HTTP-level mocks for NIM API using `responses` or `pytest-httpx`
2. Mock responses include both valid JSON and realistic malformed responses (prose, markdown blocks, partial JSON)
3. VisionClient tests can run without network access
4. Mock responses are reusable across other test files
5. Tests run in <5 seconds total (no real API calls)

**Notes:** This phase enables all other work by providing deterministic testing infrastructure. Model compliance changes (Phase 11) cannot be properly tested without this.

---

## Phase 11: Model JSON Compliance

**Goal:** Reliable structured output from vision model through validation pipeline with retry.

**Requirements:**
- [ ] **MODEL-01**: Every vision model response is validated as JSON before use, with structured error on failure
- [ ] **MODEL-02**: JSON extraction from mixed responses (markdown code blocks, prose-wrapped) using regex pattern
- [ ] **MODEL-03**: Retry with progressively stricter prompts on JSON parse failure (max 2 retries)
- [ ] **MODEL-04**: Structured error reporting includes expected schema, raw response, and debugging context

**Success Criteria:**
1. 95%+ of model responses result in valid JSON (including retries)
2. Malformed responses are automatically retried with stricter prompts
3. After max retries, a structured `ModelResponseError` is raised with schema context
4. All existing VisionClient tests pass with mocked responses
5. No regression in successful parsing latency (<50ms added for validation)

**Notes:** Highest risk phase. If the model consistently fails to produce JSON after retries, the fallback is a better system prompt, not a more complex parser.

---

## Phase 12: Differential Screenshot Integration

**Goal:** Auto-capture differential screenshots in the orchestrator execution flow with configurable thresholds.

**Requirements:**
- [ ] **DIFF-01**: Differential screenshots automatically captured before and after each orchestrator action (opt-in via config)
- [ ] **DIFF-02**: Configurable diff threshold to skip identical or near-identical frames
- [ ] **DIFF-03**: Diff results stored with task context and retrievable for debugging
- [ ] **DIFF-04**: Automatic cleanup of old diffs (keep last N per session, configurable)

**Success Criteria:**
1. With `auto_diff_screenshots: true` in config, every action produces a diff result
2. With `auto_diff_screenshots: false` (default), no performance impact
3. Diffs below the configured threshold are skipped (not stored)
4. Diffs are stored in session directory with timestamp and action context
5. Old diffs are automatically cleaned up (configurable max count, default 10)
6. Auto-capture adds <200ms per action (benchmark verified)

**Notes:** Low risk. The `diff_screenshot` module already exists — this is wiring it into the orchestrator.

---

## Phase 13: MCP Server Hardening

**Goal:** Resilient MCP server with health monitoring, error recovery, and connection lifecycle management.

**Requirements:**
- [ ] **MCP-01**: Health check tool (`ping`/`health`) for client verification of server status
- [ ] **MCP-02**: All MCP tools wrapped in error recovery — never raise unhandled exceptions to clients
- [ ] **MCP-03**: Connection state tracking (connected, disconnected, recovering) with state queries
- [ ] **MCP-04**: Structured error responses with retry-after hints on model API failures

**Success Criteria:**
1. `health` MCP tool returns server status (ok/degraded/error) with details
2. All existing 6 tools continue to work with identical response shapes
3. Browser crash during tool execution returns structured error, not crash
4. Model API failure returns error with `retry_after` hint (seconds)
5. Connection state is queryable and updates on state changes
6. Existing MCP clients (Claude, Cursor) continue to work after changes

**Notes:** Medium risk. Must maintain backward compatibility with existing tool response formats.

---

## Phase 14: CLI Improvements

**Goal:** Polished CLI with real-time progress indicators, readable error messages, and task summary reports.

**Requirements:**
- [ ] **CLI-01**: Real-time progress indicators during task execution (current step, action being performed)
- [ ] **CLI-02**: Human-readable error messages with suggested fixes instead of stack traces
- [ ] **CLI-03**: Task summary report on completion (actions taken, success/failure, final state)
- [ ] **CLI-04**: Rich is optional dependency — graceful fallback to basic output when unavailable

**Success Criteria:**
1. During task execution, user sees current step and action (e.g., "→ Clicking 'Submit' button...")
2. Errors display as formatted messages with suggestions (e.g., "Cannot connect to browser. Check if Playwright is installed.")
3. Task completion shows summary table: actions taken, time elapsed, success/failure
4. CLI works correctly with Rich installed and without Rich (basic output fallback)
5. No regression in CLI startup time (<100ms added)
6. All existing CLI commands work identically (backward compatible)

**Notes:** Low risk. Cosmetic improvements with graceful fallback. Rich is optional.

---

## Dependency Graph

```
Phase 10 (Test Infra) ─────────────────────────────────────┐
                      ↓                                    ↓
Phase 11 (Model) ────→ Required for Phase 13 (MCP)         │
                      ↓                                    │
Phase 12 (Diff) ──────→ Independent, can parallelize       │
                                                   All feed into
Phase 14 (CLI) ──────→ Benefits from all above             │
                                                             ↓
                                                    Integration verified
                                                    in existing test suite
```

**Parallel execution notes:**
- Phase 12 (Differential Screenshots) can start in parallel with Phase 11 after Phase 10 is done
- Phase 14 (CLI) should wait for Phase 13 (MCP) to ensure error messages are consistent
- Phase 13 (MCP) should wait for Phase 11 (Model) to have stable error handling

---

## Traceability

| Requirement | Phase |
|-------------|-------|
| MODEL-01 | Phase 11 |
| MODEL-02 | Phase 11 |
| MODEL-03 | Phase 11 |
| MODEL-04 | Phase 11 |
| DIFF-01 | Phase 12 |
| DIFF-02 | Phase 12 |
| DIFF-03 | Phase 12 |
| DIFF-04 | Phase 12 |
| MCP-01 | Phase 13 |
| MCP-02 | Phase 13 |
| MCP-03 | Phase 13 |
| MCP-04 | Phase 13 |
| CLI-01 | Phase 14 |
| CLI-02 | Phase 14 |
| CLI-03 | Phase 14 |
| CLI-04 | Phase 14 |
| TEST-01 | Phase 10 |
| TEST-02 | Phase 14 (CLI tests) |
| TEST-03 | Phase 14 (CLI tests) |
| TEST-04 | Phase 10-14 (ongoing) |

*Note: TEST-02 (DesktopController tests) and TEST-03 (CLI tests) are distributed across phases where those components are modified. TEST-04 (integration tests) is ongoing across all phases.*
