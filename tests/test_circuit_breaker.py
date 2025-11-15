"""Tests for circuit breaker module"""

import unittest
import asyncio
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerState


class TestCircuitBreaker(unittest.TestCase):
    """Test CircuitBreaker state machine"""

    def setUp(self):
        """Create test circuit breaker"""
        self.cb = CircuitBreaker(
            name="test_breaker",
            failure_threshold=3,
            recovery_timeout=10,
            half_open_max_calls=2
        )

    def test_initial_state(self):
        """Test circuit breaker starts in CLOSED state"""
        self.assertEqual(self.cb.state, CircuitBreakerState.CLOSED)

    def test_closed_to_open_transition(self):
        """Test transition from CLOSED to OPEN after failures"""
        # Simulate 3 failures
        for _ in range(3):
            self.cb.record_failure()

        self.assertEqual(self.cb.state, CircuitBreakerState.OPEN)

    def test_open_to_half_open_transition(self):
        """Test transition from OPEN to HALF_OPEN after timeout"""
        # Force OPEN state
        for _ in range(3):
            self.cb.record_failure()

        self.assertEqual(self.cb.state, CircuitBreakerState.OPEN)

        # Manually set recovery time to past
        self.cb.open_at = asyncio.get_event_loop().time() - 15

        # Should transition to HALF_OPEN
        self.cb.check_timeout()
        self.assertEqual(self.cb.state, CircuitBreakerState.HALF_OPEN)

    def test_half_open_to_closed_on_success(self):
        """Test transition from HALF_OPEN to CLOSED on success"""
        # Force HALF_OPEN state
        self.cb.state = CircuitBreakerState.HALF_OPEN
        self.cb.half_open_calls = 0

        # Record success
        self.cb.record_success()

        self.assertEqual(self.cb.state, CircuitBreakerState.CLOSED)

    def test_is_available_closed(self):
        """Test circuit breaker is available when CLOSED"""
        self.assertTrue(self.cb.is_available())

    def test_is_not_available_open(self):
        """Test circuit breaker is not available when OPEN"""
        # Force OPEN state
        for _ in range(3):
            self.cb.record_failure()

        self.assertFalse(self.cb.is_available())

    def test_half_open_limited_calls(self):
        """Test HALF_OPEN state limits calls"""
        self.cb.state = CircuitBreakerState.HALF_OPEN
        self.cb.half_open_calls = 0

        # First call should be available
        self.assertTrue(self.cb.is_available())
        self.cb.half_open_calls += 1

        # Second call should be available
        self.assertTrue(self.cb.is_available())
        self.cb.half_open_calls += 1

        # Third call should not be available (limit is 2)
        self.assertFalse(self.cb.is_available())


class TestCircuitBreakerIntegration(unittest.TestCase):
    """Test circuit breaker in realistic scenarios"""

    def test_failure_recovery_cycle(self):
        """Test complete failure and recovery cycle"""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=5
        )

        # Start in CLOSED state
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

        # First failure
        cb.record_failure()
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

        # Second failure triggers transition
        cb.record_failure()
        self.assertEqual(cb.state, CircuitBreakerState.OPEN)

        # Should not be available
        self.assertFalse(cb.is_available())

        # Simulate timeout
        cb.open_at = asyncio.get_event_loop().time() - 6
        cb.check_timeout()

        # Should be HALF_OPEN now
        self.assertEqual(cb.state, CircuitBreakerState.HALF_OPEN)

        # Recovery success
        cb.record_success()
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)
        self.assertTrue(cb.is_available())


if __name__ == '__main__':
    unittest.main()
