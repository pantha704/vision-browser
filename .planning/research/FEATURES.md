# Features Research — v0.6 Developer Experience & Reliability

## Overview

Analysis of feature categories for v0.6: model JSON compliance, differential screenshot integration, MCP server hardening, CLI improvements, and test coverage.

## Category 1: Model JSON Compliance

### Table Stakes
- **JSON validation on all model responses** — Every response from the vision model must be validated as JSON before use. Invalid responses trigger retry.
- **Graceful degradation on persistent failure** — After max retries, return a structured error with the raw response for debugging rather than crashing.
- **Structured error reporting** — Errors should include what was expected (schema), what was received (raw response), and actionable suggestions.

### Differentiators
- **Progressive prompt hardening** — On failure, automatically strengthen the system prompt for retry attempts. First retry adds emphasis; second retry includes explicit schema example.
- **Response caching for retry analysis** — Log failed responses with their context to identify patterns in model failures over time.
- **Schema versioning** — Allow different JSON schemas for different action types (click, fill, extract, navigate).

### Research Notes
- NIM Llama 3.2 90B Vision is not fine-tuned for JSON output — it's a general vision model
- Typical compliance rates for JSON from vision models range from 40-80% depending on prompt clarity
- The key is not just validation but making the retry loop fast enough that users don't notice the overhead
- Some teams use a separate "parser" model to convert vision model outputs to JSON, but this adds latency and cost

## Category 2: Differential Screenshot Integration

### Table Stakes
- **Auto-capture before/after each action** — Integrate `diff_screenshot` into `FastOrchestrator.execute()` so every action automatically captures differential screenshots
- **Configurable diff thresholds** — Allow users to set sensitivity (e.g., ignore pixel-level anti-aliasing differences)
- **Storage and retrieval** — Store differential screenshots with task context for debugging and audit trails

### Differentiators
- **Visual regression detection** — Alert when expected page changes don't occur (e.g., form submission didn't produce expected result)
- **Diff annotation** — Overlay action descriptions on differential screenshots for human-readable audit logs
- **Bandwidth optimization** — Only transmit/store diffs above a configurable threshold, skip identical frames

### Research Notes
- The `diff_screenshot` module exists but is not wired into the orchestrator execution flow
- Differential screenshots are most valuable for debugging failed tasks, not for every successful action
- Consider making auto-capture opt-in via config flag to avoid unnecessary overhead

## Category 3: MCP Server Hardening

### Table Stakes
- **Health check endpoint** — Add a `/health` or `ping` tool so clients can verify server status
- **Error recovery** — Graceful handling of browser crashes, connection drops, and model API failures
- **Connection lifecycle events** — Notify clients of state changes (connected, disconnected, error, recovering)

### Differentiators
- **Additional MCP tools** — Consider adding `wait_for_element`, `get_page_info`, `execute_javascript` tools
- **Session management tools** — `save_session`, `restore_session`, `list_sessions` for MCP clients
- **Tool versioning** — Support tool version negotiation for backward compatibility

### Research Notes
- MCP specification supports tool versioning via the `title` and `description` fields
- Error handling in MCP should follow the JSON-RPC error code conventions
- The 6 existing tools (navigate, screenshot, click, fill, extract, execute) cover the core use cases well

## Category 4: CLI Improvements

### Table Stakes
- **Real-time progress indicators** — Show current step, estimated time remaining, and action being performed
- **Better error messages** — Replace stack traces with human-readable error descriptions and suggested fixes
- **Task summary report** — After completion, show what actions were taken, success/failure status, and final state

### Differentiators
- **Interactive mode improvements** — Better prompt for multi-step tasks, context-aware suggestions
- **Verbosity levels** — `--quiet`, `--normal`, `--verbose` flags for different output densities
- **Color-coded output** — Green for success, yellow for warnings, red for errors

### Research Notes
- Rich library provides all of these capabilities out of the box
- The current CLI uses basic `print()` and `input()` calls
- Progress indicators are especially important for vision models which can take 2-5 seconds per turn

## Category 5: Test Coverage Completion

### Table Stakes
- **VisionClient tests** — Mock NIM API responses, test JSON parsing, retry logic, error handling
- **DesktopController tests** — Test badge injection, selector generation, action execution
- **Integration tests** — End-to-end tests for common user flows (login, form fill, navigation)

### Differentiators
- **Property-based tests** — Use `hypothesis` to generate random inputs and edge cases
- **Performance benchmarks** — Automated timing tests for key operations (screenshot latency, model response time)
- **Chaos testing** — Inject failures (network drops, API errors, browser crashes) to verify resilience

### Research Notes
- 151 tests passing is good coverage but VisionClient and DesktopController remain untested
- Mocking the NIM API is critical for fast, deterministic tests
- Integration tests should be separate from unit tests (slower, require Playwright)

## Dependencies Between Categories

1. **Model compliance** affects all other categories — if JSON parsing is unreliable, everything downstream is affected
2. **CLI improvements** depend on **MCP hardening** — better error messages require better error handling
3. **Test coverage** is a prerequisite for confidence in all other changes
4. **Differential screenshot integration** is low-risk and can be done independently
