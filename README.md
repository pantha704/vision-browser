# Vision Browser

**Fast browser automation** using **Playwright + AI**. Search, click, fill forms, and extract data from any website using natural language.

```bash
# ⚡ Locator mode (fastest — 15s for search + click)
uv run vision-browser "Search for 'Python tutorial' on YouTube and click the first video" --url https://youtube.com --brave --locator

# 🖼️ Fast mode (screenshot + vision model)
uv run vision-browser "Search for 'Python libraries'" --url https://google.com --brave --fast

# 🔌 MCP server (for AI assistants)
uv run vision-browser-mcp
```

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/YOUR_USERNAME/vision-browser.git
cd vision-browser
uv sync
uv run playwright install chromium
```

### 2. Set API Key

```bash
export NVIDIA_API_KEY="nvapi-..."
```

Get a key at [build.nvidia.com](https://build.nvidia.com) (free tier available).

### 3. Start Brave with Remote Debugging

```bash
brave-browser --remote-debugging-port=9222 --no-sandbox &
```

### 4. Run

```bash
uv run vision-browser "Search for 'machine learning' on YouTube" --url https://youtube.com --brave --locator
```

---

## Three Modes

| Mode | Flag | Speed | Best For |
|------|------|-------|----------|
| **🎯 Locator** | `--locator` | ⚡⚡⚡ ~3-5s/turn | Search, navigation, form filling |
| **🖼️ Fast** | `--fast` | ⚡⚡ ~5-10s/turn | Visual tasks (click specific image) |
| **🐢 Legacy** | (none) | ⚡ ~30-60s/turn | Desktop apps, non-browser targets |

### 🎯 Locator Mode (Recommended)

Uses Playwright's semantic locators — **no screenshots needed for element finding**. Extracts interactive elements instantly via JavaScript and sends only text to the AI model.

```bash
# Search and click (completes in ~15s)
uv run vision-browser "Search for 'Python tutorial' on YouTube and click the first video" --url https://youtube.com --brave --locator

# Fill a form
uv run vision-browser "Fill the contact form with name John, email john@example.com, message Hello" --url https://example.com/contact --brave --locator
```

**How it works:**
```
1. JS querySelectorAll → Get all interactive elements with CSS selectors (~200ms)
2. Build numbered list: [1] role=searchbox "Search" → input#search
3. Text-only AI → Plans actions: {"actions": [{"action": "fill", "element": 1, "text": "query"}]}
4. Playwright → Executes directly via CSS selectors (~50ms/action)
5. Feedback → Reports success/failure back to AI next turn
6. Completion → Detects URL changes (no unreliable model-based verification)
```

### 🖼️ Fast Mode (Screenshot + Vision)

Takes screenshots, injects numbered badges on elements, and sends annotated images to a Vision model. Use when you need visual understanding (e.g., "click the thumbnail showing a sunset").

```bash
uv run vision-browser "Find and click the video with over 1M views" --url https://youtube.com --brave --fast
```

### 🔌 MCP Server

Expose browser automation as an MCP server for AI assistants (Claude, Cursor, VS Code).

```bash
# In your MCP client config (e.g., Claude Desktop):
{
  "mcpServers": {
    "vision-browser": {
      "command": "uv",
      "args": ["run", "vision-browser-mcp"],
      "cwd": "/path/to/vision-browser",
      "env": {
        "NVIDIA_API_KEY": "nvapi-..."
      }
    }
  }
}
```

**Available MCP tools:**
- `vision_browser_navigate(url)` — Go to a URL
- `vision_browser_get_elements()` — See interactive elements
- `vision_browser_click(element)` — Click by index
- `vision_browser_fill(element, text)` — Fill input by index
- `vision_browser_press(key)` — Press keyboard key
- `vision_browser_scroll(direction, amount)` — Scroll page
- `vision_browser_screenshot(full_page)` — Take screenshot
- `vision_browser_execute(task)` — High-level natural language task

---

## Architecture

### Locator Mode (Default Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                  Locator Orchestrator                        │
│                                                              │
│  1. Playwright → Connect via CDP to existing Brave browser  │
│     → Persistent connection, zero subprocess overhead         │
│                                                              │
│  2. JS Eval → Get interactive elements with CSS selectors   │
│     → querySelectorAll for all interactive elements (~200ms) │
│     → Sorted by visual position (top-to-bottom)              │
│     → Each element gets a unique CSS selector                │
│                                                              │
│  3. Text AI → Send page state (no image) to NIM model       │
│     → URL, title, numbered element list                      │
│     → ~3-5s for text-only inference (no image encoding)      │
│     → Returns: {"actions": [{"action": "fill", "element": 1, │
│         "text": "query"}], "done": false}                    │
│                                                              │
│  4. Execute → Playwright direct API calls via CSS selectors  │
│     → page.click(selector), page.fill(selector, text)        │
│     → ~50ms per action                                       │
│     → Reports success/failure back to AI next turn           │
│                                                              │
│  5. Completion → URL-based state detection                   │
│     → Tracks /watch URLs (YouTube redirects back to /)       │
│     → Checks search results loaded (/results)                │
│     → No unreliable model-based verification                 │
│                                                              │
│  Speed: ~3-5s per turn                                       │
│  Accuracy: 80-95% (CSS selector precision)                   │
└─────────────────────────────────────────────────────────────┘
```

### Fast Mode (Screenshot + Vision)

