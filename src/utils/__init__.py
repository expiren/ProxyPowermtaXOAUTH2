"""Utility modules and infrastructure"""

from src.utils.http_pool import HTTPSessionPool
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerManager, CircuitBreakerState
from src.utils.retry import retry_async, retry_on_exception, RetryConfig
from src.utils.network import (
    get_server_ips,
    get_public_server_ips,
    is_reserved_ip,
    validate_ip_address,
    is_ip_available_on_server,
    test_source_ip_binding,
)
from src.utils.exceptions import (
    ProxyException,
    ConfigError,
    AccountError,
    AccountNotFound,
    DuplicateAccount,
    ProxyConnectionError,
    CircuitBreakerOpen,
    ProxyTimeoutError,
)

__all__ = [
    # HTTP pooling
    'HTTPSessionPool',
    # Circuit breaker
    'CircuitBreaker',
    'CircuitBreakerManager',
    'CircuitBreakerState',
    # Retry
    'retry_async',
    'retry_on_exception',
    'RetryConfig',
    # Network utilities
    'get_server_ips',
    'get_public_server_ips',
    'is_reserved_ip',
    'validate_ip_address',
    'is_ip_available_on_server',
    'test_source_ip_binding',
    # Exceptions
    'ProxyException',
    'ConfigError',
    'AccountError',
    'AccountNotFound',
    'DuplicateAccount',
    'ProxyConnectionError',
    'CircuitBreakerOpen',
    'ProxyTimeoutError',
]
