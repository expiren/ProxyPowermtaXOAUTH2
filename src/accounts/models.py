"""Account configuration models"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING, Dict, Any
from datetime import datetime, UTC
import asyncio

if TYPE_CHECKING:
    from src.oauth2.models import OAuthToken


@dataclass
class AccountConfig:
    """Single account configuration with per-account overrides"""
    account_id: str
    email: str
    ip_address: str
    vmta_name: str
    provider: str  # 'gmail' or 'outlook'
    client_id: str
    refresh_token: str
    oauth_endpoint: str  # SMTP endpoint (e.g., smtp.office365.com:587)
    oauth_token_url: str  # OAuth2 token endpoint (provider-specific)
    client_secret: str = ""  # Optional for some Outlook OAuth flows

    # Concurrency limits (legacy, kept for backward compatibility)
    max_concurrent_messages: int = 10
    max_messages_per_hour: int = 10000

    # Per-account overrides (optional, overrides provider defaults from config.json)
    connection_settings: Optional[Dict[str, Any]] = None
    rate_limiting: Optional[Dict[str, Any]] = None
    retry: Optional[Dict[str, Any]] = None
    circuit_breaker: Optional[Dict[str, Any]] = None

    # State (thread-safe)
    token: Optional['OAuthToken'] = None
    messages_this_hour: int = field(default=0)
    concurrent_messages: int = field(default=0)
    active_connections: int = field(default=0)  # Track active authenticated connections
    # IMPROVED: Lock created in __post_init__ for durability (not default_factory)
    lock: Optional[asyncio.Lock] = field(default=None, init=False, repr=False)

    # Merged config from provider defaults + account overrides (set during initialization)
    _merged_connection_pool: Optional[Any] = field(default=None, init=False, repr=False)
    _merged_rate_limiting: Optional[Any] = field(default=None, init=False, repr=False)
    _merged_retry: Optional[Any] = field(default=None, init=False, repr=False)
    _merged_circuit_breaker: Optional[Any] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize token and lock if not present"""
        # Create lock in __post_init__ (more durable than default_factory on hot-reload)
        if self.lock is None:
            self.lock = asyncio.Lock()

        # Initialize token if not present
        if self.token is None:
            from src.oauth2.models import OAuthToken
            self.token = OAuthToken(
                access_token="",
                expires_at=datetime.now(UTC),
                refresh_token=self.refresh_token
            )

    def apply_provider_config(self, provider_config):
        """
        Merge provider defaults with account-specific overrides

        Args:
            provider_config: ProviderConfig from config.json
        """
        from src.config.proxy_config import ConnectionPoolConfig, RateLimitConfig, RetryConfig, CircuitBreakerConfig

        # Merge connection pool settings
        pool_data = provider_config.connection_pool.__dict__.copy()
        if self.connection_settings:
            pool_data.update(self.connection_settings)
        self._merged_connection_pool = ConnectionPoolConfig(**pool_data)

        # Merge rate limiting settings
        rate_data = provider_config.rate_limiting.__dict__.copy()
        if self.rate_limiting:
            rate_data.update(self.rate_limiting)
        self._merged_rate_limiting = RateLimitConfig(**rate_data)

        # Merge retry settings
        retry_data = provider_config.retry.__dict__.copy()
        if self.retry:
            retry_data.update(self.retry)
        self._merged_retry = RetryConfig(**retry_data)

        # Merge circuit breaker settings
        cb_data = provider_config.circuit_breaker.__dict__.copy()
        if self.circuit_breaker:
            cb_data.update(self.circuit_breaker)
        self._merged_circuit_breaker = CircuitBreakerConfig(**cb_data)

    def get_connection_pool_config(self):
        """Get merged connection pool configuration"""
        return self._merged_connection_pool

    def get_rate_limiting_config(self):
        """Get merged rate limiting configuration"""
        return self._merged_rate_limiting

    def get_retry_config(self):
        """Get merged retry configuration"""
        return self._merged_retry

    def get_circuit_breaker_config(self):
        """Get merged circuit breaker configuration"""
        return self._merged_circuit_breaker

    @property
    def is_gmail(self) -> bool:
        """Check if this is a Gmail account"""
        return self.provider.lower() == 'gmail'

    @property
    def is_outlook(self) -> bool:
        """Check if this is an Outlook account"""
        return self.provider.lower() == 'outlook'

    def can_send(self, concurrent_limit: int = None) -> bool:
        """Check if account can send (not at limit)"""
        limit = concurrent_limit or self.max_concurrent_messages
        return self.concurrent_messages < limit

    def get_concurrency_percentage(self) -> float:
        """Get current concurrency as percentage"""
        if self.max_concurrent_messages == 0:
            return 0.0
        return (self.concurrent_messages / self.max_concurrent_messages) * 100

    def __str__(self) -> str:
        """String representation"""
        return f"Account({self.email}, provider={self.provider}, concurrent={self.concurrent_messages}/{self.max_concurrent_messages})"

    def __hash__(self):
        """Make hashable by email"""
        return hash(self.email)

    def __eq__(self, other):
        """Compare by email"""
        if isinstance(other, AccountConfig):
            return self.email == other.email
        return False
