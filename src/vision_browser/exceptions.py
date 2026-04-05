"""Vision Browser — custom exception classes."""

from __future__ import annotations


class VisionBrowserError(Exception):
    """Base exception for all vision-browser errors."""


class ConfigError(VisionBrowserError):
    """Configuration or validation error."""


class VisionAPIError(VisionBrowserError):
    """Error from vision model API (Groq, NIM)."""


class BrowserError(VisionBrowserError):
    """Error from agent-browser subprocess."""


class BrowserNotInstalledError(BrowserError):
    """agent-browser CLI not found on PATH."""


class ActionExecutionError(VisionBrowserError):
    """Error executing a vision model action."""


class RateLimitError(VisionAPIError):
    """API rate limit exceeded (HTTP 429)."""


class TimeoutError(VisionBrowserError):
    """Operation timed out."""


class ModelResponseError(VisionAPIError):
    """Model response could not be parsed as valid JSON.

    Attributes:
        raw_response: The raw text returned by the model.
        expected_schema: The JSON schema the model was expected to match.
        context: Additional debugging context.
    """

    def __init__(
        self,
        message: str,
        raw_response: str = "",
        expected_schema: dict | None = None,
    ):
        super().__init__(message)
        self.raw_response = raw_response
        self.expected_schema = expected_schema
        self.context: dict[str, str] = {}

    def with_context(self, **kwargs) -> "ModelResponseError":
        """Add debugging context and return self for chaining."""
        self.context.update(kwargs)
        return self
