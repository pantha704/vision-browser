---
wave: 1
depends_on: []
files_modified:
  - tests/conftest.py
  - tests/mocks/
  - pyproject.toml
  - tests/test_vision_and_desktop.py
  - tests/test_core.py
autonomous: true
requirements_addressed: [TEST-01]
---

# Phase 10: Test Infrastructure & Mocks — Plan

**Goal:** Set up mock infrastructure for deterministic NIM API tests, enabling all subsequent work.

**Must-haves (goal-backward verification):**
- HTTP-level mocks for NIM and Groq APIs exist and are reusable
- Tests run without network access (no real API calls)
- Mock responses cover both valid JSON and realistic malformed responses
- Tests complete in under 5 seconds total

---

## Plan 1: HTTP Mock Infrastructure & Test Fixtures

<objective>
Create the foundational mock infrastructure: pytest-httpx dependency, conftest.py fixtures with reusable mock responses (valid and malformed), and migrate existing VisionClient tests to use HTTP-level mocks instead of `patch("httpx.post")`.
</objective>

<wave>1</wave>
<depends_on>[]</depends_on>
<files_modified>
  - pyproject.toml
  - tests/conftest.py
  - tests/mocks/nim_responses.py
  - tests/mocks/groq_responses.py
  - tests/mocks/__init__.py
</files_modified>
<autonomous>true</autonomous>

<read_first>
- `pyproject.toml` — current dev dependencies, add `pytest-httpx`
- `tests/test_vision_and_desktop.py` — existing VisionClient tests using `patch("httpx.post")`
- `tests/test_core.py` — existing tests that touch VisionClient
- `src/vision_browser/vision.py` — the actual `_nim_analyze` and `_groq_analyze` methods to understand exact HTTP call signatures
- `src/vision_browser/config.py` — VisionConfig to understand API key and endpoint configuration
- `src/vision_browser/exceptions.py` — exception types that tests should assert
</read_first>

<acceptance_criteria>
- `pyproject.toml` contains `pytest-httpx` in dev dependencies
- `tests/conftest.py` exists with `@pytest.fixture` named `mock_nim_success`, `mock_nim_malformed`, `mock_groq_success`
- `tests/mocks/nim_responses.py` exists and contains at least 5 mock response builders: valid JSON, markdown-wrapped JSON, prose-only, empty content, partial/truncated JSON
- `tests/mocks/groq_responses.py` exists and contains at least 3 mock response builders: valid JSON via tool calls, valid JSON via json_object, empty response
- `tests/mocks/__init__.py` exists and exports all mock builders
- No import of `unittest.mock.patch` for `httpx.post` in any test file after migration (grep: `patch.*httpx.post` returns 0 matches in tests/)
</acceptance_criteria>

<action>
1. Add `pytest-httpx>=0.27.0` to dev dependencies in `pyproject.toml`:
   - Edit `[dependency-groups]` section, add `"pytest-httpx>=0.27.0"` to the dev list

2. Create `tests/mocks/__init__.py` with exports:
```python
from .nim_responses import (
    nim_success_response,
    nim_markdown_response,
    nim_prose_response,
    nim_empty_response,
    nim_partial_json_response,
)
from .groq_responses import (
    groq_success_response,
    groq_tool_call_response,
    groq_empty_response,
)

__all__ = [
    "nim_success_response",
    "nim_markdown_response",
    "nim_prose_response",
    "nim_empty_response",
    "nim_partial_json_response",
    "groq_success_response",
    "groq_tool_call_response",
    "groq_empty_response",
]
```

3. Create `tests/mocks/nim_responses.py` with mock response builders. Each function returns a dict matching the NIM API response structure `{"choices": [{"message": {"content": "..."}}]}`:
   - `nim_success_response(content=None)` — returns valid JSON content (default: `{"actions": [], "done": true, "reasoning": "ok"}`)
   - `nim_markdown_response(content=None)` — returns JSON wrapped in ```json``` markdown block
   - `nim_prose_response()` — returns prose text like "This page shows a login form with username and password fields"
   - `nim_empty_response()` — returns `{"choices": [{"message": {"content": ""}}]}`
   - `nim_partial_json_response()` — returns truncated JSON like `{"actions": [{"action": "click", "elem`

