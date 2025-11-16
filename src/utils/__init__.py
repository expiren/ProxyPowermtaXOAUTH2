"""Utility modules and infrastructure"""

from src.utils.connection_pool import SMTPConnectionPool, PooledSMTPConnection
from src.utils.http_pool import HTTPSessionPool
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerManager, CircuitBreakerState
from src.utils.retry import retry_async, retry_on_exception, RetryConfig
from src.utils.rate_limiter import RateLimiter, TokenBucket
from src.utils.exceptions import (
    ProxyException,
    ConfigError,
    AccountError,
    AccountNotFound,
    DuplicateAccount,
    ConnectionError,
    CircuitBreakerOpen,
    RateLimitExceeded,
    TimeoutError,
)

__all__ = [
    # Connection pooling
    'SMTPConnectionPool',
    'PooledSMTPConnection',
    'HTTPSessionPool',
    # Circuit breaker
    'CircuitBreaker',
    'CircuitBreakerManager',
    'CircuitBreakerState',
    # Retry
    'retry_async',
    'retry_on_exception',
    'RetryConfig',
    # Rate limiting
    'RateLimiter',
    'TokenBucket',
    # Exceptions
    'ProxyException',
    'ConfigError',
    'AccountError',
    'AccountNotFound',
    'DuplicateAccount',
    'ConnectionError',
    'CircuitBreakerOpen',
    'RateLimitExceeded',
    'TimeoutError',
]
