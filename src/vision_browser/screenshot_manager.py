"""Screenshot lifecycle management for vision-browser sessions.

Handles creation, retention, and cleanup of screenshot files.
Uses a unique session directory per run to avoid conflicts.
"""

from __future__ import annotations

import logging
import shutil
import signal
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """Manages screenshot files with session isolation and auto-cleanup.

    Creates a unique temp directory per session, stores numbered screenshots
    (turn-001.png, turn-002.png, etc.), and auto-deletes on normal exit.
    Use keep=True to preserve for debugging.

    Usage:
        mgr = ScreenshotManager(keep=False)
        mgr.register_cleanup()  # Auto-delete on SIGINT/SIGTERM
        path = mgr.next_path()  # Returns unique path for this turn
        browser.screenshot(path)
        mgr.cleanup()  # Manual cleanup (also called by signal handler)
    """

    def __init__(self, keep: bool = False, max_retain: int = 20):
        """
        Args:
            keep: If True, never delete screenshots (for debugging).
            max_retain: Max screenshots to keep per session (0 = unlimited).
                       Oldest are deleted first when exceeded.
        """
        self.keep = keep
        self.max_retain = max_retain
        self._session_dir: Path | None = None
        self._turn = 0
        self._cleanup_registered = False

    @property
    def session_dir(self) -> Path:
        """Lazy-create unique session directory."""
        if self._session_dir is None:
            self._session_dir = Path(tempfile.mkdtemp(prefix="vision-browser-"))
            logger.info(f"Screenshot session: {self._session_dir}")
        return self._session_dir

    def next_path(self) -> Path:
        """Get the next screenshot path for this turn. Increments turn counter."""
        self._turn += 1
        path = self.session_dir / f"turn-{self._turn:03d}.png"

        # Enforce retention limit
        if self.max_retain > 0:
            self._enforce_retention()

        return path

    @property
    def current_path(self) -> Path:
        """Get the most recent screenshot path (without incrementing turn)."""
        if self._turn == 0:
            raise RuntimeError("No screenshots taken yet")
        return self.session_dir / f"turn-{self._turn:03d}.png"

    @property
    def turn(self) -> int:
        """Current turn number."""
        return self._turn

    def list_screenshots(self) -> list[Path]:
        """List all screenshots in session directory, sorted by turn."""
        if self._session_dir is None or not self._session_dir.exists():
            return []
        return sorted(self._session_dir.glob("turn-*.png"))

    def get_diff_paths(self) -> tuple[Path | None, Path]:
        """Get (previous_screenshot, new_screenshot) for differential comparison.

        Returns (None, new_path) on first turn.
        """
        new_path = self.next_path()
        if self._turn <= 1:
            return None, new_path
        prev_path = self.session_dir / f"turn-{self._turn - 1:03d}.png"
        return prev_path, new_path

    def cleanup(self) -> None:
        """Delete session directory unless keep=True."""
        if self.keep:
            screenshots = self.list_screenshots()
            if screenshots:
                logger.info(f"Screenshots preserved ({len(screenshots)} files): {self.session_dir}")
            return

        if self._session_dir and self._session_dir.exists():
            try:
                count = len(list(self._session_dir.glob("*.png")))
                shutil.rmtree(self._session_dir)
                logger.debug(f"Cleaned up {count} screenshots: {self._session_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup screenshots: {e}")

        self._session_dir = None
        self._turn = 0

    def register_cleanup(self) -> None:
        """Register signal handlers for auto-cleanup on exit."""
        if self._cleanup_registered:
            return

        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        def _handler(signum: int, frame: Any) -> None:
            self.cleanup()
            # Re-raise the signal for default handling
            orig = original_sigint if signum == signal.SIGINT else original_sigterm
            if callable(orig):
                orig(signum, frame)

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
        self._cleanup_registered = True

    def _enforce_retention(self) -> None:
        """Delete oldest screenshots when exceeding max_retain."""
        if self.max_retain <= 0:
            return

        screenshots = self.list_screenshots()
        while len(screenshots) > self.max_retain:
            oldest = screenshots.pop(0)
            try:
                oldest.unlink()
                logger.debug(f"Removed old screenshot: {oldest}")
            except Exception as e:
                logger.warning(f"Failed to remove old screenshot {oldest}: {e}")

    def __enter__(self) -> "ScreenshotManager":
        self.register_cleanup()
        return self

    def __exit__(self, *args: Any) -> None:
        self.cleanup()
