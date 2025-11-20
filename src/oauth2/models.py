"""OAuth2 token and cache models"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC


@dataclass
class OAuthToken:
    """OAuth2 token with expiration tracking"""
    access_token: str
    expires_at: datetime
    refresh_token: str = ""
    scope: str = ""
    token_type: str = "Bearer"

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired with buffer (default 5 minutes)"""
        return datetime.now(UTC) >= (self.expires_at - timedelta(seconds=buffer_seconds))

    def expires_in_seconds(self) -> int:
        """Get seconds until expiration"""
        delta = self.expires_at - datetime.now(UTC)
        return max(0, int(delta.total_seconds()))

    def __str__(self) -> str:
        """String representation (safe, no secrets)"""
        return f"OAuthToken(type={self.token_type}, expires_in={self.expires_in_seconds()}s)"


@dataclass
class TokenCache:
    """Cache for OAuth2 tokens with TTL"""
    token: OAuthToken
    cached_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_valid(self, max_age_seconds: int = 3300) -> bool:
        """
        Check if cached token is still valid.

        Default max_age is 3300s (55 minutes) which is less than typical token lifetime (3600s)
        but more than the 300s buffer used in is_expired(). This ensures:
        - Cached tokens are reused for nearly their full lifetime
        - Cache expires slightly before token expiry check would trigger refresh
        - Verification tokens are reused even hours later
        """
        age = (datetime.now(UTC) - self.cached_at).total_seconds()
        return age < max_age_seconds and not self.token.is_expired(buffer_seconds=300)

    def age_seconds(self) -> float:
        """Get cache age in seconds"""
        return (datetime.now(UTC) - self.cached_at).total_seconds()
