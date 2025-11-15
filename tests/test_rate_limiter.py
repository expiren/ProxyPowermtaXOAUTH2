"""Tests for rate limiting module"""

import unittest
import time
from src.utils.rate_limiter import TokenBucket, RateLimiter


class TestTokenBucket(unittest.TestCase):
    """Test TokenBucket algorithm"""

    def test_token_bucket_creation(self):
        """Test token bucket creation"""
        bucket = TokenBucket(capacity=10, refill_rate=1)
        self.assertEqual(bucket.capacity, 10)
        self.assertEqual(bucket.tokens, 10)

    def test_consume_token(self):
        """Test consuming tokens"""
        bucket = TokenBucket(capacity=10, refill_rate=1)
        self.assertTrue(bucket.consume(1))
        self.assertEqual(bucket.tokens, 9)

    def test_consume_multiple_tokens(self):
        """Test consuming multiple tokens"""
        bucket = TokenBucket(capacity=10, refill_rate=1)
        self.assertTrue(bucket.consume(5))
        self.assertEqual(bucket.tokens, 5)

    def test_consume_more_than_available(self):
        """Test consuming more tokens than available"""
        bucket = TokenBucket(capacity=10, refill_rate=1)
        bucket.tokens = 5
        self.assertFalse(bucket.consume(10))
        self.assertEqual(bucket.tokens, 5)  # Should not change

    def test_token_refill(self):
        """Test token refilling over time"""
        bucket = TokenBucket(capacity=10, refill_rate=10)  # 10 tokens per second
        bucket.tokens = 0
        bucket.last_refill = time.time() - 1  # 1 second ago

        bucket.refill()
        self.assertEqual(bucket.tokens, 10)

    def test_refill_respects_capacity(self):
        """Test that refill respects max capacity"""
        bucket = TokenBucket(capacity=10, refill_rate=100)
        bucket.tokens = 5
        bucket.last_refill = time.time() - 1

        bucket.refill()
        self.assertEqual(bucket.tokens, 10)  # Should not exceed capacity


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter"""

    def test_rate_limiter_creation(self):
        """Test rate limiter creation"""
        limiter = RateLimiter(max_messages_per_hour=1000)
        self.assertEqual(limiter.max_messages_per_hour, 1000)

    def test_allow_message_under_limit(self):
        """Test allowing message under rate limit"""
        limiter = RateLimiter(max_messages_per_hour=1000)
        self.assertTrue(limiter.check_rate_limit("test@example.com"))

    def test_rate_limit_per_account(self):
        """Test rate limiting per account"""
        limiter = RateLimiter(max_messages_per_hour=2)
        email = "test@example.com"

        # First message should be allowed
        self.assertTrue(limiter.check_rate_limit(email))

        # Second message should be allowed
        self.assertTrue(limiter.check_rate_limit(email))

        # Third message should be rejected
        self.assertFalse(limiter.check_rate_limit(email))

    def test_different_accounts_independent(self):
        """Test that different accounts have independent limits"""
        limiter = RateLimiter(max_messages_per_hour=2)

        email1 = "test1@example.com"
        email2 = "test2@example.com"

        # Account 1 uses up limit
        limiter.check_rate_limit(email1)
        limiter.check_rate_limit(email1)
        self.assertFalse(limiter.check_rate_limit(email1))

        # Account 2 should still be allowed
        self.assertTrue(limiter.check_rate_limit(email2))

    def test_reset_limits(self):
        """Test resetting rate limits"""
        limiter = RateLimiter(max_messages_per_hour=2)
        email = "test@example.com"

        # Use up limit
        limiter.check_rate_limit(email)
        limiter.check_rate_limit(email)
        self.assertFalse(limiter.check_rate_limit(email))

        # Reset
        limiter.reset_limit(email)

        # Should be allowed again
        self.assertTrue(limiter.check_rate_limit(email))


if __name__ == '__main__':
    unittest.main()
