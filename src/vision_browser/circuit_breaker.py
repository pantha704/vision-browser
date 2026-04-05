"""Circuit breaker pattern for external API resilience."""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """States for the circuit breaker."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are rejected immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Prevents cascading failures when external APIs are down.

    Wraps API calls and tracks failures. After consecutive failures exceed
    the threshold, the circuit opens and calls fail immediately without
    hitting the API. After a timeout, it transitions to half-open and
    allows one test request through. If that succeeds, the circuit closes.

    Usage:
        breaker = CircuitBreaker(name="vision-api", failure_threshold=5)

        def call_vision_api():
            return breaker.call(
                func=lambda: vision_client.analyze(path, prompt),
            )
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        """
        Args:
            name: Human-readable name for logging.
            failure_threshold: Consecutive failures before opening circuit.
            timeout: Seconds to wait before trying half-open recovery.
            success_threshold: Consecutive successes in half-open to close.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._total_calls = 0
        self._total_failures = 0
        self._total_rejections = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def stats(self) -> dict[str, Any]:
        """Return usage statistics."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_rejections": self._total_rejections,
        }

    def call(self, func: Callable[[], T], **kwargs: Any) -> T:
        """Execute the wrapped function, respecting circuit state.

        Args:
            func: The function to call (should accept no args).
            **kwargs: Ignored (for API compatibility).

        Returns:
            The function's return value.

        Raises:
            CircuitOpenError: If circuit is open and timeout hasn't elapsed.
            Exception: If the function raises and circuit is closed/half-open.
        """
        self._total_calls += 1

        # Check if circuit should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.timeout:
                logger.info(f"[{self.name}] Circuit: OPEN → HALF_OPEN (timeout {self.timeout}s elapsed)")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
            else:
                self._total_rejections += 1
                remaining = self.timeout - elapsed
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. Retry in {remaining:.0f}s.",
                    state=self._state,
                    retry_after=remaining,
                )

        try:
            result = func()
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info(
                    f"[{self.name}] Circuit: HALF_OPEN → CLOSED "
                    f"({self._success_count} consecutive successes)"
                )
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            # Reset failure count on any success in CLOSED state
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            logger.warning(
                f"[{self.name}] Circuit: HALF_OPEN → OPEN "
                f"(failure during recovery test)"
            )
            self._state = CircuitState.OPEN
            self._success_count = 0
        elif self._failure_count >= self.failure_threshold:
            logger.warning(
                f"[{self.name}] Circuit: CLOSED → OPEN "
                f"({self._failure_count} consecutive failures, threshold={self.failure_threshold})"
            )
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset the circuit to closed state."""
        logger.info(f"[{self.name}] Circuit: manual reset to CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""

    def __init__(self, message: str, state: CircuitState, retry_after: float):
        super().__init__(message)
        self.state = state
        self.retry_after = retry_after
