# STRUCTURE.md -- Project File Structure

```
vision-browser/
├── pyproject.toml                          # Project metadata, deps, build config (hatchling)
├── config.yaml                             # Default configuration (no secrets)
├── README.md                               # User-facing documentation
├── uv.lock                                 # Frozen dependency tree (uv)
├── .python-version                         # Python 3.14 pin
├── .gitignore                              # Git ignore patterns
│
├── src/vision_browser/                     # Main package (10 Python modules + 1 JS)
│   ├── __init__.py                         # Public API exports (7 classes + 6 exceptions)
│   ├── cli.py                              # CLI entry point (argparse + rich console)
│   ├── config.py                           # Pydantic models: AppConfig, VisionConfig, BrowserConfig, etc.
│   ├── exceptions.py                       # Custom exception hierarchy (7 classes)
│   ├── vision.py                           # VisionClient -- NIM (primary) + Groq (fallback)
│   ├── playwright_browser.py               # PlaywrightBrowser -- CDP persistent browser control
│   ├── fast_orchestrator.py                # FastOrchestrator -- Playwright-based automation loop
│   ├── orchestrator.py                     # Orchestrator -- legacy agent-browser CLI automation loop
│   ├── browser.py                          # AgentBrowser -- agent-browser CLI subprocess wrapper
│   ├── desktop.py                          # DesktopController -- scrot + xdotool fallback
│   └── inject.js                           # DOM badge injection + a11y tree extraction (IIFE)
│
├── tests/                                  # Test suite (2 files)
│   ├── test_core.py                        # 22 tests: JSON extraction, config, URL validation, element refs
│   └── test_playwright.py                  # 12 tests: PlaywrightBrowser operations, BrowserConfig
│
└── prompts/                                # (Directory exists but contents not analyzed)
```

## Source Module Summary

| Module | Lines (approx) | Key Classes/Functions | Purpose |
|--------|---------------|----------------------|---------|
| `__init__.py` | ~30 | Package exports | Public API surface |
| `cli.py` | ~120 | `main()` | CLI entry, arg parsing, orchestrator routing |
| `config.py` | ~90 | `AppConfig`, `VisionConfig`, `BrowserConfig`, `DesktopConfig`, `OrchestratorConfig` | Pydantic config models with validation |
| `exceptions.py` | ~30 | `VisionBrowserError`, `ConfigError`, `VisionAPIError`, `BrowserError`, `BrowserNotInstalledError`, `ActionExecutionError`, `RateLimitError`, `TimeoutError` | Exception hierarchy |
| `vision.py` | ~200 | `VisionClient` | NIM + Groq API clients with retry/fallback |
| `playwright_browser.py` | ~250 | `PlaywrightBrowser` | Playwright CDP browser controller |
| `fast_orchestrator.py` | ~200 | `FastOrchestrator` | Fast automation loop |
| `orchestrator.py` | ~350 | `Orchestrator` | Legacy automation loop (CLI + desktop) |
| `browser.py` | ~200 | `AgentBrowser`, `_element_to_ref()`, `_validate_url()` | agent-browser CLI wrapper |
| `desktop.py` | ~80 | `DesktopController` | scrot + xdotool desktop control |
| `inject.js` | ~100 | IIFE `(function(){...})()` | Badge overlay + a11y extraction |

## Test File Summary

| File | Test Classes | Test Count | Coverage Area |
|------|-------------|------------|---------------|
| `test_core.py` | `TestExtractJson`, `TestConfig`, `TestUrlValidation`, `TestElementRef` | 22 | JSON parsing, config validation, URL safety, element refs |
| `test_playwright.py` | `TestPlaywrightBrowser`, `TestBrowserConfig` | 12 | Playwright browser CRUD, config defaults |

## Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `pyproject.toml` | TOML | Dependencies, build system, entry points, dev tools |
| `config.yaml` | YAML | Runtime defaults for vision, browser, desktop, orchestrator |
| `.python-version` | Plain text | Python version pin (3.14) |

## Key Entry Points

- **CLI:** `vision_browser.cli:main` (registered as `vision-browser` console script)
- **Programmatic:** `FastOrchestrator(cfg).run(task, url=url)`
- **Tests:** `uv run pytest tests/ -v`
