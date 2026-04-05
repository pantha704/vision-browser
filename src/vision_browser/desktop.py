"""Desktop control fallback — scrot + xdotool for non-browser apps."""

from __future__ import annotations

import subprocess

from vision_browser.config import DesktopConfig
from vision_browser.exceptions import ActionExecutionError

# Allowed keys for xdotool key press
_ALLOWED_DESKTOP_KEYS = frozenset(
    {
        "Return",
        "Enter",
        "Tab",
        "Escape",
        "BackSpace",
        "Delete",
        "Left",
        "Right",
        "Up",
        "Down",
        "Home",
        "End",
        "Page_Up",
        "Page_Down",
        "Control_L+a",
        "Control_L+c",
        "Control_L+v",
        "Control_L+x",
        "Alt_L+Tab",
        "Alt_L+F4",
    }
)


class DesktopController:
    """Controls the real desktop via scrot + xdotool."""

    def __init__(self, cfg: DesktopConfig | None = None):
        self.cfg = cfg or DesktopConfig()

    def screenshot(self, path: str) -> str:
        """Take full desktop screenshot."""
        subprocess.run([self.cfg.screenshot_cmd, path], check=True)
        return path

    def click(self, x: int, y: int) -> None:
        """Move mouse and click at coordinates."""
        if x < 0 or y < 0:
            raise ActionExecutionError(f"Invalid click coordinates: ({x}, {y})")
        subprocess.run(
            ["xdotool", "mousemove", str(x), str(y), "click", "1"],
            check=True,
        )

    def type_text(self, text: str, delay: int | None = None) -> None:
        """Type text via xdotool."""
        if not text:
            raise ActionExecutionError("Empty text to type")
        if len(text) > 5000:
            raise ActionExecutionError("Text too long (>5000 chars)")
        d = delay if delay is not None else self.cfg.type_delay_ms
        subprocess.run(
            ["xdotool", "type", "--delay", str(d), "--", text],
            check=True,
        )

    def press_key(self, key: str) -> None:
        """Press a single key. Validated against allowlist."""
        if key not in _ALLOWED_DESKTOP_KEYS:
            raise ActionExecutionError(f"Disallowed desktop key: {key!r}")
        subprocess.run(["xdotool", "key", key], check=True)

    def scroll(self, direction: str = "down", amount: int = 5) -> None:
        """Scroll via mouse wheel (4=up, 5=down)."""
        button = 5 if direction == "down" else 4
        for _ in range(max(1, min(amount, 50))):  # cap at 50 scrolls
            subprocess.run(["xdotool", "click", str(button)], check=True)

    def get_mouse_pos(self) -> tuple[int, int]:
        """Get current mouse position."""
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True,
            text=True,
            check=True,
        )
        x = y = 0
        for line in result.stdout.split("\n"):
            if line.startswith("X="):
                x = int(line.split("=")[1])
            elif line.startswith("Y="):
                y = int(line.split("=")[1])
        return x, y
