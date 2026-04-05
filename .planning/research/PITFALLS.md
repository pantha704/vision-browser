# Pitfalls Research — v0.6 Developer Experience & Reliability

## Overview

Common mistakes when adding developer experience and reliability features to an existing browser automation system, with prevention strategies.

## Pitfall 1: Over-Engineering JSON Compliance

**Risk:** Building a complex parsing system that tries to handle every possible malformed response.

**Warning signs:**
- Regex patterns growing beyond 50 characters
- Special cases for different response formats
- Parsing taking longer than the model response itself

**Prevention:**
- Keep the pipeline simple: validate → extract (one regex) → retry (2x max) → error
- If the model consistently fails, the fix is a better prompt, not a better parser
- Set a hard limit: if parsing takes >100ms, something is wrong

**Which phase addresses it:** Phase 1 (Model JSON Compliance)

## Pitfall 2: Performance Regression from Auto-Screenshots

**Risk:** Differential screenshots add significant latency to every action, making the tool feel slow.

**Warning signs:**
- Action latency increases by >500ms
- Memory usage grows unbounded (screenshots not being cleaned up)
- Disk space consumed by stored diffs

**Prevention:**
- Make auto-capture opt-in via config flag (disabled by default)
- Set a configurable diff threshold to skip identical frames
- Implement automatic cleanup: keep only last N diffs per session
- Benchmark: screenshot capture should add <200ms per action

**Which phase addresses it:** Phase 2 (Differential Screenshot Integration)

## Pitfall 3: MCP Error Handling Breaking Existing Clients

**Risk:** Adding error recovery changes the response format, breaking existing MCP clients that expect specific response shapes.

**Warning signs:**
- Error responses include extra fields not in the original tool schema
- Successful responses wrapped in error-handling containers
- Health check tool changes the tool list (version mismatch)

**Prevention:**
- Keep tool response schemas backward-compatible
- Error responses should use the same shape as successful responses, just with error-specific content
- Document the health check tool as optional (clients can ignore it)
- Test with existing MCP clients after changes

**Which phase addresses it:** Phase 3 (MCP Server Hardening)

## Pitfall 4: Rich Dependency Breaking Environments

**Risk:** Adding Rich as a dependency causes issues in minimal environments or CI.

**Warning signs:**
- Import errors in environments without Rich installed
- Terminal compatibility issues (Windows, minimal Linux)
- Increased startup time from Rich initialization

**Prevention:**
- Make Rich an optional dependency with graceful fallback
- Use try/except import: `try: from rich.console import Console; except ImportError: Console = None`
- Fall back to basic `print()` when Rich is unavailable
- Pin Rich version in requirements.txt

**Which phase addresses it:** Phase 4 (CLI Improvements)

## Pitfall 5: Flaky Tests from Mocked APIs

**Risk:** Tests that mock the NIM API become unreliable because the mocks don't match real behavior.

**Warning signs:**
- Tests pass locally but fail in CI
- Tests that mock JSON responses don't cover real-world malformed responses
- Timing-dependent tests (timeouts, retries) fail intermittently

**Prevention:**
- Use a mix of ideal and realistic mock responses (include some malformed JSON)
- Mock at the HTTP level (responses/httpx) not at the function level
- Use fixed clocks for timeout/retry tests instead of real time.sleep()
- Keep integration tests separate from unit tests

**Which phase addresses it:** Ongoing (all phases)

## Pitfall 6: Scope Creep in "Developer Experience"

**Risk:** "Developer experience" is broad — easy to add features that aren't core to the milestone goal.

**Warning signs:**
- Adding features that only benefit developers of the codebase, not users of the tool
- Building features that would be better as a separate milestone
- Features that require significant architectural changes

**Prevention:**
- Stay focused on the 5 defined feature categories
- Any new feature request → backlog for future milestone
- Time-box each phase to prevent expansion
- Define clear success criteria before starting each phase

**Which phase addresses it:** All phases (milestone discipline)

## Pitfall 7: Ignoring the Vision Model Latency

**Risk:** Adding features that compound the existing 2-5 second per-turn latency, making the tool feel unresponsive.

**Warning signs:**
- Total action time exceeds 10 seconds
- Multiple sequential API calls without parallelization
- Blocking operations during the model response wait time

**Prevention:**
- All new features should be non-blocking where possible
- Differential screenshots should happen asynchronously
- CLI progress indicators should update during model wait time
- Benchmark each change: if it adds >500ms of blocking time, reconsider

**Which phase addresses it:** All phases (performance awareness)

## Prevention Summary

| Pitfall | Severity | Likelihood | Prevention |
|---------|----------|------------|------------|
| Over-engineering JSON parsing | Medium | High | Simple pipeline, max 2 retries |
| Auto-screenshot performance | High | Medium | Opt-in default, cleanup, threshold |
| MCP backward compat | High | Low | Same response shape, test with clients |
| Rich dependency | Low | Medium | Optional import, graceful fallback |
| Flaky mock tests | Medium | Medium | Realistic mocks, HTTP-level mocking |
| Scope creep | Medium | High | Time-box phases, strict criteria |
| Compounding latency | High | Medium | Non-blocking design, benchmark each change |
