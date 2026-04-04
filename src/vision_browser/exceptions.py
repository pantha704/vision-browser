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
