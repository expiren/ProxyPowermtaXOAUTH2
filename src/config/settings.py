"""Global proxy settings"""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Settings:
    """Proxy configuration settings (CLI arguments only)

    Note: All other settings (timeouts, pools, retry, circuit breaker, etc.)
    are configured via ProxyConfig (loaded from config.json), not here.
    """

    # Server settings
    host: str = "127.0.0.1"
    port: int = 2525

    # Global concurrency
    global_concurrency_limit: int = 100

    # Features
    dry_run: bool = False

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
