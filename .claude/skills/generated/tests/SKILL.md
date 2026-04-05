---
name: tests
description: "Skill for the Tests area of vision-browser. 300 symbols across 29 files."
---

# Tests

300 symbols | 29 files | Cohesion: 85%

## When to Use

- Working with code in `tests/`
- Understanding how test_init_with_config, test_init_registers_signals, test_empty_legend work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/test_vision_and_desktop.py` | test_init_with_defaults, test_init_with_orchestrator_config, test_nim_analyze_success, test_nim_analyze_timeout, test_nim_analyze_http_error (+29) |
| `tests/test_core.py` | test_defaults, test_nim_api_key_from_env, test_nim_api_key_missing, test_viewport_validation, test_viewport_upper_validation (+25) |
| `tests/test_milestone2.py` | _run_async, test_list_tools, test_call_unknown_tool, test_call_tool_no_orchestrator, test_call_navigate (+16) |
| `tests/test_session_and_diff.py` | test_init_creates_dir, test_init_with_default_dir, test_save_session, test_restore_session_success, test_restore_session_not_found (+16) |
| `tests/test_fast_orchestrator_and_cli.py` | test_init_with_config, test_init_registers_signals, test_empty_legend, test_legend_within_max, test_legend_exceeds_max (+15) |
| `tests/test_mcp_server_hardening.py` | _run_async, test_health_returns_ok_when_connected, test_health_returns_error_when_disconnected, test_health_lists_all_other_tools, test_tool_error_returns_structured_error (+12) |
| `tests/test_model_json_compliance.py` | test_valid_json_passes, test_markdown_wrapped_json_passes, test_empty_string_raises, test_prose_text_raises, test_partial_json_raises (+11) |
| `src/vision_browser/fast_orchestrator.py` | FastOrchestrator, _run_loop, _build_element_list, _verify_completion, _log_diff (+7) |
| `tests/test_playwright.py` | test_create_browser, test_navigate_to_page, test_screenshot_creates_file, test_badge_injection, test_click_method (+7) |
| `tests/test_vision_client_mocks.py` | test_nim_empty_response, test_nim_partial_json_response, test_nim_markdown_response_parsed, test_nim_prose_response_fallback, test_nim_success_response_is_valid_json (+6) |

## Entry Points

Start here when exploring this area:

- **`test_init_with_config`** (Function) — `tests/test_fast_orchestrator_and_cli.py:22`
- **`test_init_registers_signals`** (Function) — `tests/test_fast_orchestrator_and_cli.py:33`
- **`test_empty_legend`** (Function) — `tests/test_fast_orchestrator_and_cli.py:46`
- **`test_legend_within_max`** (Function) — `tests/test_fast_orchestrator_and_cli.py:56`
- **`test_legend_exceeds_max`** (Function) — `tests/test_fast_orchestrator_and_cli.py:69`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `FastOrchestrator` | Class | `src/vision_browser/fast_orchestrator.py` | 82 |
| `AppConfig` | Class | `src/vision_browser/config.py` | 78 |
| `VisionClient` | Class | `src/vision_browser/vision.py` | 25 |
| `RateLimitError` | Class | `src/vision_browser/exceptions.py` | 29 |
| `VisionConfig` | Class | `src/vision_browser/config.py` | 10 |
| `MCPServer` | Class | `src/vision_browser/mcp_server.py` | 115 |
| `PlaywrightBrowser` | Class | `src/vision_browser/playwright_browser.py` | 44 |
| `BrowserConfig` | Class | `src/vision_browser/config.py` | 35 |
| `SessionManager` | Class | `src/vision_browser/session.py` | 17 |
| `ScreenshotManager` | Class | `src/vision_browser/screenshot_manager.py` | 18 |
| `DifferentialScreenshot` | Class | `src/vision_browser/diff_screenshot.py` | 11 |
| `Orchestrator` | Class | `src/vision_browser/orchestrator.py` | 91 |
| `JsonFormatter` | Class | `src/vision_browser/cli.py` | 75 |
| `SessionPool` | Class | `src/vision_browser/session_pool.py` | 35 |
| `VisionAPIError` | Class | `src/vision_browser/exceptions.py` | 13 |
| `ModelResponseError` | Class | `src/vision_browser/exceptions.py` | 37 |
| `OrchestratorConfig` | Class | `src/vision_browser/config.py` | 63 |
| `DesktopConfig` | Class | `src/vision_browser/config.py` | 56 |
| `MultiBrowserManager` | Class | `src/vision_browser/multi_browser.py` | 24 |
| `test_init_with_config` | Function | `tests/test_fast_orchestrator_and_cli.py` | 22 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run → List_screenshots` | cross_community | 5 |
| `Run → _encode_image` | cross_community | 5 |
| `Run → TimeoutError` | cross_community | 5 |
| `_run_desktop → VisionAPIError` | cross_community | 5 |
| `_verify_completion → VisionAPIError` | cross_community | 5 |
| `_analyze_with_json_retry → VisionAPIError` | cross_community | 5 |
| `Run → Title` | cross_community | 4 |
| `Run → _apply_rate_limit` | cross_community | 4 |
| `Run → _build_stricter_prompt` | cross_community | 4 |
| `Run → ActionExecutionError` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Vision_browser | 29 calls |

## How to Explore

1. `gitnexus_context({name: "test_init_with_config"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
