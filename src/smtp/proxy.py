"""SMTP Proxy Server"""

import asyncio
import logging
from pathlib import Path

from src.config.settings import Settings
from src.config.proxy_config import ProxyConfig
from src.oauth2.manager import OAuth2Manager
from src.accounts.manager import AccountManager
from src.smtp.handler import SMTPProxyHandler
from src.smtp.upstream import UpstreamRelay
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger('xoauth2_proxy')


class SMTPProxyServer:
    """Main SMTP proxy server"""

    def __init__(
        self,
        config_path: Path,
        settings: Settings,
        proxy_config_path: Path = None
    ):
        self.config_path = config_path
        self.settings = settings

        # ✅ Load ProxyConfig (provider defaults, feature flags, etc.)
        if proxy_config_path and proxy_config_path.exists():
            self.proxy_config = ProxyConfig(proxy_config_path)
            logger.info(f"[SMTPProxyServer] Loaded proxy config from {proxy_config_path}")
        else:
            # Try loading config.json from same directory as accounts.json
            default_config_path = config_path.parent / "config.json"
            if default_config_path.exists():
                self.proxy_config = ProxyConfig(default_config_path)
                logger.info(f"[SMTPProxyServer] Loaded proxy config from {default_config_path}")
            else:
                # Use built-in defaults
                self.proxy_config = ProxyConfig()
                logger.info("[SMTPProxyServer] Using built-in provider defaults (no config.json found)")

        # ✅ Initialize components with proxy_config
        self.account_manager = AccountManager(config_path, proxy_config=self.proxy_config)

        # ✅ Use oauth2_timeout from proxy_config (not settings)
        oauth2_timeout = self.proxy_config.global_config.oauth2_timeout
        self.oauth_manager = OAuth2Manager(timeout=oauth2_timeout)
        logger.debug(f"[SMTPProxyServer] OAuth2Manager initialized (timeout={oauth2_timeout}s)")

        # ✅ Initialize RateLimiter (uses provider defaults, per-account overrides applied at runtime)
        # Default to Gmail's limit (10k messages/hour) as conservative baseline
        gmail_config = self.proxy_config.get_provider_config('gmail')
        default_messages_per_hour = gmail_config.rate_limiting.messages_per_hour
        self.rate_limiter = RateLimiter(messages_per_hour=default_messages_per_hour)
        logger.info(f"[SMTPProxyServer] RateLimiter initialized (default: {default_messages_per_hour} msg/hour)")

        # ✅ Initialize UpstreamRelay with provider-specific connection pool settings
        # Use Gmail defaults as baseline (most common provider)
        pool_config = gmail_config.connection_pool
        self.upstream_relay = UpstreamRelay(
            self.oauth_manager,
            max_connections_per_account=pool_config.max_connections_per_account,
            max_messages_per_connection=pool_config.max_messages_per_connection,
            connection_max_age=pool_config.connection_max_age_seconds,  # ✅ From config
            connection_idle_timeout=pool_config.connection_idle_timeout_seconds,  # ✅ From config
            rate_limiter=self.rate_limiter  # ✅ Pass rate limiter for per-account limits
        )

        # ✅ Global semaphore for backpressure
        self.global_semaphore = asyncio.Semaphore(self.proxy_config.global_config.global_concurrency_limit)

        self.server = None

    async def initialize(self) -> int:
        """Initialize all components"""
        # Load accounts
        num_accounts = await self.account_manager.load()

        # Initialize OAuth2 manager
        await self.oauth_manager.initialize()

        # Initialize upstream relay with connection pool
        await self.upstream_relay.initialize()

        logger.info(f"[SMTPProxyServer] Initialized with {num_accounts} accounts")
        return num_accounts

    async def start(self):
        """Start the SMTP proxy server"""
        try:
            # Initialize
            num_accounts = await self.initialize()

            logger.info(
                f"Starting XOAUTH2 proxy on {self.settings.host}:{self.settings.port} "
                f"({num_accounts} accounts)"
            )
            logger.info(f"Dry-run mode: {self.settings.dry_run}")

            # Create SMTP server factory
            loop = asyncio.get_running_loop()

            def handler_factory():
                return SMTPProxyHandler(
                    config_manager=self.account_manager,
                    oauth_manager=self.oauth_manager,
                    upstream_relay=self.upstream_relay,
                    dry_run=self.settings.dry_run,
                    global_concurrency_limit=self.settings.global_concurrency_limit,
                    global_semaphore=self.global_semaphore,
                    backpressure_queue_size=self.proxy_config.global_config.backpressure_queue_size
                )

            # Create SMTP server (with backlog for TCP backpressure)
            self.server = await loop.create_server(
                handler_factory,
                self.settings.host,
                self.settings.port,
                backlog=self.proxy_config.global_config.connection_backlog
            )

            logger.info("[SMTPProxyServer] XOAUTH2 proxy started successfully")

            # Serve
            async with self.server:
                await self.server.serve_forever()

        except asyncio.CancelledError:
            await self.shutdown()
        except Exception as e:
            logger.error(f"[SMTPProxyServer] Fatal error: {e}")
            await self.shutdown()
            raise

    async def shutdown(self):
        """Shutdown the proxy"""
        logger.info("[SMTPProxyServer] Shutting down...")

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        await self.upstream_relay.shutdown()
        await self.oauth_manager.cleanup()

        logger.info("[SMTPProxyServer] Shutdown complete")
