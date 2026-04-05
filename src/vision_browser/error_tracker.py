"""Error tracking and diagnostics for post-mortem analysis."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ErrorRecord:
    """Single error event with full context."""

    timestamp: float
    phase: str  # "navigation", "screenshot", "analysis", "execution", "verification"
    error_type: str  # Exception class name
    message: str
    url: str = ""
    title: str = ""
    turn: int = 0
    action: dict | None = None
    element_refs: int = 0
    retry_count: int = 0
    stack_trace: str = ""
    recoverable: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class ErrorTracker:
    """Tracks all errors during a session for post-mortem analysis.

    Writes to a JSON file at the end of the session for debugging.
    """

    def __init__(self, log_path: str | None = None):
        self._errors: list[ErrorRecord] = []
        self._log_path = Path(log_path) if log_path else None

    def record(
        self,
        phase: str,
        error: Exception,
        url: str = "",
        title: str = "",
        turn: int = 0,
        action: dict | None = None,
        element_refs: int = 0,
        retry_count: int = 0,
        recoverable: bool = True,
    ) -> None:
        """Record an error with full context."""
        record = ErrorRecord(
            timestamp=time.time(),
            phase=phase,
            error_type=type(error).__name__,
            message=str(error),
            url=url,
            title=title,
            turn=turn,
            action=action,
            element_refs=element_refs,
            retry_count=retry_count,
            stack_trace=self._format_traceback(error),
            recoverable=recoverable,
        )
        self._errors.append(record)

        # Log immediately for real-time visibility
        if recoverable:
            logger.warning(f"[{phase}] {type(error).__name__}: {error}")
        else:
            logger.error(f"[{phase}] FATAL {type(error).__name__}: {error}")

    @property
    def error_count(self) -> int:
        return len(self._errors)

    @property
    def fatal_count(self) -> int:
        return sum(1 for e in self._errors if not e.recoverable)

    @property
    def phases_with_errors(self) -> set[str]:
        return {e.phase for e in self._errors}

    def summary(self) -> dict[str, Any]:
        """Return a summary of all errors."""
        by_phase: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for e in self._errors:
            by_phase[e.phase] = by_phase.get(e.phase, 0) + 1
            by_type[e.error_type] = by_type.get(e.error_type, 0) + 1

        return {
            "total_errors": self.error_count,
            "fatal_errors": self.fatal_count,
            "recoverable_errors": self.error_count - self.fatal_count,
            "by_phase": by_phase,
            "by_type": by_type,
            "errors": [e.to_dict() for e in self._errors],
        }

    def save_report(self, path: str | None = None) -> str:
        """Save error report to JSON file."""
        output_path = Path(path) if path else self._log_path
        if output_path is None:
            output_path = Path("/tmp/vision-browser-error-report.json")

        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary": self.summary(),
        }
        output_path.write_text(json.dumps(report, indent=2))
        logger.info(f"Error report saved to: {output_path}")
        return str(output_path)

    def print_summary(self) -> None:
        """Print a human-readable error summary."""
        from rich.console import Console

        console = Console()
        if not self._errors:
            console.print("[green]✓ No errors recorded[/green]")
            return

        console.print(
            f"\n[bold red]Error Summary ({self.error_count} total, {self.fatal_count} fatal)[/bold red]"
        )

        # Group by phase
        from collections import Counter

        by_phase = Counter(e.phase for e in self._errors)
        for phase, count in by_phase.most_common():
            fatal = sum(
                1 for e in self._errors if e.phase == phase and not e.recoverable
            )
            icon = "💀" if fatal > 0 else "⚠️"
            console.print(f"  {icon} {phase}: {count} errors ({fatal} fatal)")

        # Show most recent errors
        console.print("\n[bold]Most Recent Errors:[/bold]")
        for e in self._errors[-5:]:
            icon = "💀" if not e.recoverable else "⚠️"
            console.print(
                f"  {icon} Turn {e.turn}: [{e.phase}] {e.error_type}: {e.message[:80]}"
            )

    @staticmethod
    def _format_traceback(error: Exception) -> str:
        """Format exception traceback as string."""
        import traceback

        return "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
