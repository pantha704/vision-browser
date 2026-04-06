"""Persistent session management -- save and restore browser state across runs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext

logger = logging.getLogger(__name__)

SESSION_DIR = Path.home() / ".local" / "share" / "vision-browser" / "sessions"


class SessionManager:
    """Manages browser session persistence across automation runs.

    Saves and restores:
    - Cookies
    - LocalStorage (per origin)
    - Session metadata (last URL, timestamp)
    """

    def __init__(self, session_dir: Path | None = None):
        self._session_dir = session_dir or SESSION_DIR
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, context: BrowserContext, session_name: str) -> Path:
        """Save browser session state to disk.

        Args:
            context: The Playwright BrowserContext to save.
            session_name: Name for this session.

        Returns:
            Path to the saved session file.
        """
        session_file = self._session_dir / f"{session_name}.json"

        session_data: dict[str, Any] = {
            "version": 1,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "name": session_name,
            "cookies": context.cookies(),
            "origins": [],
        }

        # Save local storage per origin
        try:
            for origin in context.origins:
                storage = context.storage_state()
                for o in storage.get("origins", []):
                    if o.get("origin") == origin:
                        session_data["origins"].append(o)
        except Exception as e:
            logger.debug(f"Could not save storage state: {e}")

        # Also use Playwright's built-in storage_state if available
        try:
            storage = context.storage_state()
            session_data["storage_state"] = storage
        except Exception as e:
            logger.debug(f"Could not save full storage state: {e}")

        session_file.write_text(json.dumps(session_data, indent=2))
        logger.info(
            f"Session saved: {session_file} ({len(session_data['cookies'])} cookies)"
        )
        return session_file

    def restore_session(self, context: BrowserContext, session_name: str) -> bool:
        """Restore browser session state from disk.

        Args:
            context: The Playwright BrowserContext to restore into.
            session_name: Name of the session to restore.

        Returns:
            True if session was restored successfully.
        """
        session_file = self._session_dir / f"{session_name}.json"

        if not session_file.exists():
            logger.debug(f"Session not found: {session_name}")
            return False

        try:
            session_data = json.loads(session_file.read_text())

            # Restore cookies
            cookies = session_data.get("cookies", [])
            if cookies:
                context.add_cookies(cookies)
                logger.info(
                    f"Restored {len(cookies)} cookies from session '{session_name}'"
                )

            # Restore localStorage/IndexedDB via JS evaluation
            # (storage_state can only be set at context creation, not on existing context)
            storage_state = session_data.get("storage_state")
            if storage_state and storage_state.get("origins"):
                origins_restored = 0
                for origin_data in storage_state["origins"]:
                    origin = origin_data.get("origin", "")
                    local_storage = origin_data.get("localStorage", [])
                    if origin and local_storage:
                        try:
                            # Restore localStorage via JS on each origin's page
                            context.add_init_script(
                                f"""
                                (() => {{
                                    const items = {json.dumps(local_storage)};
                                    items.forEach(([key, value]) => {{
                                        try {{ localStorage.setItem(key, value); }}
                                        catch (e) {{}}
                                    }});
                                }})();
                                """
                            )
                            origins_restored += 1
                        except Exception as e:
                            logger.debug(f"Could not restore localStorage for {origin}: {e}")

                if origins_restored:
                    logger.info(
                        f"Queued localStorage restore for {origins_restored} origins "
                        f"from session '{session_name}'"
                    )

            return True

        except Exception as e:
            logger.warning(f"Failed to restore session '{session_name}': {e}")
            return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all saved sessions.

        Returns:
            List of session info dicts with name, saved_at, cookie_count.
        """
        sessions = []
        for session_file in self._session_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text())
                sessions.append(
                    {
                        "name": data.get("name", session_file.stem),
                        "saved_at": data.get("saved_at", "unknown"),
                        "cookie_count": len(data.get("cookies", [])),
                        "path": str(session_file),
                    }
                )
            except Exception:
                sessions.append(
                    {
                        "name": session_file.stem,
                        "saved_at": "unknown",
                        "cookie_count": 0,
                        "path": str(session_file),
                    }
                )
        return sorted(sessions, key=lambda s: s["saved_at"], reverse=True)

    def delete_session(self, session_name: str) -> bool:
        """Delete a saved session.

        Args:
            session_name: Name of the session to delete.

        Returns:
            True if session was deleted.
        """
        session_file = self._session_dir / f"{session_name}.json"
        if session_file.exists():
            session_file.unlink()
            logger.info(f"Deleted session: {session_name}")
            return True
        return False

    def session_exists(self, session_name: str) -> bool:
        """Check if a session exists."""
        return (self._session_dir / f"{session_name}.json").exists()
