# ARCHITECTURE.md -- System Architecture

## Overview

Vision Browser is a vision-driven browser automation system. A vision model (NVIDIA NIM or Groq) analyzes annotated screenshots and returns JSON action plans, which are executed via either Playwright (fast path) or the `agent-browser` CLI (legacy path).

```
+------------------------------------------------------------------+
|                     Vision Browser (CLI Entry)                    |
|                                                                   |
|  User Task --> CLI --> [ --fast? ] ---+--> FastOrchestrator       |
|                                       |                           |
|                                       +--> Orchestrator (legacy)  |
|                                       |                           |
|                                       +--> DesktopController      |
+------------------------------------------------------------------+
```

## Core Components

### 1. FastOrchestrator (`fast_orchestrator.py`)

The **primary** automation engine. Uses Playwright's persistent CDP connection for speed.

**Responsibilities:**
- Connects to browser via Playwright + CDP (or launches headless Chromium)
- Runs the main automation loop: screenshot -> badge inject -> vision analyze -> execute -> verify
- Handles same-URL loop detection and auto-fill fallback (Google homepage)
- Post-completion verification step (asks model "is task done?")
- Signal handling for graceful shutdown (SIGINT, SIGTERM)

**Flow:**
```
1. PlaywrightBrowser.screenshot() --> saves PNG
2. PlaywrightBrowser._inject_badges() --> numbered overlays + a11y tree
3. VisionClient.analyze() --> NIM (primary) or Groq (fallback) returns JSON
4. PlaywrightBrowser.execute_batch() --> clicks, fills, scrolls via Playwright API
5. _verify_completion() --> re-screenshots and asks model to confirm
```

**Key difference from legacy:** Direct Playwright API calls (~50ms/action) vs subprocess-per-action (~20s/action).

### 2. Orchestrator (`orchestrator.py`)

The **legacy** automation engine. Wraps the `agent-browser` CLI subprocess.

**Responsibilities:**
- Same automation loop as FastOrchestrator but uses `AgentBrowser` (CLI wrapper)
- Supports desktop mode via `DesktopController` (scrot + xdotool)
- Action validation against available element refs (skips hallucinated refs)
- Browser crash recovery (reconnect and restore URL)
- JSON retry logic (if model returns prose, re-prompts with strict schema)
- Same-URL loop detection with auto-fill fallback

**Three sub-modes:**
- `_run_browser()` -- browser automation via `agent-browser` CLI
- `_run_desktop()` -- desktop automation via `scrot` + `xdotool`
- `_analyze_with_json_retry()` -- vision analysis with prose-to-JSON retry

### 3. PlaywrightBrowser (`playwright_browser.py`)

Browser controller using **Playwright's sync API** with persistent CDP connection.

**Capabilities:**
- **CDP connect mode:** Connects to existing Brave/Chrome via `connect_over_cdp()` -- zero subprocess overhead, user's session/cookies preserved
- **Launch mode:** Launches headless Chromium locally with `--no-sandbox`
- Badge injection via `inject.js` -- overlays numbered badges on interactive elements
- A11y tree extraction -- role, label, text, placeholder for each element
- CSS selector generation -- prioritizes `#id`, `[name]`, `[aria-label]`, `[data-testid]`
- Batch action execution -- `execute_batch()` runs multiple actions, handles navigation waits
- URL validation (http/https only)
- Text length limits (5000 chars max for fill)
- Keyboard key allowlist (prevents arbitrary key injection)
- `is_alive()` health check via `page.evaluate("1")`

**Close behavior:** Skips close if connected via CDP (user controls their own browser).

### 4. AgentBrowser (`browser.py`)

Browser controller wrapping the **`agent-browser` CLI** as a subprocess.

**Capabilities:**
- URL navigation via `agent-browser open`
- Annotated screenshots via `agent-browser screenshot --annotate` -- parses legend output into badge->ref mapping
- Interactive element snapshot via `agent-browser snapshot -i`
- Click, fill, type, select, press, scroll via CLI commands
- JavaScript evaluation via temp file + `agent-browser eval`
- Session persistence via `--session-name` flag
- CDP mode via `--cdp` flag

**Key limitation:** Each action spawns a new subprocess (~20s per action), making it 10-30x slower than Playwright.

### 5. VisionClient (`vision.py`)

Unified interface for vision models with retry, rate limiting, and fallback.

**Primary path -- NVIDIA NIM:**
- HTTP POST to `https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{nim_function_id}`
- Sends base64-encoded image + prompt as messages array
- 120s HTTP timeout
- Parses NVCF response format: `data["choices"][0]["message"]["content"]`

**Fallback path -- Groq:**
- Uses `groq.Groq()` Python SDK client
- Supports function calling (when schema provided) for structured JSON output
- Falls back to `json_object` response format when no schema

**Shared behavior:**
- Exponential backoff retry (default 3 attempts, base 1.0s)
- Rate limiting (default 500ms minimum between requests)
- Groq fallback on NIM failure before retrying NIM
- JSON extraction with 4-tier strategy: code blocks -> direct parse -> balanced brace extraction -> text wrapper fallback
- Base64 image encoding

### 6. DesktopController (`desktop.py`)

Fallback for **non-browser desktop automation** using OS-level tools.

**Tools:**
- `scrot` -- full desktop screenshot capture
- `xdotool` -- mouse movement, clicks, keyboard input, scrolling

**Capabilities:**
- Coordinate-based clicking (`xdotool mousemove X Y click 1`)
- Text typing with configurable delay (`xdotool type --delay 20 -- {text}`)
- Key pressing with allowlist validation
- Mouse wheel scrolling (button 4=up, 5=down, capped at 50 scrolls)
- Mouse position querying

## Data Flow

```
User Command
    |
    v
+-----------+     +------------------+     +----------------+
|    CLI    |---->| FastOrchestrator |---->|PlaywrightBrowser|
|  (cli.py) |     |  or Orchestrator |     |  or AgentBrowser|
+-----------+     +--------+---------+     +----------------+
                           |
                    +------+------+
                    v             v
              +----------+  +-------------+
              |VisionClient|  |DesktopCtrl  |
              | (NIM+Groq) |  |(scrot+xdotool)|
              +----------+  +-------------+
```

## Configuration Hierarchy

```
1. Pydantic defaults (code)
2. config.yaml (project root)
3. ~/.config/vision-browser/config.yaml (user override)
4. --config flag (CLI override)
5. Environment variables (API keys only)
```