```
┌─────────────────────────────────────────────────────────────┐
│              Vision Browser (Fast Orchestrator)              │
│                                                              │
│  1. Screenshot → Capture current page (~200ms)              │
│  2. Badges → Inject numbered overlays on elements (~200ms)  │
│  3. Vision AI → Send annotated screenshot to NIM model      │
│     → Image encoding + API call (~5-10s)                     │
│  4. Execute → Playwright direct API calls (~50ms/action)     │
│  5. Verify → Check completion via URL state                  │
│                                                              │
│  Speed: ~5-10s per turn                                      │
│  Use when: Visual understanding needed                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Command-Line Options

| Flag | Description |
|------|-------------|
| `--url`, `-u` | Starting URL |
| `--brave` | Connect to running Brave browser (port 9222) |
| `--locator` | **Use locator-based mode (recommended, fastest)** |
| `--fast` | Use screenshot + vision model orchestrator |
| `--desktop`, `-d` | Desktop mode (scrot + xdotool for non-browser apps) |
| `--config`, `-c` | Path to custom config.yaml |
| `--verbose`, `-v` | Enable debug logging |
| `--session` | Session name for persistent cookies/auth |

---

## Configuration

Create `~/.config/vision-browser/config.yaml`:

```yaml
vision:
  provider: "nim"
  nim_function_id: "24e0c62b-f7d0-44ba-8012-012c2a1aaf31"
  nim_max_tokens: 1024

browser:
  viewport: [1280, 720]
  timeout_ms: 30000
  session_name: ""          # Set to persist cookies between runs
  cdp_url: "http://localhost:9222"  # Connect to running Brave/Chrome

orchestrator:
  max_turns: 20
  max_prompt_elements: 40
  retry_attempts: 3
  retry_backoff_base: 1.0
  rate_limit_delay: 0.5
```

**API keys are loaded from environment variables only** (`NVIDIA_API_KEY`). Never commit them to version control.

---

## Performance Comparison

| Metric | Legacy (agent-browser) | Fast (screenshot) | Locator (recommended) |
|--------|----------------------|-------------------|----------------------|
| **Speed** | 30-60s/turn | 5-10s/turn | **3-5s/turn** |
| **YouTube search** | ❌ Too slow | ⚠️ Model can't parse JSON | ✅ Works reliably |
| **Search + click** | ❌ Stuck loops | ⚠️ 25+ turns | ✅ **~15s, 3 turns** |
| **Element finding** | ~15s subprocess | ~200ms badge inject | **~200ms JS eval** |
| **Vision API** | Required | Required (image) | **Text-only (faster)** |
| **Screenshot** | ~5s | Required | **Not needed** |

---

## Security

- API keys via environment variables only (never in config files)
- URL validation (http/https only)
- Keyboard input allowlist (prevents arbitrary key injection)
- Text length limits on fill actions (max 5000 chars)
- No shell injection in subprocess calls
- Config validation via Pydantic models

---

## Project Structure

```
vision-browser/
├── pyproject.toml              # Project config + dependencies
├── config.yaml                 # Configuration (no secrets)
├── README.md                   # This file
├── src/vision_browser/
│   ├── __init__.py             # Package exports
│   ├── cli.py                  # CLI entry point
│   ├── config.py               # Pydantic config models
│   ├── exceptions.py           # Custom exceptions
│   ├── vision.py               # Vision model clients (NIM)
│   ├── playwright_browser.py   # Playwright browser controller + locators
│   ├── locator_orchestrator.py # ⭐ Locator-based orchestrator (recommended)
│   ├── fast_orchestrator.py    # Screenshot + vision orchestrator
│   ├── orchestrator.py         # Legacy orchestrator (agent-browser)
│   ├── mcp_server_v2.py        # ⭐ MCP server for AI assistants
│   ├── circuit_breaker.py      # API failure circuit breaker
│   ├── error_tracker.py        # Comprehensive error tracking
│   ├── diff_screenshot.py      # Differential screenshot detection
│   ├── screenshot_manager.py   # Screenshot lifecycle management
│   ├── session.py              # Persistent session/cookie management
│   └── inject.js               # Badge overlay + a11y extraction
└── tests/
    ├── test_core.py            # JSON extraction, config, validation
    ├── test_circuit_breaker.py # Circuit breaker tests
    └── test_playwright.py      # Playwright browser tests
```

---

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=vision_browser

# Lint + format check
uv run ruff check src/vision_browser/
uv run ruff format src/vision_browser/
```

**240 tests passing** — covering JSON extraction, config validation, URL sanitization, element refs, circuit breaker, Playwright browser operations, and more.

---

## Roadmap

### v0.7 Production Readiness
- [x] CDP disconnection fix (signal handler + close())
- [x] Navigation timeout fix (networkidle → load for SPAs)
- [x] Scroll lag fix (documentElement.scrollTo)
- [x] Same-action loop detection
- [x] Error tracking (ErrorTracker class)
- [x] Circuit breaker for Vision API
- [x] Differential screenshot detection
- [x] **Locator mode (Playwright semantic locators)**
- [x] **MCP server for AI assistants**
- [ ] Rate limit persistence across runs
- [ ] MCP server integration tests
- [ ] MultiBrowserManager integration

### v0.8 Next
- [ ] Versioned element references (prevent stale selectors)
- [ ] History compression (summarize past turns)
- [ ] Prompt prefix caching (reduce NIM cost)
- [ ] Bulk action parallelization
- [ ] WebSocket live preview

---

## License

MIT
