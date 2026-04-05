# INTEGRATIONS.md -- External System Integrations

## 1. NVIDIA NIM Vision API

| Aspect | Detail |
|--------|--------|
| **Endpoint** | `POST https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/{nim_function_id}` |
| **Function ID** | `24e0c62b-f7d0-44ba-8012-012c2a1aaf31` (Llama 3.2 90B Vision) |
| **Auth** | `Authorization: Bearer {NVIDIA_API_KEY}` header |
| **Request Format** | Messages array with text + base64 image_url |
| **Response Format** | NVCF standard: `{"choices": [{"message": {"content": "..."}}]}` |
| **Timeout** | 120 seconds (httpx) |
| **Max Tokens** | 1024 (configurable, range 64-4096) |
| **Temperature** | 0.1 (hardcoded) |
| **Schema Enforcement** | Prompt-based -- JSON schema injected into user prompt text (no native JSON mode) |
| **Rate Limiting** | HTTP 429 detection -> `RateLimitError` -> exponential backoff |

**Implementation:** `VisionClient._nim_analyze()` in `src/vision_browser/vision.py`

## 2. Groq Vision API

| Aspect | Detail |
|--------|--------|
| **Client** | `groq.Groq()` Python SDK (>=0.13.0) |
| **Model** | `llama-3.2-11b-vision` (configurable) |
| **Auth** | `GROQ_API_KEY` environment variable (SDK reads automatically) |
| **Max Tokens** | 1024 (configurable, range 64-4096) |
| **Temperature** | 0.1 (hardcoded) |
| **Structured Output** | Two modes: function calling (with schema) or `json_object` response format |
| **Role** | Fallback -- called when NIM fails before retrying NIM |

**Implementation:** `VisionClient._groq_analyze()` in `src/vision_browser/vision.py`

## 3. Brave CDP (Chrome DevTools Protocol)

| Aspect | Detail |
|--------|--------|
| **URL** | `http://localhost:9222` (default `cdp_url` config) |
| **Connection** | Playwright `chromium.connect_over_cdp()` |
| **Browser Launch** | User must start: `brave-browser --remote-debugging-port=9222 --no-sandbox` |
| **Session Persistence** | Uses existing Brave context -- cookies, auth, extensions preserved |
| **Close Behavior** | Skips browser close when CDP connected (user owns the browser) |
| **Fallback** | Launches headless Chromium locally if CDP unavailable |

**Implementation:** `PlaywrightBrowser._connect()` in `src/vision_browser/playwright_browser.py`

## 4. agent-browser CLI

| Aspect | Detail |
|--------|--------|
| **Install** | `npm i -g agent-browser && agent-browser install` |
| **Detection** | `shutil.which("agent-browser")` -- exits with error if not found |
| **Communication** | Subprocess per action -- `subprocess.run()` with timeout |
| **Commands Used** | `open`, `close`, `screenshot`, `snapshot`, `click`, `type`, `select`, `press`, `scroll`, `wait`, `get`, `eval`, `find`, `keyboard` |
| **Timeouts** | Navigation: 60s, Screenshot: 30s, Snapshot: 15s, Default: 30s |
| **Annotation** | `--annotate` flag adds numbered badges; output parsed via regex for badge->ref mapping |
| **Session** | `--session-name` flag for persistent cookies |
| **CDP** | `--cdp {url}` flag for connecting to existing browser |

**Implementation:** `AgentBrowser` class in `src/vision_browser/browser.py`

## 5. scrot (Desktop Screenshots)

| Aspect | Detail |
|--------|--------|
| **Command** | `scrot {path}` |
| **Purpose** | Full desktop screenshot capture (non-browser automation fallback) |
| **Config** | `desktop.screenshot_cmd` (default: `"scrot"`) |
| **Usage** | Called via `subprocess.run()` with `check=True` |

**Implementation:** `DesktopController.screenshot()` in `src/vision_browser/desktop.py`

## 6. xdotool (Desktop Input)

| Aspect | Detail |
|--------|--------|
| **Mouse Click** | `xdotool mousemove {x} {y} click 1` |
| **Text Input** | `xdotool type --delay 20 -- {text}` (20ms delay between chars) |
| **Key Press** | `xdotool key {key}` (allowlist validated) |
| **Scroll** | `xdotool click 4` (up) or `xdotool click 5` (down), capped at 50 iterations |
| **Mouse Position** | `xdotool getmouselocation --shell` (parses X= and Y= from output) |
| **Allowed Keys** | `Return`, `Enter`, `Tab`, `Escape`, `BackSpace`, `Delete`, arrows, `Home`, `End`, `Page_Up`, `Page_Down`, modifier combos |

**Implementation:** `DesktopController` class in `src/vision_browser/desktop.py`

## Integration Dependency Graph

```
+---------------------------------------------+
|              vision-browser                  |
|                                              |
|  FastOrchestrator --> PlaywrightBrowser --> Brave CDP
|                       |                      |
|                       +--> inject.js (in-page)|
|                       |                       |
|  VisionClient --------+--> NVIDIA NIM API     |
|                       |   +--> Groq API (fallback)
|                       |                       |
|  Orchestrator --------+--> AgentBrowser --> agent-browser CLI
|                       |                       |
|                       +--> DesktopController --> scrot
|                       |                         +--> xdotool
|                       |
|  AppConfig -----------+--> config.yaml + env vars
```
