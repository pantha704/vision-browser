"""agent-browser CLI wrapper — handles navigation, screenshots, interactions."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

from vision_browser.config import BrowserConfig
from vision_browser.exceptions import (
    ActionExecutionError,
    BrowserError,
    BrowserNotInstalledError,
    TimeoutError,
)


# Allowed keyboard keys for press action
_ALLOWED_KEYS = frozenset({
    "Enter", "Tab", "Escape", "Backspace", "Delete", "ArrowLeft", "ArrowRight",
    "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown", "Space",
    "Control+a", "Control+c", "Control+v", "Control+x", "Control+z",
    "Meta+a", "Meta+c", "Meta+v", "Meta+x",
})

# Navigation timeout per operation (ms)
_NAV_TIMEOUT_MS = 60_000
_SCREENSHOT_TIMEOUT_MS = 30_000
_SNAPSHOT_TIMEOUT_MS = 15_000


class AgentBrowser:
    """Wraps the agent-browser CLI for vision-driven automation."""

    def __init__(self, cfg: BrowserConfig | None = None):
        self.cfg = cfg or BrowserConfig()
        self._check_installed()

    def _build_open_args(self) -> list[str]:
        """Build args for the open command based on config."""
        args = []
        if self.cfg.cdp_url:
            # CDP mode: don't add --args, just use --cdp
            args.extend(["--cdp", self.cfg.cdp_url])
        else:
            # Local Chrome mode: needs --no-sandbox
            args.append("--args")
            args.append("--no-sandbox")
            if self.cfg.session_name:
                args = ["--session-name", self.cfg.session_name, "--args", "--no-sandbox"]
        return args

    def _check_installed(self) -> None:
        """Verify agent-browser is on PATH."""
        if shutil.which("agent-browser") is None:
            raise BrowserNotInstalledError(
                "agent-browser not found on PATH. Install it: npm i -g agent-browser && agent-browser install"
            )

    def _run(
        self,
        args: list[str],
        timeout_ms: int | None = None,
    ) -> str:
        """Run agent-browser command, return stdout. Raises BrowserError on failure."""
        cmd = ["agent-browser"] + args
        timeout = (timeout_ms or self.cfg.timeout_ms) / 1000
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(
                f"agent-browser {' '.join(args[:3])} timed out after {timeout:.0f}s"
            ) from e

        if result.returncode != 0:
            raise BrowserError(
                f"agent-browser failed (exit {result.returncode}): {result.stderr.strip()[:500]}"
            )
        return result.stdout

    # ── Navigation ──────────────────────────────────────────────────

    def open(self, url: str) -> None:
        """Navigate to URL. Validates http/https only."""
        _validate_url(url)
        extra_args = self._build_open_args()
        cmd = ["open"] + extra_args + [url]
        self._run(cmd, timeout_ms=_NAV_TIMEOUT_MS)

    def close(self) -> None:
        """Close browser. Skipped when using CDP (user controls the browser)."""
        if self.cfg.cdp_url:
            return  # Don't close user's Brave
        try:
            self._run(["close"])
        except BrowserError:
            pass  # Browser may already be closed

    # ── Screenshots ─────────────────────────────────────────────────

    def screenshot(
        self,
        path: str,
        *,
        annotate: bool = False,
        full_page: bool = False,
    ) -> dict[str, Any]:
        """Take screenshot. If annotate, parse legend into badge→ref mapping.

        Returns dict with 'path' and optionally 'refs': dict[int, str] mapping
        badge numbers to element refs (e.g. {3: '@e3', 5: '@e5'}).
        """
        args = ["screenshot"]
        if annotate:
            args.append("--annotate")
        if full_page:
            args.append("--full")
        args.append(path)
        output = self._run(args, timeout_ms=_SCREENSHOT_TIMEOUT_MS)

        result: dict[str, Any] = {"path": path}
        if annotate:
            # Strip ANSI color codes, then parse legend lines
            ansi_clean = re.sub(r"\x1b\[[0-9;]*m", "", output)
            refs: dict[int, str] = {}
            legend_lines: list[str] = []
            for line in ansi_clean.split("\n"):
                line = line.strip()
                if line.startswith("[") and "@" in line:
                    m = re.match(r"\[(\d+)\]\s+(@\w+)\s+(.*)", line)
                    if m:
                        badge_num = int(m.group(1))
                        ref = m.group(2)
                        desc = m.group(3).strip().strip('"')
                        refs[badge_num] = ref
                        # Include role+label in legend for the prompt
                        legend_lines.append(f"  [{badge_num}] {ref} ({desc})")
            result["refs"] = refs
            result["legend"] = legend_lines
        return result

    # ── Snapshot ────────────────────────────────────────────────────

    def snapshot(self, *, interactive: bool = True) -> str:
        """Get page snapshot with element refs."""
        args = ["snapshot"]
        if interactive:
            args.append("-i")
        return self._run(args, timeout_ms=_SNAPSHOT_TIMEOUT_MS)

    # ── Interaction ─────────────────────────────────────────────────

    def click(self, ref: str) -> None:
        """Click element by ref (e.g. @e12)."""
        self._run(["click", ref])

    def fill(self, ref: str, text: str) -> None:
        """Clear and type into element. Uses click + type for JS compatibility."""
        # Click first to focus (ensures real keypress events fire)
        self._run(["click", ref])
        # Then type text (sends real keyboard events, triggers JS listeners)
        self._run(["type", ref, text])

    def type_into(self, ref: str, text: str) -> None:
        """Type text into element using real keypresses (triggers JS events)."""
        # First click to focus
        self._run(["click", ref])
        # Then type character by character
        self._run(["type", ref, text])

    def select(self, ref: str, option: str) -> None:
        """Select dropdown option."""
        self._run(["select", ref, option])

    def press(self, key: str) -> None:
        """Press keyboard key. Validated against allowlist."""
        if key not in _ALLOWED_KEYS:
            raise ActionExecutionError(f"Disallowed key press: {key!r}")
        self._run(["press", key])

    def scroll(self, direction: str = "down", amount: int = 500) -> None:
        """Scroll page."""
        self._run(["scroll", direction, str(amount)])

    def find_and_click(self, text: str) -> None:
        """Find element by visible text and click it (semantic locator)."""
        self._run(["find", "text", text, "click"])

    def submit_search(self) -> None:
        """Submit a search by triggering form submission via JS."""
        # Try multiple approaches
        try:
            # Approach 1: Click the first submit/input[type=submit] button
            self._run(["eval", "--stdin"], timeout_ms=5000)
        except Exception:
            pass
        # Approach 2: Use keyboard press Enter
        try:
            self._run(["keyboard", "press", "Enter"])
        except Exception:
            pass

    def eval(self, js: str) -> str:
        """Execute JavaScript in the browser context."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(js)
            f.flush()
            return self._run(["eval", f.name])

    def wait(self, *args: str) -> None:
        """Wait for element / network idle."""
        self._run(["wait"] + list(args))

    # ── Info ────────────────────────────────────────────────────────

    def get_title(self) -> str:
        """Get page title."""
        return self._run(["get", "title"]).strip()

    def get_url(self) -> str:
        """Get current URL."""
        return self._run(["get", "url"]).strip()

    # ── Action Execution ────────────────────────────────────────────

    def execute_action(self, action: dict) -> None:
        """Execute a single action dict from the vision model."""
        act = action.get("action", "")
        element = action.get("element")

        match act:
            case "click":
                ref = _element_to_ref(element)
                self.click(ref)
            case "fill" | "type":
                ref = _element_to_ref(element)
                text = action.get("text", "")
                if len(text) > 5000:
                    raise ActionExecutionError("fill text too long (>5000 chars)")
                self.fill(ref, text)
            case "select":
                ref = _element_to_ref(element)
                self.select(ref, action.get("option", ""))
            case "press" | "key":
                self.press(action.get("key", "Enter"))
            case "scroll":
                self.scroll(
                    action.get("direction", "down"),
                    action.get("amount", 500),
                )
            case "wait":
                self.wait("--load", "networkidle")
            case "navigate" | "open":
                url = action.get("url", "")
                _validate_url(url)
                self.open(url)
            case _:
                raise ActionExecutionError(f"Unknown action: {act!r}")

    def execute_batch(self, actions: list[dict]) -> int:
        """Execute multiple actions. Returns count of successful executions."""
        success = 0
        for i, action in enumerate(actions):
            try:
                self.execute_action(action)
                success += 1
            except Exception as e:
                # Log but continue executing remaining actions
                from vision_browser.exceptions import ActionExecutionError
                if isinstance(e, ActionExecutionError):
                    raise
                # Non-critical failures (e.g. click on disappeared element) continue
                continue
        return success


def _element_to_ref(element: int | str | None) -> str:
    """Convert element number or ref string to a valid @ref."""
    if element is None:
        raise ActionExecutionError("Action missing element reference")
    if isinstance(element, int):
        return f"@e{element}"
    s = str(element).strip()
    if not s.startswith("@"):
        s = f"@{s}"
    return s


def _validate_url(url: str) -> None:
    """Validate URL is http/https only."""
    if not url:
        raise ActionExecutionError("Empty URL")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ActionExecutionError(
            f"Only http/https URLs allowed, got: {url[:80]}"
        )
