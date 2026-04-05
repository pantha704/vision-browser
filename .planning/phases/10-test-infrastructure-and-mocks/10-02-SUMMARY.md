# Plan 2: Migrate VisionClient Tests to Use Mock Infrastructure — Summary

**Phase:** 10 (Test Infrastructure & Mocks)
**Wave:** 2
**Status:** COMPLETE

## Objective
Rewrite all existing VisionClient tests to use the new mock fixtures instead of `patch("httpx.post")`. Add tests for malformed response handling.

## What Was Done
- Rewrote `tests/test_vision_and_desktop.py` (41 tests, all passing):
  - All `TestVisionClientNIM` tests use `httpx_mock.add_response()` instead of `@patch("httpx.post")`
  - All `TestVisionClientGroq` tests use mock fixtures from conftest
  - Added 5 new malformed response tests: prose, partial JSON, markdown, rate limit exhausted, timeout fallback to Groq
  - Removed duplicate `mock_api_keys` fixture (now in conftest.py as autouse)

## Key Findings
- **Groq fallback timing**: The `analyze()` method only calls Groq fallback when `attempt < max_retries`. With `retry_attempts=1`, Groq fallback never runs. Tests need `retry_attempts=2` to trigger Groq fallback.
- **httpx_mock intercepts Groq SDK**: The Groq SDK uses httpx internally. When `patch.object(client, "_get_groq")` is used, the real Groq class is instantiated (since `vision_browser.vision.Groq` isn't patched), creating a real httpx client. Solution: set `client._groq` directly on the test instance.
- **Source code bug exposed**: `test_nim_analyze_http_error` revealed that `httpx.HTTPError` subclasses like `ConnectError` don't have a `.response` attribute, but the code checks `e.response.status_code`. This causes `AttributeError` to propagate instead of the intended `VisionAPIError`.

## Acceptance Criteria
- [x] All TestVisionClientNIM tests use `httpx_mock`
- [x] All TestVisionClientGroq tests use mock fixtures
- [x] 5 new malformed response tests added
- [x] `pytest tests/test_vision_and_desktop.py -v` exits 0 with 41 passed
- [x] No `@patch("vision_browser.vision.httpx.post"` decorators remain
- [x] Tests complete in 1.91s
