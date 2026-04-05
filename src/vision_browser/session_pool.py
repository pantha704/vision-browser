"""Concurrent multi-browser sessions -- manage multiple browser instances."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

logger = logging.getLogger(__name__)

DEFAULT_MAX_SESSIONS = 5


@dataclass
class BrowserSession:
    """Represents a single browser session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    name: str = ""
    is_active: bool = False

    @property
    def url(self) -> str:
        return self.page.url if self.page else ""

    @property
    def title(self) -> str:
        return self.page.title() if self.page else ""


class SessionPool:
    """Manages a pool of concurrent browser sessions.

    Features:
    - Multiple independent browser instances
    - Session isolation (cookies, state, context)
    - Resource usage monitoring
    - Configurable maximum sessions
    """

    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS):
        self.max_sessions = max_sessions
        self._playwright = None
        self._sessions: dict[str, BrowserSession] = {}

    def _ensure_playwright(self) -> None:
        """Start Playwright if not already started."""
        if self._playwright is None:
            self._playwright = sync_playwright().start()

    def create_session(self, name: str = "", headless: bool = True) -> BrowserSession:
        """Create a new browser session.

        Args:
            name: Optional name for the session.
            headless: Run in headless mode.

        Returns:
            The created BrowserSession.

        Raises:
            RuntimeError: If max sessions reached.
        """
        if len(self._sessions) >= self.max_sessions:
            raise RuntimeError(
                f"Max sessions ({self.max_sessions}) reached. "
                f"Close a session before creating a new one."
            )

        self._ensure_playwright()

        session = BrowserSession(name=name or f"session-{len(self._sessions) + 1}")

        try:
            session.browser = self._playwright.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            session.context = session.browser.new_context()
            session.page = session.context.new_page()
            session.is_active = True
            self._sessions[session.id] = session

            logger.info(f"Created session '{session.name}' (id: {session.id})")
            return session

        except Exception as e:
            raise RuntimeError(f"Failed to create session: {e}") from e

    def get_session(self, session_id: str) -> BrowserSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close a specific session.

        Args:
            session_id: ID of the session to close.

        Returns:
            True if session was found and closed.
        """
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False

        try:
            if session.page:
                session.page.close()
            if session.context:
                session.context.close()
            if session.browser:
                session.browser.close()
            session.is_active = False
            logger.info(f"Closed session '{session.name}' (id: {session_id})")
        except Exception as e:
            logger.warning(f"Error closing session: {e}")

        return True

    def close_all(self) -> None:
        """Close all sessions and stop Playwright."""
        for session_id in list(self._sessions):
            self.close_session(session_id)

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    @property
    def active_sessions(self) -> list[BrowserSession]:
        """List all active sessions."""
        return [s for s in self._sessions.values() if s.is_active]

    @property
    def session_count(self) -> int:
        """Number of active sessions."""
        return len(self.active_sessions)

    def get_session_status(self) -> list[dict[str, Any]]:
        """Get status of all sessions."""
        return [
            {
                "id": s.id,
                "name": s.name,
                "is_active": s.is_active,
                "url": s.url,
                "title": s.title,
            }
            for s in self._sessions.values()
        ]
