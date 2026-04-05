---
name: vision-browser
description: "Skill for the Vision_browser area of vision-browser. 106 symbols across 16 files."
---

# Vision_browser

106 symbols | 16 files | Cohesion: 75%

## When to Use

- Working with code in `src/`
- Understanding how test_init_defaults, test_broadcast, test_connect_disconnect work
- Modifying vision_browser-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `src/vision_browser/browser.py` | __init__, _check_installed, _build_open_args, open, screenshot (+18) |
| `src/vision_browser/orchestrator.py` | run, _run_browser, _analyze_with_json_retry, _build_element_list_from_legend, _validate_actions (+5) |
| `tests/test_milestone2.py` | test_init_defaults, test_broadcast, test_connect_disconnect, test_send_screenshot_missing_file, test_send_navigation (+4) |
| `src/vision_browser/websocket_preview.py` | WebSocketPreview, broadcast, send_screenshot, send_navigation, send_action (+4) |
| `src/vision_browser/playwright_browser.py` | screenshot, click, fill, press, scroll (+4) |
| `src/vision_browser/screenshot_manager.py` | list_screenshots, cleanup, _handler, _enforce_retention, __exit__ (+2) |
| `src/vision_browser/mcp_server.py` | _handle_navigate, _handle_screenshot, _handle_click, _handle_fill, _handle_extract (+2) |
| `src/vision_browser/exceptions.py` | VisionBrowserError, ConfigError, BrowserError, BrowserNotInstalledError, ActionExecutionError (+1) |
| `tests/test_vision_and_desktop.py` | test_type_text, test_type_text_empty, test_type_text_too_long, test_type_text_with_delay, test_get_mouse_pos (+1) |
| `src/vision_browser/inject.js` | getA11yInfo, removeBadges, generateSelector, badgeElements, extractA11yTree (+1) |

## Entry Points

Start here when exploring this area:

- **`test_init_defaults`** (Function) — `tests/test_milestone2.py:134`
- **`test_broadcast`** (Function) — `tests/test_milestone2.py:146`
- **`test_connect_disconnect`** (Function) — `tests/test_milestone2.py:158`
- **`test_send_screenshot_missing_file`** (Function) — `tests/test_milestone2.py:167`
- **`test_send_navigation`** (Function) — `tests/test_milestone2.py:173`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `WebSocketPreview` | Class | `src/vision_browser/websocket_preview.py` | 13 |
| `VisionBrowserError` | Class | `src/vision_browser/exceptions.py` | 5 |
| `ConfigError` | Class | `src/vision_browser/exceptions.py` | 9 |
| `BrowserError` | Class | `src/vision_browser/exceptions.py` | 17 |
| `BrowserNotInstalledError` | Class | `src/vision_browser/exceptions.py` | 21 |
| `ActionExecutionError` | Class | `src/vision_browser/exceptions.py` | 25 |
| `DesktopController` | Class | `src/vision_browser/desktop.py` | 18 |
| `AgentBrowser` | Class | `src/vision_browser/browser.py` | 32 |
| `TimeoutError` | Class | `src/vision_browser/exceptions.py` | 33 |
| `BrowserSession` | Class | `src/vision_browser/session_pool.py` | 17 |
| `test_init_defaults` | Function | `tests/test_milestone2.py` | 134 |
| `test_broadcast` | Function | `tests/test_milestone2.py` | 146 |
| `test_connect_disconnect` | Function | `tests/test_milestone2.py` | 158 |
| `test_send_screenshot_missing_file` | Function | `tests/test_milestone2.py` | 167 |
| `test_send_navigation` | Function | `tests/test_milestone2.py` | 173 |
| `test_send_error` | Function | `tests/test_milestone2.py` | 182 |
| `test_generate_dashboard` | Function | `tests/test_milestone2.py` | 191 |
| `broadcast` | Function | `src/vision_browser/websocket_preview.py` | 28 |
| `send_screenshot` | Function | `src/vision_browser/websocket_preview.py` | 48 |
| `send_navigation` | Function | `src/vision_browser/websocket_preview.py` | 69 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run → List_screenshots` | cross_community | 5 |
| `Run → _encode_image` | cross_community | 5 |
| `Run → TimeoutError` | cross_community | 5 |
| `Execute_batch → TimeoutError` | cross_community | 5 |
| `Execute_batch → BrowserError` | cross_community | 5 |
| `_run_desktop → VisionAPIError` | cross_community | 5 |
| `_analyze_with_json_retry → VisionAPIError` | cross_community | 5 |
| `Run → _apply_rate_limit` | cross_community | 4 |
| `Run → _build_stricter_prompt` | cross_community | 4 |
| `Run → ActionExecutionError` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 13 calls |

## How to Explore

1. `gitnexus_context({name: "test_init_defaults"})` — see callers and callees
2. `gitnexus_query({query: "vision_browser"})` — find related execution flows
3. Read key files listed above for implementation details
