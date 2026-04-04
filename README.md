# Vision Browser

Fast vision-driven browser and desktop automation using **NVIDIA NIM Llama 3.2 90B Vision** + **agent-browser**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Fast Orchestrator (Playwright)              │
│                                                              │
│  1. Playwright: Connect via CDP to existing Brave browser    │
│     → Persistent connection, no subprocess overhead           │
│                                                              │
│  2. DOM: Inject numbered badges on every interactive element │
│     → Extract CSS selectors + a11y info via JS injection     │
│     → ~200ms (vs ~15s with agent-browser CLI)                │
│                                                              │
│  3. Vision: Send annotated screenshot + element list         │
│     → NVIDIA NIM Llama 3.2 90B Vision                        │
│     → DOM validates all refs (no hallucination)              │
│                                                              │
│  4. Execute: Playwright direct API calls                     │
│     → click(), fill(), press() — no subprocess spawning      │
│     → ~50ms per action (vs ~20s per action)                  │
│                                                              │
│  Speed: ~2-5s per round (vs 30-60s old CLI approach)        │
│  Accuracy: 80-95% (DOM-validated refs)                      │
│                                                              │
│  Legacy: agent-browser CLI orchestrator still available      │
│  Usage: --fast flag enables new Playwright mode              │
└─────────────────────────────────────────────────────────────┘
```

## Speed: ~2-5s per round (vs 30-60s for CLI-based approach)

- **No mouse movement** — DOM-level clicks via element refs
- **NVIDIA NIM** — fast Llama 3.2 90B Vision inference
- **Batched actions** — multiple actions per API call
- **Compact element list** — only top 30 relevant elements

## Prerequisites

- **NVIDIA API key** — get one at https://build.nvidia.com
- **agent-browser** — `npm i -g agent-browser && agent-browser install`
- **Python 3.10+**

## Installation

```bash
cd ~/Desktop/projects/vision-browser
uv sync

# Set your NVIDIA API key
export NVIDIA_API_KEY="nvapi-..."

# Optional: Groq fallback (if you have vision model access)
export GROQ_API_KEY="gsk_..."
```

## Usage

### Fast Mode (Playwright + CDP — recommended)

```bash
# Start Brave with CDP (run once per session):
brave-browser --remote-debugging-port=9222 --no-sandbox &

# Run with --fast flag (Playwright-based, ~2-5s per turn):
uv run vision-browser "Search for 'Python vision libraries'" --url https://google.com --brave --fast

# Without CDP (launches separate headless Chrome):
uv run vision-browser "Search for 'Python vision libraries'" --url https://duckduckgo.com --fast
```

### Legacy Mode (agent-browser CLI)

```bash
# Default mode (no --fast flag, uses agent-browser CLI):
uv run vision-browser "Search for 'Python vision libraries'" --url https://google.com --brave
```

### Desktop Mode

```bash
# For non-browser apps (uses scrot + xdotool)
uv run vision-browser "Open the terminal" --desktop
```

### Programmatic Usage

```python
from vision_browser import Orchestrator, AppConfig

cfg = AppConfig()
orchestrator = Orchestrator(cfg)
orchestrator.run(
    "Find the latest news about AI",
    url="https://news.ycombinator.com",
)
```

## Configuration

Edit `config.yaml` or create `~/.config/vision-browser/config.yaml`:

```yaml
vision:
  provider: "nim"
  nim_function_id: "24e0c62b-f7d0-44ba-8012-012c2a1aaf31"
  nim_max_tokens: 1024
  fallback_provider: "groq"

browser:
  annotate: true
  viewport: [1280, 720]
  timeout_ms: 30000

orchestrator:
  max_turns: 20
  max_prompt_elements: 30
  retry_attempts: 3
  retry_backoff_base: 1.0
  rate_limit_delay: 0.5
```

**API keys are loaded from environment variables only** (`NVIDIA_API_KEY`, `GROQ_API_KEY`). Never commit them to version control.

## Security

- API keys via environment variables only
- URL validation (http/https only)
- Keyboard input allowlist
- Text length limits on fill actions
- No shell injection in subprocess calls

## Testing

```bash
uv run pytest tests/ -v
```

## Roadmap

- [x] Core orchestrator loop
- [x] NIM Vision integration
- [x] agent-browser wrapper with ANSI parsing
- [x] Desktop fallback (xdotool)
- [x] Retry with exponential backoff
- [x] Rate limiting
- [x] Input validation (URLs, keys, text)
- [x] Pydantic config models
- [x] Custom exception classes
- [x] Graceful shutdown (signal handlers)
- [x] Browser crash recovery
- [x] Task verification step
- [x] 22 unit tests
- [x] Brave CDP integration (authenticated sessions, no CAPTCHAs)
- [x] Descriptive element list with roles (combobox vs link)
- [x] Same-URL loop detection + auto-fill fallback
- [x] JSON retry loop for model compliance
- [ ] Differential screenshots (changed regions only)
- [ ] MCP server mode
- [ ] WebSocket live preview
