# TESTING.md -- Testing Strategy and Coverage

## Framework

| Tool | Version | Role |
|------|---------|------|
| pytest | >=8.0.0 | Test runner, assertions, fixtures |
| ruff | >=0.4.0 | Linting (not test execution) |

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Core tests only
uv run pytest tests/test_core.py -v

# Playwright tests only
uv run pytest tests/test_playwright.py -v

# Specific test
uv run pytest tests/test_core.py::TestExtractJson::test_direct_json -v
```

## Test Inventory

### test_core.py -- 22 Tests

**TestExtractJson** (7 tests) -- JSON extraction from model output:

| # | Test Method | What It Tests |
|---|------------|---------------|
| 1 | `test_direct_json` | Direct JSON string parsing |
| 2 | `test_markdown_code_block` | JSON inside code blocks |
| 3 | `test_nested_json` | JSON embedded in prose text |
| 4 | `test_deeply_nested_json` | Deeply nested object structures |
| 5 | `test_non_json_text_fallback` | Fallback wrapping for non-JSON text |
| 6 | `test_empty_string` | Empty input handling |
| 7 | `test_multiple_json_objects` | Multiple JSON objects in one response |

**TestConfig** (6 tests) -- Pydantic config validation:

| # | Test Method | What It Tests |
|---|------------|---------------|
| 8 | `test_defaults` | Default config values |
| 9 | `test_viewport_validation` | Minimum viewport enforcement (320x240) |
| 10 | `test_max_turns_validation` | Lower bound on max_turns (>=1) |
| 11 | `test_max_turns_upper_validation` | Upper bound on max_turns (<=100) |
| 12 | `test_nim_api_key_from_env` | NVIDIA_API_KEY env var loading |
| 13 | `test_nim_api_key_missing` | ConfigError when API key absent |

**TestUrlValidation** (5 tests) -- URL safety:

| # | Test Method | What It Tests |
|---|------------|---------------|
| 14 | `test_valid_http` | HTTP URLs accepted |
| 15 | `test_valid_https` | HTTPS URLs with query strings accepted |
| 16 | `test_reject_file_url` | `file://` URLs blocked |
| 17 | `test_reject_javascript_url` | `javascript:` URLs blocked |
| 18 | `test_reject_empty_url` | Empty URLs blocked |

**TestElementRef** (4 tests) -- Element reference helpers:

| # | Test Method | What It Tests |
|---|------------|---------------|
| 19 | `test_int_to_ref` | Integer `5` -> `"@e5"` conversion |
| 20 | `test_string_ref_preserved` | `"@e12"` preserved as-is |
| 21 | `test_string_ref_without_at` | `"e7"` -> `"@e7"` conversion |
| 22 | `test_none_raises` | `None` raises `ActionExecutionError` |

### test_playwright.py -- 12 Tests

**TestPlaywrightBrowser** (10 tests) -- Playwright browser operations:

| # | Test Method | What It Tests |
|---|------------|---------------|
| 1 | `test_create_browser` | Browser launch without CDP |
| 2 | `test_navigate_to_page` | URL navigation + URL/title extraction |
| 3 | `test_screenshot_creates_file` | Screenshot file creation with refs |
| 4 | `test_badge_injection` | Badge injection returns refs + legend |
| 5 | `test_click_method` | Click by badge number |
| 6 | `test_fill_method` | Fill by badge number |
| 7 | `test_get_url_and_title` | URL and title after navigation |
| 8 | `test_execute_batch` | Batch action execution (scroll) |
| 9 | `test_is_alive` | Browser responsiveness check |
| 10 | `test_close` | Clean browser shutdown |

**TestBrowserConfig** (2 tests) -- BrowserConfig validation:

| # | Test Method | What It Tests |
|---|------------|---------------|
| 11 | `test_default_config` | Default values (cdp_url="", annotate=True, timeout_ms=30000) |
| 12 | `test_cdp_config` | Custom CDP URL configuration |

## Test Coverage Gaps

The following components have **no dedicated test coverage**:

- **FastOrchestrator** -- No unit tests for the automation loop, same-URL detection, or auto-fill fallback
- **Orchestrator** (legacy) -- No tests for CLI wrapper loop, crash recovery, or desktop mode
- **VisionClient** -- No mocked API tests for NIM/Groq calls, retry logic, rate limiting, or fallback behavior
- **DesktopController** -- No tests for scrot/xdotool subprocess calls
- **CLI** -- No tests for argument parsing, config loading, or error handling paths
- **inject.js** -- No headless browser tests for badge injection correctness

## Test Characteristics

- **Integration-heavy:** Playwright tests launch real browsers and navigate to `https://example.com`
- **No mocks:** Vision API tests would require mocking `httpx` and `groq` clients (not yet implemented)
- **Environment-dependent:** `test_nim_api_key_from_env` manipulates `os.environ` directly
- **try/finally cleanup:** All Playwright tests use `try/finally` to close browsers even on assertion failure
- **Exception tolerance:** `test_fill_method` catches expected failures on pages with few inputs
