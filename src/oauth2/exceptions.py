"""OAuth2-specific exceptions"""

from src.utils.exceptions import ProxyException


class OAuth2Error(ProxyException):
    """Base OAuth2 error"""
    pass


class TokenRefreshError(OAuth2Error):
    """Token refresh failed"""
    pass


class InvalidToken(OAuth2Error):
    """Invalid OAuth2 token"""
    pass


class InvalidGrant(OAuth2Error):
    """Invalid grant (e.g., refresh token expired)"""
    pass


class ServiceUnavailable(OAuth2Error):
    """OAuth2 service unavailable"""
    pass


class ProviderError(OAuth2Error):
    """Provider-specific error"""
    pass
