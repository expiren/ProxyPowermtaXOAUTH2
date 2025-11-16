"""Global proxy settings"""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Settings:
    """Proxy configuration settings"""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 2525

    # Performance tuning (high-concurrency configuration)
    global_concurrency_limit: int = 100
    max_concurrent_per_account: int = 10
    max_messages_per_hour: int = 10000
    smtp_thread_pool_size: int = 500  # Thread pool for blocking SMTP operations
    http_pool_connections: int = 500  # HTTP connection pool size for OAuth2
    http_pool_maxsize: int = 500      # Maximum HTTP pool size

    # Timeouts
    smtp_timeout: int = 15
    oauth2_timeout: int = 10
    connection_timeout: int = 15

    # Connection pooling (legacy settings, kept for compatibility)
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_idle_timeout: int = 300

    # Retry policy
    retry_attempts: int = 3
    retry_backoff_factor: float = 2.0
    retry_max_delay: int = 30

    # Circuit breaker
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60

    # OAuth2
    token_refresh_buffer: int = 300  # 5 minutes
    token_cache_ttl: int = 60

    # Features
    dry_run: bool = False
    enable_metrics: bool = True
    enable_circuit_breaker: bool = True

    @classmethod
    def from_env(cls) -> 'Settings':
        """Create settings from environment variables"""
        return cls(
            host=os.getenv('XOAUTH2_HOST', '127.0.0.1'),
            port=int(os.getenv('XOAUTH2_PORT', 2525)),
            global_concurrency_limit=int(os.getenv('XOAUTH2_GLOBAL_CONCURRENCY', 100)),
            dry_run=os.getenv('XOAUTH2_DRY_RUN', 'false').lower() == 'true',
        )

    @staticmethod
    def get_config_path(config_arg: str = None) -> Path:
        """Get accounts.json path with smart discovery"""
        if config_arg:
            path = Path(config_arg)
            if path.exists():
                return path

        # Try current directory first
        local_path = Path('accounts.json')
        if local_path.exists():
            return local_path

        # Try standard locations
        std_paths = [
            Path('/etc/xoauth2/accounts.json'),  # Linux
            Path('/usr/local/etc/xoauth2/accounts.json'),  # macOS
            Path(os.path.expanduser('~/.xoauth2/accounts.json')),  # Home
        ]

        for path in std_paths:
            if path.exists():
                return path

        # Default to current directory
        return Path('accounts.json')
