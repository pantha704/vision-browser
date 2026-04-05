"""Tests for the circuit breaker pattern."""

from __future__ import annotations

import time

import pytest

from vision_browser.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class TestCircuitBreakerBasic:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_successful_call_resets_failures(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb._failure_count = 2
        cb.call(lambda: "ok")
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, timeout=60.0)
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        # Should reject immediately
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.call(lambda: "ok")
        assert exc_info.value.retry_after > 0
        assert exc_info.value.state == CircuitState.OPEN

    def test_stats_tracking(self):
        cb = CircuitBreaker(name="test")
        cb.call(lambda: "ok")
        cb.call(lambda: "ok")
        stats = cb.stats
        assert stats["total_calls"] == 2
        assert stats["total_failures"] == 0
        assert stats["total_rejections"] == 0


class TestCircuitBreakerRecovery:
    def test_half_open_after_timeout(self, monkeypatch):
        cb = CircuitBreaker(name="test", failure_threshold=2, timeout=5.0)
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.state == CircuitState.OPEN

        # Simulate time passing
        monkeypatch.setattr(time, "monotonic", lambda: cb._last_failure_time + 10.0)

        # Next call should transition to half-open and succeed
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.HALF_OPEN  # Needs 2 successes to close

    def test_closes_after_success_threshold(self, monkeypatch):
        cb = CircuitBreaker(
            name="test", failure_threshold=2, timeout=5.0, success_threshold=2
        )
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))

        # Simulate timeout
        monkeypatch.setattr(time, "monotonic", lambda: cb._last_failure_time + 10.0)

        # Two successes should close it
        cb.call(lambda: "ok1")
        assert cb.state == CircuitState.HALF_OPEN
        cb.call(lambda: "ok2")
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self, monkeypatch):
        cb = CircuitBreaker(name="test", failure_threshold=2, timeout=5.0)
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))

        # Simulate timeout
        monkeypatch.setattr(time, "monotonic", lambda: cb._last_failure_time + 10.0)

        # Failure in half-open reopens
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("still broken")))
        assert cb.state == CircuitState.OPEN

    def test_manual_reset(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_repr(self):
        cb = CircuitBreaker(name="api", failure_threshold=5)
        cb._failure_count = 3
        assert "api" in repr(cb)
        assert "closed" in repr(cb)
        assert "3/5" in repr(cb)
