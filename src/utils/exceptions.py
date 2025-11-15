"""Custom exceptions for XOAUTH2 Proxy"""


class ProxyException(Exception):
    """Base exception for proxy"""
    pass


class ConfigError(ProxyException):
    """Configuration error"""
    pass


class AccountError(ProxyException):
    """Account-related error"""
    pass


class AccountNotFound(AccountError):
    """Account not found"""
    pass


class DuplicateAccount(AccountError):
    """Duplicate account"""
    pass


class ConnectionError(ProxyException):
    """Connection error"""
    pass


class CircuitBreakerOpen(ProxyException):
    """Circuit breaker is open"""
    pass


class RateLimitExceeded(ProxyException):
    """Rate limit exceeded"""
    pass


class TimeoutError(ProxyException):
    """Operation timeout"""
    pass
