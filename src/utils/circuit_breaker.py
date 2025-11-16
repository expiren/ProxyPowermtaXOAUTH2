"""Circuit breaker pattern for handling upstream failures"""

import asyncio
import logging
from typing import Callable, Any, Optional, Dict
from enum import Enum
from datetime import datetime, UTC

from src.utils.exceptions import CircuitBreakerOpen
from src.smtp.constants import (
    DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
    DEFAULT_CIRCUIT_BREAKER_TIMEOUT,
)

logger = logging.getLogger('xoauth2_proxy')


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """Circuit breaker for upstream service failures"""

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        recovery_timeout: int = DEFAULT_CIRCUIT_BREAKER_TIMEOUT,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.success_count = 0
        self.lock = asyncio.Lock()

        logger.info(
            f"[CircuitBreaker] {name} initialized "
            f"(threshold={failure_threshold}, timeout={recovery_timeout}s)"
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker

        Args:
            func: Async function to execute
            *args, **kwargs: Arguments for function

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        # ✅ FAST PATH: Check state without lock (99.9% of calls in healthy system)
        # Reading self.state is atomic for Enum types in Python
        current_state = self.state

        if current_state == CircuitBreakerState.OPEN:
            # SLOW PATH: Acquire lock to check recovery
            async with self.lock:
                # Double-check state (may have changed while waiting for lock)
                if self.state == CircuitBreakerState.OPEN:
                    # Check if recovery timeout has elapsed
                    if self._should_attempt_recovery():
                        self.state = CircuitBreakerState.HALF_OPEN
                        logger.info(f"[CircuitBreaker] {self.name} moving to HALF_OPEN state")
                    else:
                        raise CircuitBreakerOpen(
                            f"Circuit breaker {self.name} is OPEN"
                        )

        # Execute function (no lock held during execution - critical for throughput!)
        try:
            result = await func(*args, **kwargs)

            # Success - update state only if needed (avoid lock in common case)
            if current_state == CircuitBreakerState.HALF_OPEN:
                async with self.lock:
                    if self.state == CircuitBreakerState.HALF_OPEN:
                        self.success_count += 1
                        # Allow 2 successes before closing
                        if self.success_count >= 2:
                            self._close()
            elif self.failure_count > 0:
                # Reset failure count on success (only if non-zero)
                async with self.lock:
                    self.failure_count = 0

            return result

        except Exception as e:
            # Failure - always update state
            async with self.lock:
                self.failure_count += 1
                self.last_failure_time = datetime.now(UTC)

                if self.failure_count >= self.failure_threshold:
                    self._open()
                elif self.state == CircuitBreakerState.HALF_OPEN:
                    # Failed during recovery attempt
                    self._open()

            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has elapsed to attempt recovery"""
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.now(UTC) - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _open(self):
        """Open the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        logger.warning(
            f"[CircuitBreaker] {self.name} OPENED after {self.failure_count} failures"
        )

    def _close(self):
        """Close the circuit breaker"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"[CircuitBreaker] {self.name} CLOSED and recovered")

    def get_state(self) -> dict:
        """Get circuit breaker state"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


class CircuitBreakerManager:
    """Manages multiple circuit breakers"""

    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self.lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        failure_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        recovery_timeout: int = DEFAULT_CIRCUIT_BREAKER_TIMEOUT,
    ) -> CircuitBreaker:
        """Get or create circuit breaker"""
        async with self.lock:
            if name not in self.breakers:
                self.breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                )
            return self.breakers[name]

    def get_stats(self) -> dict:
        """Get all circuit breaker states"""
        return {
            name: breaker.get_state()
            for name, breaker in self.breakers.items()
        }
