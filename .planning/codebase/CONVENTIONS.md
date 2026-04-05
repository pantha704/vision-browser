# CONVENTIONS.md -- Code Conventions and Patterns

## Python Type Hints

- **Python 3.14** type hints throughout the codebase
- Uses `from __future__ import annotations` in all modules (enables PEP 604 `X | Y` union syntax at parse time)
- Optional types use `X | None` syntax (not `Optional[X]`)
- Generic collections use built-in types: `list[str]`, `dict[int, str]` (not `List[str]`, `Dict[int, str]`)
- Private attributes prefixed with underscore: `_playwright`, `_badge_map`, `_shutdown_requested`

```python
def run(self, task: str, url: str | None = None) -> None:
def execute_batch(self, actions: list[dict]) -> int:
def _resolve_ref(self, ref: str | int) -> str:
```

## Pydantic Config Models

All configuration uses **Pydantic v2** `BaseModel` with:

- **Field constraints** via `Field()` with `ge`, `le` validators:
  ```python
  timeout_ms: int = Field(default=30000, ge=5000, le=120000)
  max_turns: int = Field(default=20, ge=1, le=100)
  ```
- **Custom validators** via `@field_validator`:
  ```python
  @field_validator("viewport")
  @classmethod
  def validate_viewport(cls, v: tuple[int, int]) -> tuple[int, int]:
  ```
- **Computed properties** for secrets (env var loading):
  ```python
  @property
  def nim_api_key(self) -> str:
      key = os.environ.get("NVIDIA_API_KEY", "")
      if not key:
          raise ConfigError("NVIDIA_API_KEY not set...")
      return key
  ```
- **YAML loading** via classmethod: `AppConfig.from_yaml(path)`
- **Default factories** for nested models: `Field(default_factory=VisionConfig)`

## Custom Exception Hierarchy

All exceptions inherit from `VisionBrowserError`:

```
VisionBrowserError (base)
├── ConfigError              # Configuration/validation failures
├── VisionAPIError           # Vision model API errors
│   └── RateLimitError       # HTTP 429 rate limit
├── BrowserError             # Browser subprocess errors
│   └── BrowserNotInstalledError  # agent-browser not on PATH
├── ActionExecutionError     # Action execution failures
└── TimeoutError             # Operation timeouts
```

**Pattern:** Exceptions include context in message, use `from e` for exception chaining.

## Rich Console Output

- Single `Console()` instance per module: `console = Console()`
- **Panels** for task display: `Panel(f"[bold green]Task:[/bold green] {task}", title="Vision Browser")`
- **Color-coded status:**
  - `[bold green]` -- success/completion
  - `[bold cyan]` -- turn progress
  - `[bold blue]` -- mode indicators
  - `[yellow]` -- warnings/fallbacks
  - `[red]` -- errors
  - `[dim]` -- secondary/reasoning text
- **Emoji indicators status:** screenshot, vision, execute, success, error, warning

## Logging

- **Dual output:** structured JSON to file + human-readable to console
- **Log file:** `~/.local/share/vision-browser/logs/vision-browser-{YYYYMMDD}.log`
- **Rotation:** `RotatingFileHandler` -- 10MB max, 5 backups
- **Console format:** `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- **File format:** JSON structured: `{"timestamp": ..., "level": ..., "logger": ..., "message": ...}`
- **Verbosity:** `--verbose` flag switches from INFO to DEBUG

## Naming Conventions

| Element | Convention | Examples |
|---------|-----------|----------|
| Modules | `snake_case.py` | `fast_orchestrator.py`, `playwright_browser.py` |
| Classes | `PascalCase` | `FastOrchestrator`, `PlaywrightBrowser`, `VisionClient` |
| Functions/Methods | `snake_case` | `execute_batch()`, `_inject_badges()`, `_resolve_ref()` |
| Private Methods | `_snake_case` | `_connect()`, `_apply_rate_limit()`, `_build_element_list()` |
| Constants | `UPPER_SNAKE_CASE` | `SCREENSHOT_PATH`, `_ALLOWED_KEYS`, `_NAV_TIMEOUT` |
| Variables | `snake_case` | `badge_num`, `consecutive_failures`, `element_list` |

## Code Structure Patterns

- **Match statements** for action dispatch (Python 3.10+):
  ```python
  match act:
      case "click":
          self.click(element)
      case "fill" | "type":
          self.fill(element, action.get("text", ""))
      case _:
          logger.warning(f"Unknown action: {act}")
  ```
- **Context managers** for browser lifecycle (try/finally cleanup)
- **Signal handlers** for graceful shutdown (SIGINT, SIGTERM)
- **f-strings** for all string formatting
- **Path objects** (`pathlib.Path`) for file paths

## Security Patterns

- URL validation: `url.startswith(("http://", "https://"))` -- blocks `file://`, `javascript:`, etc.
- Text length limits: 5000 chars max for fill/type actions
- Keyboard allowlists: `frozenset` of permitted keys
- No shell injection: subprocess calls use list form `["xdotool", "type", "--delay", str(d), "--", text]`
- API keys from environment only -- never in config files

## JavaScript Conventions (inject.js)

- **IIFE pattern** -- `(function(){...})()` for Playwright `page.evaluate()` compatibility
- **CSS injection** -- inline styles with `!important` and high z-index
- **Selector generation** -- priority: `#id` -> `[name]` -> `[aria-label]` -> `[placeholder]` -> `[data-testid]` -> marker attribute
- **Visibility filtering** -- skips elements with `offsetWidth === 0 || offsetHeight === 0`
- **Text truncation** -- element text limited to 100 chars in a11y info
- **A11y tree depth limit** -- first 200 lines only
