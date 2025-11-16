"""Account configuration models"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from src.oauth2.models import OAuthToken


@dataclass
class AccountConfig:
    """Single account configuration"""
    account_id: str
    email: str
    ip_address: str
    vmta_name: str
    provider: str  # 'gmail' or 'outlook'
    client_id: str
    client_secret: str
    refresh_token: str
    oauth_endpoint: str  # SMTP endpoint (e.g., smtp.office365.com:587)
    oauth_token_url: str  # OAuth2 token endpoint (provider-specific)

    # Concurrency limits
    max_concurrent_messages: int = 10
    max_messages_per_hour: int = 10000

    # State (thread-safe)
    token: Optional['OAuthToken'] = None
    messages_this_hour: int = field(default=0)
    concurrent_messages: int = field(default=0)
    active_connections: int = field(default=0)  # Track active authenticated connections
    # IMPROVED: Lock created in __post_init__ for durability (not default_factory)
    lock: Optional[asyncio.Lock] = field(default=None, init=False, repr=False)

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
                expires_at=__import__('datetime').datetime.now(__import__('datetime').UTC),
                refresh_token=self.refresh_token
            )

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
