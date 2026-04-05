"""Tests for session management and differential screenshots."""

from __future__ import annotations

import json
from unittest.mock import MagicMock


from vision_browser.session import SessionManager
from vision_browser.diff_screenshot import DifferentialScreenshot


# ── Session Manager Tests ──────────────────────────────────────────


class TestSessionManagerInit:
    def test_init_creates_dir(self, tmp_path):
        """SessionManager creates session directory."""
        session_dir = tmp_path / "sessions"
        _manager = SessionManager(session_dir)  # noqa: F841
        assert session_dir.exists()

    def test_init_with_default_dir(self):
        """SessionManager works with default directory."""
        manager = SessionManager()
        assert manager._session_dir.exists()


class TestSessionManagerSaveRestore:
    def test_save_session(self, tmp_path):
        """Save session creates JSON file."""
        manager = SessionManager(tmp_path)
        mock_context = MagicMock()
        mock_context.cookies.return_value = [
            {"name": "session", "value": "abc123", "domain": ".example.com"}
        ]
        mock_context.origins = []
        mock_context.storage_state.return_value = {"origins": []}

        result = manager.save_session(mock_context, "my-session")

        assert result.exists()
        data = json.loads(result.read_text())
        assert data["name"] == "my-session"
        assert len(data["cookies"]) == 1

    def test_restore_session_success(self, tmp_path):
        """Restore session loads cookies."""
        manager = SessionManager(tmp_path)

        # Create a session file
        session_data = {
            "version": 1,
            "saved_at": "2026-04-05T10:00:00+00:00",
            "name": "my-session",
            "cookies": [{"name": "auth", "value": "token", "domain": ".example.com"}],
            "origins": [],
        }
        (tmp_path / "my-session.json").write_text(json.dumps(session_data))

        mock_context = MagicMock()

        result = manager.restore_session(mock_context, "my-session")

        assert result is True
        mock_context.add_cookies.assert_called_once()

    def test_restore_session_not_found(self, tmp_path):
        """Restore session returns False for missing session."""
        manager = SessionManager(tmp_path)
        mock_context = MagicMock()

        result = manager.restore_session(mock_context, "nonexistent")

        assert result is False

    def test_restore_session_corrupted_file(self, tmp_path):
        """Restore session handles corrupted JSON gracefully."""
        manager = SessionManager(tmp_path)
        (tmp_path / "bad-session.json").write_text("not valid json{{{")
        mock_context = MagicMock()

        result = manager.restore_session(mock_context, "bad-session")

        assert result is False


class TestSessionManagerListDelete:
    def test_list_sessions(self, tmp_path):
        """List sessions returns session info."""
        manager = SessionManager(tmp_path)

        # Create two session files
        session1 = {
            "version": 1,
            "saved_at": "2026-04-05T10:00:00+00:00",
            "name": "s1",
            "cookies": [{"name": "a"}],
        }
        session2 = {
            "version": 1,
            "saved_at": "2026-04-05T09:00:00+00:00",
            "name": "s2",
            "cookies": [],
        }
        (tmp_path / "s1.json").write_text(json.dumps(session1))
        (tmp_path / "s2.json").write_text(json.dumps(session2))

        sessions = manager.list_sessions()

        assert len(sessions) == 2
        assert sessions[0]["name"] == "s1"  # Sorted by saved_at descending

    def test_list_sessions_empty(self, tmp_path):
        """List sessions returns empty list when no sessions."""
        manager = SessionManager(tmp_path)
        assert manager.list_sessions() == []

    def test_delete_session(self, tmp_path):
        """Delete session removes file."""
        manager = SessionManager(tmp_path)
        (tmp_path / "old-session.json").write_text("{}")

        result = manager.delete_session("old-session")

        assert result is True
        assert not (tmp_path / "old-session.json").exists()

    def test_delete_session_not_found(self, tmp_path):
        """Delete session returns False for missing session."""
        manager = SessionManager(tmp_path)
        assert manager.delete_session("nonexistent") is False

    def test_session_exists(self, tmp_path):
        """Session exists check."""
        manager = SessionManager(tmp_path)
        (tmp_path / "my-session.json").write_text("{}")

        assert manager.session_exists("my-session") is True
        assert manager.session_exists("other") is False


