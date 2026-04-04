"""Vision Browser — fast vision-driven automation with NIM Vision + Playwright."""

from vision_browser.browser import AgentBrowser
from vision_browser.config import AppConfig
from vision_browser.desktop import DesktopController
from vision_browser.exceptions import (
    ActionExecutionError,
    BrowserError,
    BrowserNotInstalledError,
    ConfigError,
    TimeoutError,
    VisionAPIError,
    VisionBrowserError,
)
from vision_browser.fast_orchestrator import FastOrchestrator
from vision_browser.orchestrator import Orchestrator
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.vision import VisionClient

__all__ = [
    # Core
    "AgentBrowser",
    "AppConfig",
    "DesktopController",
    "FastOrchestrator",
    "Orchestrator",
    "PlaywrightBrowser",
    "VisionClient",
    # Exceptions
    "ActionExecutionError",
    "BrowserError",
    "BrowserNotInstalledError",
    "ConfigError",
    "TimeoutError",
    "VisionAPIError",
    "VisionBrowserError",
]
__version__ = "0.3.0"
