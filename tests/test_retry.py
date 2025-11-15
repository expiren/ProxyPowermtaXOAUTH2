"""Tests for retry logic"""

import unittest
import asyncio
from src.utils.retry import RetryConfig, retry_on_exception


class TestRetryConfig(unittest.TestCase):
    """Test RetryConfig"""

    def test_default_config(self):
        """Test default retry configuration"""
        config = RetryConfig()
        self.assertEqual(config.max_attempts, 3)
        self.assertEqual(config.initial_delay, 1)
        self.assertEqual(config.max_delay, 60)
        self.assertEqual(config.exponential_base, 2)

    def test_custom_config(self):
        """Test custom retry configuration"""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=120,
            exponential_base=3
        )
        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.initial_delay, 0.5)
        self.assertEqual(config.max_delay, 120)
        self.assertEqual(config.exponential_base, 3)


class TestRetryDecorator(unittest.TestCase):
    """Test @retry_on_exception decorator"""

    def test_success_on_first_attempt(self):
        """Test successful execution on first attempt"""
        call_count = 0

        @retry_on_exception(max_attempts=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    def test_retry_on_exception(self):
        """Test retrying on exception"""
        call_count = 0

        @retry_on_exception(max_attempts=3)
        def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"

        result = failing_then_succeeding()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_max_attempts_exceeded(self):
        """Test that exception is raised after max attempts"""
        call_count = 0

        @retry_on_exception(max_attempts=2, initial_delay=0.01)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            always_failing()

        self.assertEqual(call_count, 2)

    def test_specific_exception_types(self):
        """Test retrying only specific exception types"""
        call_count = 0

        @retry_on_exception(max_attempts=3, exceptions=(ValueError,))
        def specific_exception():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Will retry")
            raise TypeError("Will not retry")

        with self.assertRaises(TypeError):
            specific_exception()

        self.assertEqual(call_count, 2)


if __name__ == '__main__':
    unittest.main()
