---
name: tests
description: "Skill for the Tests area of vision-browser. 296 symbols across 29 files."
---

# Tests

296 symbols | 29 files | Cohesion: 80%

## When to Use

- Working with code in `tests/`
- Understanding how test_nim_empty_response, test_init_with_defaults, test_init_with_orchestrator_config work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/test_vision_and_desktop.py` | test_init_with_defaults, test_init_with_orchestrator_config, test_nim_analyze_success, test_nim_analyze_timeout, test_nim_analyze_rate_limit (+29) |
| `tests/test_core.py` | test_nim_api_key_from_env, test_nim_api_key_missing, test_viewport_validation, test_viewport_upper_validation, test_direct_json (+25) |
| `tests/test_milestone2.py` | _run_async, test_list_tools, test_call_unknown_tool, test_call_tool_no_orchestrator, test_call_navigate (+16) |
| `tests/test_session_and_diff.py` | test_init_creates_dir, test_init_with_default_dir, test_save_session, test_restore_session_success, test_restore_session_not_found (+16) |
| `tests/test_fast_orchestrator_and_cli.py` | test_main_argparse_task_required, test_main_config_file_not_found_uses_defaults, test_main_config_error_exits, test_main_agent_browser_missing, test_main_config_override_brave (+14) |
| `tests/test_mcp_server_hardening.py` | _run_async, test_health_returns_ok_when_connected, test_health_returns_error_when_disconnected, test_health_lists_all_other_tools, test_tool_error_returns_structured_error (+12) |
| `tests/test_model_json_compliance.py` | test_valid_json_passes, test_markdown_wrapped_json_passes, test_empty_string_raises, test_prose_text_raises, test_partial_json_raises (+11) |
| `tests/test_playwright.py` | test_create_browser, test_navigate_to_page, test_screenshot_creates_file, test_badge_injection, test_click_method (+7) |
| `tests/test_vision_client_mocks.py` | test_nim_empty_response, test_nim_partial_json_response, test_nim_markdown_response_parsed, test_nim_prose_response_fallback, test_nim_success_response_is_valid_json (+6) |
| `src/vision_browser/fast_orchestrator.py` | __init__, _register_signals, FastOrchestrator, _cleanup_diffs, get_diff_report (+6) |

## Entry Points

Start here when exploring this area:

- **`test_nim_empty_response`** (Function) — `tests/test_vision_client_mocks.py:52`
- **`test_init_with_defaults`** (Function) — `tests/test_vision_and_desktop.py:41`
- **`test_init_with_orchestrator_config`** (Function) — `tests/test_vision_and_desktop.py:48`
- **`test_nim_analyze_success`** (Function) — `tests/test_vision_and_desktop.py:64`
- **`test_nim_analyze_timeout`** (Function) — `tests/test_vision_and_desktop.py:80`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `VisionClient` | Class | `src/vision_browser/vision.py` | 24 |
| `VisionAPIError` | Class | `src/vision_browser/exceptions.py` | 13 |
| `RateLimitError` | Class | `src/vision_browser/exceptions.py` | 29 |
| `VisionConfig` | Class | `src/vision_browser/config.py` | 10 |
| `MCPServer` | Class | `src/vision_browser/mcp_server.py` | 113 |
| `PlaywrightBrowser` | Class | `src/vision_browser/playwright_browser.py` | 40 |
| `BrowserConfig` | Class | `src/vision_browser/config.py` | 35 |
| `SessionManager` | Class | `src/vision_browser/session.py` | 17 |
| `ScreenshotManager` | Class | `src/vision_browser/screenshot_manager.py` | 18 |
| `DifferentialScreenshot` | Class | `src/vision_browser/diff_screenshot.py` | 11 |
| `Orchestrator` | Class | `src/vision_browser/orchestrator.py` | 90 |
| `JsonFormatter` | Class | `src/vision_browser/cli.py` | 74 |
| `FastOrchestrator` | Class | `src/vision_browser/fast_orchestrator.py` | 80 |
| `AppConfig` | Class | `src/vision_browser/config.py` | 78 |
| `SessionPool` | Class | `src/vision_browser/session_pool.py` | 35 |
| `ModelResponseError` | Class | `src/vision_browser/exceptions.py` | 37 |
| `OrchestratorConfig` | Class | `src/vision_browser/config.py` | 63 |
| `DesktopConfig` | Class | `src/vision_browser/config.py` | 56 |
| `MultiBrowserManager` | Class | `src/vision_browser/multi_browser.py` | 24 |
| `test_nim_empty_response` | Function | `tests/test_vision_client_mocks.py` | 52 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run → List_screenshots` | cross_community | 5 |
| `Run → _encode_image` | cross_community | 5 |
| `Run → TimeoutError` | cross_community | 5 |
| `_run_desktop → VisionAPIError` | cross_community | 5 |
| `_verify_completion → VisionAPIError` | cross_community | 5 |
| `Run → Title` | cross_community | 4 |
| `Run → _apply_rate_limit` | cross_community | 4 |
| `Run → _build_stricter_prompt` | cross_community | 4 |
| `Run → ActionExecutionError` | cross_community | 4 |
| `Execute_batch → ActionExecutionError` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Vision_browser | 31 calls |

## How to Explore

1. `gitnexus_context({name: "test_nim_empty_response"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
