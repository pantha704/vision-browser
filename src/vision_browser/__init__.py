"""Vision Browser -- fast vision-driven automation with NIM Vision + Playwright."""

from vision_browser.browser import AgentBrowser
from vision_browser.config import AppConfig
from vision_browser.desktop import DesktopController
from vision_browser.diff_screenshot import DifferentialScreenshot
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
from vision_browser.mcp_server import MCPServer
from vision_browser.multi_browser import MultiBrowserManager
from vision_browser.orchestrator import Orchestrator
from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.session import SessionManager
from vision_browser.session_pool import SessionPool
from vision_browser.vision import VisionClient
from vision_browser.websocket_preview import WebSocketPreview

__all__ = [
    # Core
    "AgentBrowser",
    "AppConfig",
    "DesktopController",
    "DifferentialScreenshot",
    "FastOrchestrator",
    "MCPServer",
    "MultiBrowserManager",
    "Orchestrator",
    "PlaywrightBrowser",
    "SessionManager",
    "SessionPool",
    "VisionClient",
    "WebSocketPreview",
    # Exceptions
    "ActionExecutionError",
    "BrowserError",
    "BrowserNotInstalledError",
    "ConfigError",
    "TimeoutError",
    "VisionAPIError",
    "VisionBrowserError",
]
__version__ = "0.5.0"