4. Create `tests/mocks/groq_responses.py` with mock response builders matching Groq SDK response structure:
   - `groq_success_response(content=None)` — returns a mock with `choices[0].message.content` set to valid JSON
   - `groq_tool_call_response(arguments=None)` — returns a mock with `choices[0].message.tool_calls[0].function.arguments` set
   - `groq_empty_response()` — returns a mock with `choices[0].message.content = None` and no tool_calls

5. Create `tests/conftest.py` with pytest fixtures:
   - `mock_api_keys` (autouse) — sets `NVIDIA_API_KEY` and `GROQ_API_KEY` env vars, cleans up after
   - `mock_nim_success` — uses `pytest-httpx` to register a successful NIM response for the NIM endpoint URL pattern
   - `mock_nim_malformed` — registers malformed/prose responses
   - `mock_groq_success` — mocks Groq client at SDK level (since Groq uses its own SDK, not raw HTTP)
   - `vision_client` — factory fixture that creates a VisionClient with mocked dependencies

6. Run `bun run uv sync --dev` (or `uv sync --dev`) to install pytest-httpx
</action>

---

## Plan 2: Migrate VisionClient Tests to Use Mock Infrastructure

<objective>
Rewrite all existing VisionClient tests in `test_vision_and_desktop.py` to use the new mock fixtures instead of `patch("httpx.post")`. Add tests for malformed response handling that were previously missing.
</objective>

<wave>2</wave>
<depends_on>[1]</depends_on>
<files_modified>
  - tests/test_vision_and_desktop.py
</files_modified>
<autonomous>true</autonomous>

<read_first>
- `tests/conftest.py` (created in Plan 1) — available fixtures
- `tests/mocks/nim_responses.py` (created in Plan 1) — mock response builders
- `tests/mocks/groq_responses.py` (created in Plan 1) — mock response builders
- `tests/test_vision_and_desktop.py` — current test implementations to migrate
- `src/vision_browser/vision.py` — VisionClient implementation for understanding what to test
- `src/vision_browser/exceptions.py` — exception types: VisionAPIError, TimeoutError, RateLimitError
</read_first>

<acceptance_criteria>
- All TestVisionClientNIM tests use `httpx_mock` from pytest-httpx instead of `patch("vision_browser.vision.httpx.post")`
- All TestVisionClientGroq tests use mocked Groq client from conftest fixtures instead of inline patching
- At least 3 new tests exist for malformed responses: `test_nim_prose_response_raises`, `test_nim_partial_json_raises`, `test_nim_markdown_response_parsed`
- Test file runs with `pytest tests/test_vision_and_desktop.py -v` with 0 errors
- No `@patch("vision_browser.vision.httpx.post"` decorator remains in the file (grep returns 0)
- Tests complete in under 3 seconds (measure with `pytest --durations=0`)
</acceptance_criteria>

<action>
1. Migrate `TestVisionClientNIM` class tests:
   - Replace `@patch("vision_browser.vision.httpx.post")` with `httpx_mock.add_response()` calls
   - For `test_nim_analyze_success`: use `httpx_mock.add_response(json=nim_success_response(), status_code=200)`
   - For `test_nim_analyze_timeout`: use `httpx_mock.add_exception(httpx.TimeoutException("timeout"))`
   - For `test_nim_analyze_rate_limit`: use `httpx_mock.add_response(status_code=429, json={"error": "rate limited"})`
   - For `test_nim_analyze_http_error`: use `httpx_mock.add_exception(httpx.RemoteProtocolError("connection reset"))`
   - For `test_nim_analyze_non_200`: use `httpx_mock.add_response(status_code=500, text="Internal Server Error")`
   - For `test_nim_analyze_empty_response`: use `httpx_mock.add_response(json=nim_empty_response())`
   - For `test_nim_analyze_invalid_json`: use `httpx_mock.add_response(json={"choices": [{"message": {"content": "not json"}}]})` — note: this tests _extract_json fallback, not HTTP-level JSON error
   - For `test_nim_analyze_with_schema`: use `httpx_mock.add_response(json=nim_success_response())`, verify the request body contains schema-related text in the prompt

