# CONCERNS.md -- Known Issues and Risks

| # | Concern | Severity | Component | Description |
|---|---------|----------|-----------|-------------|
| 1 | NIM prose responses | **HIGH** | `vision.py` | NVIDIA NIM does not support native JSON mode or function calling. The JSON schema is injected into the user prompt as text, relying on the model to comply. When the model returns prose instead of JSON, the `_extract_json()` fallback wraps text in `{"actions": [], "done": False, "reasoning": "..."}`, silently masking the failure and losing the model's actual intent. |
| 2 | CDP connection drops | **HIGH** | `playwright_browser.py` | When connected via CDP to Brave, if the browser crashes or the connection drops, `PlaywrightBrowser` has no reconnection logic. The `is_alive()` check detects the failure but the orchestrator only logs and exits. Contrast with legacy `Orchestrator` which has crash recovery (re-launch and restore URL). |
| 3 | 500ms DOM settle delay | **MEDIUM** | `playwright_browser.py` | After navigation actions (`click`, `navigate`, `open`), `execute_batch()` waits for `networkidle` then adds a hardcoded `page.wait_for_timeout(500)` delay. This is a blind guess -- some SPAs need more time to render, others need none. Can cause actions on stale DOM elements or unnecessary latency. |
| 4 | Dual code paths | **MEDIUM** | `fast_orchestrator.py` + `orchestrator.py` | Two complete orchestrators with duplicated logic: same-URL detection, auto-fill fallback, verification step, signal handling, prompt construction. Bug fixes in one are not automatically ported to the other. The `--fast` flag toggles between them but they are not feature-parity (e.g., legacy has `_validate_actions()`, fast does not). |
| 5 | No concurrent automation | **MEDIUM** | `playwright_browser.py` | PlaywrightBrowser uses the synchronous Playwright API (`sync_playwright`). Only one action can execute at a time. No support for parallel tab management, concurrent element interactions, or async operation batching. The `execute_batch()` method runs actions sequentially with DOM stability waits between each. |
| 6 | Missing MCP server mode | **LOW** | Roadmap | Listed as a roadmap item but not implemented. Would expose browser automation as an MCP server for integration with AI agents (Claude, Cursor, etc.). Currently requires CLI or programmatic Python import. |
| 7 | Missing WebSocket live preview | **LOW** | Roadmap | No real-time feedback channel for monitoring automation progress. Users must watch CLI output. A WebSocket would enable live screenshot streaming, action logging, and remote monitoring dashboards. |
| 8 | Hardcoded screenshot path | **LOW** | `fast_orchestrator.py`, `orchestrator.py` | Both orchestrators use `SCREENSHOT_PATH = Path("/tmp/vision-browser-screenshot.png")` as a module-level constant. This is not configurable, creates a race condition if two instances run concurrently, and fails on systems where `/tmp` is not writable. |
| 9 | No differential screenshots | **LOW** | Roadmap | Every turn captures a full-page screenshot regardless of what changed on the page. Differential (changed regions only) would reduce API payload size, lower costs, and speed up the vision analysis step. |
| 10 | Silent action failures in batch | **LOW** | `playwright_browser.py` | `execute_batch()` catches all exceptions per-action and continues, returning only a success count. Individual failures are logged at DEBUG level but not surfaced to the caller or the vision model, which may continue operating under the assumption all actions succeeded. |
| 11 | inject.js brittle badge positioning | **LOW** | `inject.js` | Badge elements use `position: absolute` with `getBoundingClientRect()` + scroll offsets. Badges can misalign on pages with CSS transforms, iframes, or dynamic layout shifts. No MutationObserver is installed despite the README claiming "MutationObserver auto-re-badges on DOM changes" -- this is a documentation inaccuracy. |
| 12 | No persistent session/cookie management | **LOW** | Roadmap | `BrowserConfig.session_name` exists but is only used by the legacy `AgentBrowser` (via `--session-name` flag). `PlaywrightBrowser` has no session/cookie persistence -- every launch starts fresh. Listed as incomplete in the roadmap. |

## Severity Legend

| Level | Meaning |
|-------|---------|
| **HIGH** | Data loss, security risk, or complete feature failure under common conditions |
| **MEDIUM** | Degraded reliability, duplicated effort, or incorrect assumptions that affect a subset of users |
| **LOW** | Missing features, minor robustness issues, or documentation inaccuracies |

## Risk Matrix

```
Impact
  ^
  |  [2] CDP drops       [1] NIM prose
  |                        [3] 500ms delay
  |  [4] Dual paths      [5] No concurrent
  |                        [8] Hardcoded path
  |  [6] MCP missing     [10] Silent failures
  |  [7] WebSocket       [11] Badge positioning
  |  [12] No sessions    [9] No diff screenshots
  |
  +------------------------------------------> Likelihood
     Rare    Occasional    Common    Frequent
```

## Recommended Priority Order

1. **NIM prose responses** -- Add native JSON enforcement or switch to a model with structured output support
2. **CDP connection drops** -- Add reconnection logic to `PlaywrightBrowser` matching legacy `Orchestrator` recovery
3. **Dual code paths** -- Consolidate into single orchestrator with pluggable browser backend
4. **500ms DOM settle delay** -- Replace with explicit waiter (e.g., `waitForSelector` on expected elements)
5. **No concurrent automation** -- Consider async Playwright for parallel tab management
6-12. Address as roadmap items are prioritized
