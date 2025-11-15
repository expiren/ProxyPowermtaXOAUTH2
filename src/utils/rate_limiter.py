"""Per-account rate limiting"""

import asyncio
import logging
from typing import Dict
from datetime import datetime, UTC

from src.utils.exceptions import RateLimitExceeded

logger = logging.getLogger('xoauth2_proxy')


class TokenBucket:
    """Token bucket rate limiter"""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Max tokens
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens: float = float(capacity)
        self.last_refill: datetime = datetime.now(UTC)
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1, timeout: float = 1.0) -> bool:
        """Acquire tokens, wait if necessary"""
        async with self.lock:
            await self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def _refill(self):
        """Refill bucket based on time elapsed"""
        now: datetime = datetime.now(UTC)
        elapsed = (now - self.last_refill).total_seconds()
        new_tokens = elapsed * self.refill_rate

        self.tokens = min(float(self.capacity), self.tokens + new_tokens)
        self.last_refill = now

    def get_state(self) -> dict:
        """Get bucket state"""
        return {
            'tokens': self.tokens,
            'capacity': self.capacity,
            'refill_rate': self.refill_rate,
        }


class RateLimiter:
    """Per-account rate limiting"""

    def __init__(self, messages_per_hour: int = 10000):
        self.messages_per_hour = messages_per_hour
        self.buckets: Dict[str, TokenBucket] = {}
        self.lock = asyncio.Lock()

        # Messages per hour → tokens per second
        self.refill_rate = messages_per_hour / 3600.0

    async def get_or_create_bucket(self, account_email: str) -> TokenBucket:
        """Get or create bucket for account"""
        async with self.lock:
            if account_email not in self.buckets:
                self.buckets[account_email] = TokenBucket(
                    capacity=self.messages_per_hour,
                    refill_rate=self.refill_rate,
                )
            return self.buckets[account_email]

    async def check_rate_limit(self, account_email: str, tokens: int = 1) -> bool:
        """Check if account can send (non-blocking check)"""
        bucket = await self.get_or_create_bucket(account_email)
        # Refill and check without waiting
        await bucket._refill()
        return bucket.tokens >= tokens

    async def acquire(self, account_email: str, tokens: int = 1) -> bool:
        """Acquire tokens for account"""
        bucket = await self.get_or_create_bucket(account_email)
        success = await bucket.acquire(tokens)

        if not success:
            remaining = bucket.capacity - bucket.tokens
            logger.warning(
                f"[RateLimiter] Rate limit exceeded for {account_email} "
                f"(need {tokens}, have {bucket.tokens:.2f})"
            )
            raise RateLimitExceeded(
                f"Rate limit exceeded for {account_email}"
            )

        return True

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            'accounts': len(self.buckets),
            'buckets': {
                email: bucket.get_state()
                for email, bucket in self.buckets.items()
            },
        }
