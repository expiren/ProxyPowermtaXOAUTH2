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
from src.admin.server import AdminServer

logger = logging.getLogger('xoauth2_proxy')


class SMTPProxyServer:
    """Main SMTP proxy server"""

    def __init__(
        self,
        config_path: Path,
        accounts_path: Path,
        settings: Settings
    ):
        self.config_path = config_path
        self.accounts_path = accounts_path
        self.settings = settings

        # Load ProxyConfig from config.json (global settings + provider defaults)
        if config_path.exists():
            self.proxy_config = ProxyConfig(config_path)
            logger.info(f"[SMTPProxyServer] Loaded proxy config from {config_path}")
        else:
            # Use built-in defaults
            self.proxy_config = ProxyConfig()
            logger.info("[SMTPProxyServer] Using built-in provider defaults")

        # Initialize AccountManager with separate accounts.json file
        self.account_manager = AccountManager(accounts_path, proxy_config=self.proxy_config)

        # ✅ Use oauth2_timeout and http_pool config from proxy_config
        oauth2_timeout = self.proxy_config.global_config.oauth2_timeout
        http_pool_config = {
            'total_connections': self.proxy_config.global_config.http_pool.total_connections,
            'connections_per_host': self.proxy_config.global_config.http_pool.connections_per_host,
            'dns_cache_ttl_seconds': self.proxy_config.global_config.http_pool.dns_cache_ttl_seconds,
            'connect_timeout_seconds': self.proxy_config.global_config.http_pool.connect_timeout_seconds,
        }
        self.oauth_manager = OAuth2Manager(timeout=oauth2_timeout, http_pool_config=http_pool_config)
        logger.debug(
            f"[SMTPProxyServer] OAuth2Manager initialized (timeout={oauth2_timeout}s, "
            f"http_pool: {http_pool_config['total_connections']} total connections)"
        )

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
            rate_limiter=self.rate_limiter,  # ✅ Pass rate limiter for per-account limits
            smtp_config=self.proxy_config.global_config.smtp  # ✅ Pass SMTP config for IP binding
        )

        # ✅ Global semaphore for backpressure
        self.global_semaphore = asyncio.Semaphore(self.proxy_config.global_config.global_concurrency_limit)

        # Admin HTTP server for managing accounts via API
        self.admin_server = AdminServer(
            accounts_path=accounts_path,
            account_manager=self.account_manager,
            oauth_manager=self.oauth_manager,
            host=settings.admin_host,
            port=settings.admin_port,
            proxy_config=self.proxy_config  # Pass proxy config for IP auto-assignment
        )

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

    async def reload(self):
        """Reload configuration (accounts and provider settings)"""
        logger.info("[SMTPProxyServer] Reloading configuration...")

        # Reload ProxyConfig from file
        if self.config_path.exists():
            old_proxy_config = self.proxy_config
            self.proxy_config = ProxyConfig(self.config_path)
            logger.info(f"[SMTPProxyServer] Reloaded proxy config from {self.config_path}")

            # Update account_manager's proxy_config reference
            self.account_manager.proxy_config = self.proxy_config
            # Reload accounts (will use new provider configs)
            num_accounts = await self.account_manager.reload()

            logger.info(
                f"[SMTPProxyServer] Reload complete - {num_accounts} accounts loaded with updated provider settings"
            )
            logger.warning(
                "[SMTPProxyServer] NOTE: Global defaults (UpstreamRelay, RateLimiter baseline) "
                "were NOT updated - per-account settings from reloaded config WILL be used"
            )
            return num_accounts
        else:
            logger.error(f"[SMTPProxyServer] Cannot reload - config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

    async def start(self):
        """Start the SMTP proxy server"""
        try:
            # Initialize
            num_accounts = await self.initialize()

            # Start admin HTTP server
            await self.admin_server.start()

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

        # Shutdown admin server
        await self.admin_server.shutdown()

        await self.upstream_relay.shutdown()
        await self.oauth_manager.cleanup()

        logger.info("[SMTPProxyServer] Shutdown complete")
