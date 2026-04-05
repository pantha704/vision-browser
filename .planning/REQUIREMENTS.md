# Requirements — v0.6 Developer Experience & Reliability

## Model Compliance (MODEL)

- [ ] **MODEL-01**: Every vision model response is validated as JSON before use, with structured error on failure
- [ ] **MODEL-02**: JSON extraction from mixed responses (markdown code blocks, prose-wrapped) using regex pattern
- [ ] **MODEL-03**: Retry with progressively stricter prompts on JSON parse failure (max 2 retries)
- [ ] **MODEL-04**: Structured error reporting includes expected schema, raw response, and debugging context

## Differential Screenshots (DIFF)

- [ ] **DIFF-01**: Differential screenshots automatically captured before and after each orchestrator action (opt-in via config)
- [ ] **DIFF-02**: Configurable diff threshold to skip identical or near-identical frames
- [ ] **DIFF-03**: Diff results stored with task context and retrievable for debugging
- [ ] **DIFF-04**: Automatic cleanup of old diffs (keep last N per session, configurable)

## MCP Server (MCP)

- [ ] **MCP-01**: Health check tool (`ping`/`health`) for client verification of server status
- [ ] **MCP-02**: All MCP tools wrapped in error recovery — never raise unhandled exceptions to clients
- [ ] **MCP-03**: Connection state tracking (connected, disconnected, recovering) with state queries
- [ ] **MCP-04**: Structured error responses with retry-after hints on model API failures

## CLI (CLI)

- [ ] **CLI-01**: Real-time progress indicators during task execution (current step, action being performed)
- [ ] **CLI-02**: Human-readable error messages with suggested fixes instead of stack traces
- [ ] **CLI-03**: Task summary report on completion (actions taken, success/failure, final state)
- [ ] **CLI-04**: Rich is optional dependency — graceful fallback to basic output when unavailable

## Test Coverage (TEST)

- [ ] **TEST-01**: VisionClient unit tests with mocked NIM API responses (ideal and malformed)
- [ ] **TEST-02**: DesktopController unit tests for badge injection, selector generation, action execution
- [ ] **TEST-03**: CLI unit tests for argument parsing, output formatting, error handling
- [ ] **TEST-04**: Integration tests for common user flows (navigate, click, fill form, extract data)

---

## Future Requirements (Deferred)

### Model Improvements
- [ ] Alternative vision model support (OpenAI, Anthropic, local models)
- [ ] Fine-tuned model for structured output (higher compliance rate)
- [ ] Parser model pipeline (vision model → parser model → JSON)

### Advanced Features
- [ ] Visual regression detection (alert on unexpected page changes)
- [ ] Diff annotation (overlay action descriptions on screenshots)
- [ ] Additional MCP tools (`wait_for_element`, `get_page_info`, `execute_javascript`)
- [ ] Session management MCP tools (`save_session`, `restore_session`, `list_sessions`)
- [ ] Property-based tests with Hypothesis library
- [ ] Chaos testing (inject failures: network, API, browser crashes)

---

## Out of Scope

| Exclusion | Reasoning |
|-----------|-----------|
| Mobile device emulation | Desktop-only scope is intentional |
| Video recording | Screenshots only — video adds significant complexity |
| Distributed/cluster automation | Single-browser scope is intentional |
| Alternative vision models in v0.6 | NIM + Groq fallback is sufficient; defer to future milestone |
| Database/persistence layer | File-based session state is adequate for current scope |
| GUI framework | CLI + MCP + WebSocket dashboard is the right abstraction |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODEL-01 | Phase 11 | Not started |
| MODEL-02 | Phase 11 | Not started |
| MODEL-03 | Phase 11 | Not started |
| MODEL-04 | Phase 11 | Not started |
| DIFF-01 | Phase 12 | Not started |
| DIFF-02 | Phase 12 | Not started |
| DIFF-03 | Phase 12 | Not started |
| DIFF-04 | Phase 12 | Not started |
| MCP-01 | Phase 13 | Not started |
| MCP-02 | Phase 13 | Not started |
| MCP-03 | Phase 13 | Not started |
| MCP-04 | Phase 13 | Not started |
| CLI-01 | Phase 14 | Not started |
| CLI-02 | Phase 14 | Not started |
| CLI-03 | Phase 14 | Not started |
| CLI-04 | Phase 14 | Not started |
| TEST-01 | Phase 10 | Not started |
| TEST-02 | Phase 14 | Not started |
| TEST-03 | Phase 14 | Not started |
| TEST-04 | Phase 10-14 | Not started |
