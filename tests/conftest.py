"""Pytest fixtures for vision-browser tests."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


# ── API Key Fixtures ───────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_api_keys():
    """Set mock API keys for all tests. Cleans up after each test."""
    os.environ["NVIDIA_API_KEY"] = "test-nim-key"
    os.environ["GROQ_API_KEY"] = "test-groq-key"
    yield
    os.environ.pop("NVIDIA_API_KEY", None)
    os.environ.pop("GROQ_API_KEY", None)


# ── NIM HTTP Mock Fixtures ─────────────────────────────────────────


@pytest.fixture
def mock_nim_success(httpx_mock):
    """Mock NIM API success response."""
    from tests.mocks import nim_success_response

    httpx_mock.add_response(
        method="POST",
        url="https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/24e0c62b-f7d0-44ba-8012-012c2a1aaf31",
        json=nim_success_response(),
        status_code=200,
    )


@pytest.fixture
def mock_nim_malformed(httpx_mock):
    """Mock NIM API with malformed/prose response."""
    from tests.mocks import nim_prose_response

    httpx_mock.add_response(
        method="POST",
        url="https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/24e0c62b-f7d0-44ba-8012-012c2a1aaf31",
        json=nim_prose_response(),
        status_code=200,
    )


@pytest.fixture
def mock_nim_empty(httpx_mock):
    """Mock NIM API with empty content response."""
    from tests.mocks import nim_empty_response

    httpx_mock.add_response(
        method="POST",
        url="https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/24e0c62b-f7d0-44ba-8012-012c2a1aaf31",
        json=nim_empty_response(),
        status_code=200,
    )


@pytest.fixture
def mock_nim_markdown(httpx_mock):
    """Mock NIM API with markdown-wrapped JSON response."""
    from tests.mocks import nim_markdown_response

    httpx_mock.add_response(
        method="POST",
        url="https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/24e0c62b-f7d0-44ba-8012-012c2a1aaf31",
        json=nim_markdown_response(),
        status_code=200,
    )


@pytest.fixture
def mock_nim_partial_json(httpx_mock):
    """Mock NIM API with partial/truncated JSON response."""
    from tests.mocks import nim_partial_json_response

    httpx_mock.add_response(
        method="POST",
        url="https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/24e0c62b-f7d0-44ba-8012-012c2a1aaf31",
        json=nim_partial_json_response(),
        status_code=200,
    )


# ── Groq Mock Fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_groq_success():
    """Mock Groq client with successful JSON response."""
    from tests.mocks import groq_success_response

    mock_response = groq_success_response()

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("vision_browser.vision.Groq", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_groq_tool_call():
    """Mock Groq client with tool call (function calling) response."""
    from tests.mocks import groq_tool_call_response

    mock_response = groq_tool_call_response()

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("vision_browser.vision.Groq", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_groq_empty():
    """Mock Groq client with empty response."""
    from tests.mocks import groq_empty_response

    mock_response = groq_empty_response()

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("vision_browser.vision.Groq", return_value=mock_client):
        yield mock_client


# ── Vision Client Factory ──────────────────────────────────────────


@pytest.fixture
def vision_client():
    """Factory fixture that creates a VisionClient with mocked dependencies."""
    from vision_browser.vision import VisionClient
    from vision_browser.config import VisionConfig

    def _create_client(orchestrator_cfg: dict | None = None):
        cfg = VisionConfig()
        client = VisionClient(cfg, orchestrator_cfg)
        return client

    return _create_client
