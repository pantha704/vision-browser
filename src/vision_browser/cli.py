"""CLI entry point for vision-browser."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

# CLI-04: Graceful Rich fallback
try:
    from rich.console import Console
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class _FallbackConsole:
    """Basic console that strips Rich markup when Rich is not available."""
    def print(self, text: str = "") -> None:
        import re
        clean = re.sub(r'\[/?[^\]]*\]', '', str(text))
        print(clean)


if not HAS_RICH:
    Console = _FallbackConsole  # type: ignore
    Panel = None  # type: ignore

console = Console()


from vision_browser.config import AppConfig
from vision_browser.exceptions import (
    BrowserNotInstalledError,
    ConfigError,
    VisionBrowserError,
)


def _print_user_error(message: str, suggestion: str = "") -> None:
    """CLI-02: Print a human-readable error with optional suggestion."""
    console.print(f"[bold red]Error:[/bold red] {message}")
    if suggestion:
        console.print(f"  [dim]💡 {suggestion}[/dim]")


def _setup_logging(verbose: bool = False) -> None:
    """Configure structured logging to both stdout and file."""
    import logging.handlers
    from datetime import datetime
    
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory
    log_dir = Path.home() / ".local" / "share" / "vision-browser" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log file with timestamp
    log_file = log_dir / f"vision-browser-{datetime.now().strftime('%Y%m%d')}.log"
    
    # Configure root logger
    root_logger = logging.getLogger("vision_browser")
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Format for console (human-readable)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    
    # Format for file (JSON structured)
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_entry = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info and record.exc_info[0]:
                log_entry["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_entry)
    
    file_format = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler (rotating)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)  # Capture all to file
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging to: {log_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vision-browser",
        description="Fast vision-driven browser automation",
    )
    parser.add_argument("task", help="What you want to accomplish")
    parser.add_argument("--url", "-u", help="Starting URL")
    parser.add_argument(
        "--desktop", "-d", action="store_true", help="Use desktop mode (xdotool)"
    )
    parser.add_argument("--config", "-c", type=Path, help="Path to config.yaml")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--brave", action="store_true",
        help="Connect to running Brave browser (port 9222)"
    )
    parser.add_argument(
        "--session", type=str, default="",
        help="Session name for persistent cookies/auth"
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="Use new Playwright-based fast orchestrator (experimental)"
    )

    args = parser.parse_args()
    _setup_logging(verbose=args.verbose)

    # Check agent-browser availability
    if not args.desktop and shutil.which("agent-browser") is None:
        _print_user_error(
            "agent-browser not found on PATH.",
            "Install: npm i -g agent-browser && agent-browser install",
        )
        sys.exit(1)

    # Load and validate config
    cfg = None
    try:
        cfg = AppConfig.from_yaml(args.config)
    except FileNotFoundError:
        console.print("[yellow]⚠ No config.yaml found, using defaults[/yellow]")
        cfg = AppConfig()
    except Exception as e:
        console.print(f"[bold red]Config error:[/bold red] {e}")
        sys.exit(1)

    if cfg is None:
        sys.exit(1)

    # CLI overrides
    if args.brave:
        cfg.browser.cdp_url = "http://localhost:9222"
    if args.session:
        cfg.browser.session_name = args.session

    try:
        from vision_browser.orchestrator import Orchestrator
        from vision_browser.fast_orchestrator import FastOrchestrator

        if args.fast:
            console.print("[bold blue]⚡ Using fast Playwright orchestrator[/bold blue]")
            orchestrator = FastOrchestrator(cfg)
            orchestrator.run(args.task, url=args.url)
            # CLI-03: Print task summary
            if hasattr(orchestrator, 'print_task_summary'):
                orchestrator.print_task_summary()
        else:
            orchestrator = Orchestrator(cfg)
            orchestrator.run(args.task, url=args.url, desktop_mode=args.desktop)

        # Clean shutdown for fast orchestrator
        if args.fast and hasattr(orchestrator, 'close'):
            orchestrator.close()
    except ConfigError as e:
        _print_user_error(
            f"Configuration error: {e}",
            "Check your config.yaml file and environment variables (NVIDIA_API_KEY, GROQ_API_KEY).",
        )
        sys.exit(1)
    except BrowserNotInstalledError as e:
        _print_user_error(
            f"Browser not available: {e}",
            "Install Playwright browsers: playwright install chromium",
        )
        sys.exit(1)
    except VisionBrowserError as e:
        _print_user_error(str(e), "Check your configuration and network connection.")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️ Interrupted[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
