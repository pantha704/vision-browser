# Phase 11 Summary: Model JSON Compliance

## Status: COMPLETE

## Changes Made

### Bug Fix (vision.py line 190)
- Split `httpx.HTTPError` handler into `HTTPStatusError` (has `.response`) + generic `HTTPError` catch-all
- Fixes `AttributeError` when `ConnectError`/`RemoteProtocolError` lack `.response` attribute

### MODEL-01: JSON Validation Pipeline
- Added `ModelResponseError` exception class in `exceptions.py`
  - Stores `raw_response`, `expected_schema`, `context` dict
  - Supports context chaining via `.with_context(**kwargs)`
- Added `_validate_json_response()` method to `VisionClient`
  - Detects when `_extract_json` falls back to safe wrapper
  - Raises `ModelResponseError` with schema context on failure

### MODEL-02: JSON Extraction
- Existing `_extract_json` already handles markdown blocks, direct JSON, brace extraction
- `_validate_json_response` uses it and validates the result

### MODEL-03: Retry with Stricter Prompts
- Added `_build_stricter_prompt()` with progressively stricter messages
- `analyze()` loop catches `ModelResponseError`, retries with stricter prompt
- Falls back to Groq if NIM retry also fails

### MODEL-04: Structured Error Reporting
- `ModelResponseError` includes raw response (truncated to 1000 chars), expected schema, context dict
- Context includes stage ("empty_response", "parse_fallback") and model text preview

## Tests
- 16 new tests in `test_model_json_compliance.py` (all pass)
- 3 existing tests updated to reflect new behavior (all pass)
- Total: 185 tests passing

## Compliance Rate
- Valid JSON responses: 100% pass
- Markdown-wrapped JSON: 100% pass
- Prose responses: correctly raise `ModelResponseError` (retry/fallback triggers)
- Partial JSON: correctly raises `ModelResponseError`

## Files Modified
- `/home/panther/Desktop/projects/vision-browser/src/vision_browser/vision.py`
- `/home/panther/Desktop/projects/vision-browser/src/vision_browser/exceptions.py`
- `/home/panther/Desktop/projects/vision-browser/tests/test_vision_and_desktop.py`
- `/home/panther/Desktop/projects/vision-browser/tests/test_model_json_compliance.py` (new)