2. Migrate `TestVisionClientGroq` class tests:
   - Create a `mock_groq_client` fixture in conftest that patches `vision_browser.vision.Groq`
   - Replace inline `MagicMock` chains with fixture-provided mock
   - Keep the same test assertions but use the fixture

3. Migrate `TestVisionClientRetry` and `TestVisionClientRateLimit`:
   - Use `httpx_mock` for NIM-side mocking
   - Use `mock_groq_client` fixture for Groq fallback mocking
   - For rate limit test: use `time.sleep` patching (keep existing approach, it's correct)

4. Migrate `TestVisionClientEncode`:
   - No HTTP mocking needed (static method, file I/O only)
   - Keep as-is

5. Add NEW tests for malformed responses:
   - `test_nim_prose_response_raises` — mock NIM returns prose, VisionClient._extract_json wraps it, but `_nim_analyze` should still return a dict (not raise) since _extract_json has a fallback. Verify returned dict has `done: False` and reasoning contains the prose text.
   - `test_nim_partial_json_raises` — mock NIM returns partial JSON `{"actions": [`, verify _extract_json fallback returns safe dict
   - `test_nim_markdown_response_parsed` — mock NIM returns ```json\n{...}\n```, verify _extract_json extracts correctly
   - `test_nim_rate_limit_retry_exhausted` — mock NIM returns 429 repeatedly, verify VisionAPIError raised after all retries
   - `test_nim_timeout_fallback_to_groq` — mock NIM timeout, mock Groq success, verify Groq result returned

6. Remove the `mock_api_keys` fixture from `test_vision_and_desktop.py` (it will be in `conftest.py` as autouse)
</action>

---

## Plan 3: Add Coverage Configuration and Achieve 80%+ on vision_browser Module

<objective>
Add pytest-cov dependency, configure coverage in pyproject.toml, run coverage report, and identify gaps in the vision_browser module.
</objective>

<wave>2</wave>
<depends_on>[1]</depends_on>
<files_modified>
  - pyproject.toml
  - tests/test_core.py
</files_modified>
<autonomous>true</autonomous>

<read_first>
- `pyproject.toml` — current dev dependencies
- `tests/test_core.py` — existing tests, check what vision_browser modules they cover
- `tests/test_vision_and_desktop.py` — migrated tests from Plan 2
- `src/vision_browser/config.py` — config module coverage
- `src/vision_browser/exceptions.py` — exceptions module
- `src/vision_browser/browser.py` — browser module
- `src/vision_browser/desktop.py` — desktop module
</read_first>

<acceptance_criteria>
- `pyproject.toml` contains `pytest-cov` in dev dependencies
- `pyproject.toml` contains `[tool.pytest.ini_options]` with `addopts = "--cov=vision_browser --cov-report=term-missing"`
- Running `pytest tests/ --cov=vision_browser --cov-report=term-missing` shows >=80% coverage on `vision_browser` module
- Coverage report output is visible (term-missing format shows uncovered lines)
- `tests/test_core.py` uses httpx_mock where it touches VisionClient (if any tests do)
</acceptance_criteria>

<action>
1. Add `pytest-cov>=5.0.0` to dev dependencies in `pyproject.toml`
2. Add `[tool.pytest.ini_options]` section to `pyproject.toml` with:
   ```toml
   [tool.pytest.ini_options]
   addopts = "--cov=vision_browser --cov-report=term-missing --cov-fail-under=80"
   testpaths = ["tests"]
   ```
3. Run `pytest tests/ --cov=vision_browser --cov-report=term-missing -v` to get baseline coverage
4. Identify modules with <80% coverage from the report
5. For any module below 80%, add targeted tests:
   - If `config.py` is low: add tests for all config classes (BrowserConfig, OrchestratorConfig, DesktopConfig, etc.) with edge cases
   - If `exceptions.py` is low: add tests that raise each exception type
   - If `browser.py` is low: add tests for `_validate_url`, `_element_to_ref` (already in test_core.py, verify they run)
   - If `desktop.py` is low: add more DesktopController tests (already well-covered in test_vision_and_desktop.py)
6. Re-run coverage to confirm >=80%
</action>

---

## Plan 4: Deterministic Test Verification & Performance Gate

<objective>
Verify all tests are fully deterministic (no network calls), run within the 5-second performance gate, and produce consistent results across multiple runs.
</objective>

<wave>3</wave>
<depends_on>[2, 3]</depends_on>
<files_modified>
  - (none, verification only)
</files_modified>
<autonomous>true</autonomous>

<read_first>
- `tests/conftest.py` — verify all fixtures properly isolate tests
- `tests/test_vision_and_desktop.py` — verify no residual real API calls
- `tests/test_core.py` — verify no residual real API calls
- `pyproject.toml` — verify coverage config
</read_first>

<acceptance_criteria>
- `pytest tests/ -v --tb=short` exits 0 with all tests passing
- `pytest tests/ --durations=0` shows total time < 5 seconds
- Running `pytest tests/` three times in a row produces identical pass/fail results (deterministic)
- `pytest tests/ --cov=vision_browser --cov-report=term-missing` shows >=80% coverage
- `grep -r "api.nvcf.nvidia.com\|api.groq.com" tests/` returns 0 matches (no hardcoded real URLs in tests)
- `grep -r "NVIDIA_API_KEY\|GROQ_API_KEY" tests/` only appears in conftest.py mock fixture (no real keys)
- `pytest tests/ -x` (fail fast) works correctly — if a test fails, it stops immediately
</acceptance_criteria>

<action>
1. Run `pytest tests/ -v --tb=short` — verify all tests pass
2. Run `pytest tests/ --durations=0` — check total time, identify slow tests
3. If any test takes >1 second, investigate: likely a `time.sleep()` call that should be mocked. Patch `time.sleep` in rate limit tests.
4. Run `pytest tests/` three times, capture exit codes and test counts, verify consistency
5. Run `grep -r "api.nvcf.nvidia.com\|api.groq.com" tests/` — verify no real URLs in test code
6. Run `pytest tests/ --cov=vision_browser --cov-report=term-missing` — verify >=80% coverage
7. If coverage <80%, identify uncovered lines and add targeted tests (back to Plan 3 tasks)
8. Run `pytest tests/ -x` — verify fail-fast works
</action>

---

## Verification Summary

| Criteria | Plan | Verification Method |
|----------|------|-------------------|
| HTTP-level mocks for NIM API | Plan 1 | `grep httpx_mock tests/` returns matches |
| HTTP-level mocks for Groq API | Plan 1 | `grep mock_groq tests/` returns matches |
| Mock responses include malformed | Plan 1, 2 | `grep -c "prose\|partial\|empty\|markdown" tests/mocks/` >= 4 |
| Tests run without network | Plan 2, 4 | `pytest tests/` passes with `--tb=short`, no timeouts |
| Mock responses reusable | Plan 1 | Fixtures in conftest.py imported by multiple test files |
| 80%+ coverage on vision_browser | Plan 3, 4 | `pytest --cov=vision_browser --cov-fail-under=80` exits 0 |
| Tests run in <5 seconds | Plan 4 | `pytest --durations=0` shows total < 5s |
| Deterministic (no flakiness) | Plan 4 | 3 consecutive runs produce identical results |
