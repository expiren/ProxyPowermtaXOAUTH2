"""Retry logic with exponential backoff and jitter"""

import asyncio
import random
import logging
from typing import Callable, Any, Type, Tuple, Optional
from functools import wraps

from src.smtp.constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_RETRY_MAX_DELAY,
)

logger = logging.getLogger('xoauth2_proxy')


class RetryConfig:
    """Retry configuration"""

    def __init__(
        self,
        max_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        max_delay: int = DEFAULT_RETRY_MAX_DELAY,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt with exponential backoff"""
        delay = min(
            self.backoff_factor ** attempt,
            float(self.max_delay)
        )

        if self.jitter:
            # Add random jitter (0-100% of delay)
            delay = delay * random.uniform(0.5, 1.5)

        return delay


async def retry_async(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> Any:
    """
    Execute async function with retry logic

    Args:
        func: Async function to execute
        config: RetryConfig object
        *args, **kwargs: Arguments to pass to function

    Returns:
        Result from function

    Raises:
        Last exception if all retries exhausted
        ValueError if max_attempts < 1
    """
    if config is None:
        config = RetryConfig()

    # Validate config
    if config.max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_attempts - 1:
                delay = config.get_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed. Last error: {e}"
                )

    raise last_exception


def retry_on_exception(config: Optional[RetryConfig] = None):
    """
    Decorator for async functions with automatic retry

    Example:
        @retry_on_exception(RetryConfig(max_attempts=3))
        async def do_something():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, *args, config=config, **kwargs)
        return wrapper

    return decorator


class RetryableException(Exception):
    """Mark exception as retryable"""
    pass


class NonRetryableException(Exception):
    """Mark exception as non-retryable"""
    pass
