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


class ProxyConnectionError(ProxyException):
    """Proxy connection error (renamed to avoid shadowing built-in ConnectionError)"""
    pass


class CircuitBreakerOpen(ProxyException):
    """Circuit breaker is open"""
    pass


class ProxyTimeoutError(ProxyException):
    """Proxy operation timeout (renamed to avoid shadowing built-in TimeoutError)"""
    pass
