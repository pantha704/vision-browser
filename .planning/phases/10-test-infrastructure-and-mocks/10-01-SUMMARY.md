# Plan 1: HTTP Mock Infrastructure & Test Fixtures — Summary

**Phase:** 10 (Test Infrastructure & Mocks)
**Wave:** 1
**Status:** COMPLETE

## Objective
Create the foundational mock infrastructure: pytest-httpx dependency, conftest.py fixtures with reusable mock responses (valid and malformed), and migrate existing VisionClient tests to use HTTP-level mocks.

## What Was Built
- Added `pytest-httpx>=0.27.0` to dev dependencies
- Created `tests/mocks/` package with 8 mock response builders:
  - `nim_responses.py`: 5 builders (success, markdown, prose, empty, partial JSON)
  - `groq_responses.py`: 3 builders (success, tool call, empty)
- Created `tests/conftest.py` with 10 fixtures:
  - `mock_api_keys` (autouse) — sets/cleans mock API keys
  - `mock_nim_success`, `mock_nim_malformed`, `mock_nim_empty`, `mock_nim_markdown`, `mock_nim_partial_json` — httpx_mock fixtures
  - `mock_groq_success`, `mock_groq_tool_call`, `mock_groq_empty` — Groq SDK mock fixtures
  - `vision_client` — factory fixture
- Created `tests/test_vision_client_mocks.py` with 11 tests validating all mock builders

## Key Discovery
- `pytest-httpx` intercepts ALL httpx requests, including Groq SDK's internal httpx client. Mocking `vision_browser.vision.Groq` prevents this, but direct `patch.object(client, "_get_groq")` does not — the real Groq class creates an httpx client that gets intercepted. Solution: set `client._groq` directly on the test instance.

## Acceptance Criteria
- [x] `pyproject.toml` contains `pytest-httpx`
- [x] `tests/conftest.py` exists with all required fixtures
- [x] `tests/mocks/nim_responses.py` has 5+ mock builders
- [x] `tests/mocks/groq_responses.py` has 3+ mock builders
- [x] `tests/mocks/__init__.py` exports all builders
- [x] No `patch.*httpx.post` in test files (excluding migration target)