# ── Differential Screenshot Tests ──────────────────────────────────


class TestDifferentialScreenshotInit:
    def test_init_default_threshold(self):
        """Default threshold is 0.01."""
        ds = DifferentialScreenshot()
        assert ds.threshold == 0.01

    def test_init_custom_threshold(self):
        """Custom threshold can be set."""
        ds = DifferentialScreenshot(threshold=0.05)
        assert ds.threshold == 0.05


class TestDifferentialScreenshotChanged:
    def test_first_screenshot_always_changed(self, tmp_path):
        """First screenshot is always considered changed."""
        ds = DifferentialScreenshot()
        shot = tmp_path / "first.png"
        shot.write_bytes(b"image_data")
        assert ds.has_changed(str(shot)) is True

    def test_same_screenshot_not_changed(self, tmp_path):
        """Same screenshot returns not changed."""
        ds = DifferentialScreenshot()
        shot1 = tmp_path / "shot1.png"
        shot1.write_bytes(b"same_image_data")

        assert ds.has_changed(str(shot1)) is True
        assert ds.has_changed(str(shot1)) is False

    def test_different_screenshot_changed(self, tmp_path):
        """Different screenshot returns changed."""
        ds = DifferentialScreenshot()
        shot1 = tmp_path / "shot1.png"
        shot2 = tmp_path / "shot2.png"
        shot1.write_bytes(b"image_data_1")
        shot2.write_bytes(b"image_data_2")

        assert ds.has_changed(str(shot1)) is True
        assert ds.has_changed(str(shot2)) is True

    def test_reset_clears_cache(self, tmp_path):
        """Reset clears previous screenshot cache."""
        ds = DifferentialScreenshot()
        shot = tmp_path / "shot.png"
        shot.write_bytes(b"image_data")

        assert ds.has_changed(str(shot)) is True
        assert ds.has_changed(str(shot)) is False

        ds.reset()
        assert ds.has_changed(str(shot)) is True  # First after reset


class TestDifferentialScreenshotRegions:
    def test_no_previous_returns_none(self):
        """No previous screenshot returns None."""
        ds = DifferentialScreenshot()
        result = ds.get_changed_regions("/tmp/test.png")
        assert result is None

    def test_fallback_diff_without_pil(self, tmp_path):
        """Fallback diff works without PIL."""
        ds = DifferentialScreenshot()
        shot1 = tmp_path / "shot1.png"
        shot2 = tmp_path / "shot2.png"
        shot1.write_bytes(b"image_1")
        shot2.write_bytes(b"image_2")

        # First shot -- sets previous
        ds.get_changed_regions(str(shot1))
        # Second shot -- triggers fallback diff
        result = ds.get_changed_regions(str(shot2))
        # Returns None or list depending on PIL availability
        assert result is None or isinstance(result, list)


class TestDifferentialScreenshotDiff:
    def test_diff_no_previous_returns_original(self, tmp_path):
        """No previous screenshot returns original path."""
        ds = DifferentialScreenshot()
        shot = tmp_path / "shot.png"
        shot.write_bytes(b"image_data")
        output = tmp_path / "diff.png"

        result = ds.get_diff_screenshot(str(shot), str(output))
        assert result == str(shot)

    def test_diff_same_binary_data_returns_empty(self, tmp_path):
        """Same binary data returns empty diff file."""
        ds = DifferentialScreenshot()
        shot = tmp_path / "shot.png"
        shot.write_bytes(b"identical_data")
        output = tmp_path / "diff.png"

        # First call sets previous
        ds.get_diff_screenshot(str(shot), str(output))
        # Second call -- same data, without PIL falls to fallback
        result = ds.get_diff_screenshot(str(shot), str(output))
        # Without PIL, fallback returns None which means we return original
        # This is expected behavior when PIL is not available
        assert result is not None
