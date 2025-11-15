"""SMTP Proxy Server"""

import asyncio
import logging
from pathlib import Path

from src.config.settings import Settings
from src.oauth2.manager import OAuth2Manager
from src.accounts.manager import AccountManager
from src.metrics.server import MetricsServer
from src.smtp.handler import SMTPProxyHandler
from src.smtp.upstream import UpstreamRelay

logger = logging.getLogger('xoauth2_proxy')


class SMTPProxyServer:
    """Main SMTP proxy server"""

    def __init__(
        self,
        config_path: Path,
        settings: Settings
    ):
        self.config_path = config_path
        self.settings = settings

        # Initialize components
        self.account_manager = AccountManager(config_path)
        self.oauth_manager = OAuth2Manager(timeout=settings.oauth2_timeout)
        self.upstream_relay = UpstreamRelay(self.oauth_manager)
        self.metrics_server = MetricsServer(host='0.0.0.0', port=settings.metrics_port)

        self.server = None

    async def initialize(self) -> int:
        """Initialize all components"""
        # Load accounts
        num_accounts = await self.account_manager.load()

        # Initialize OAuth2 manager
        await self.oauth_manager.initialize()

        # Initialize upstream relay with connection pool
        await self.upstream_relay.initialize()

        logger.info(
            f"[SMTPProxyServer] Initialized with {num_accounts} accounts, "
            f"metrics on port {self.settings.metrics_port}"
        )
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
            logger.info(f"Metrics server: http://0.0.0.0:{self.settings.metrics_port}/metrics")
            logger.info(f"Dry-run mode: {self.settings.dry_run}")

            # Start metrics server in background task
            metrics_task = asyncio.create_task(self.metrics_server.start())

            # Create SMTP server factory
            loop = asyncio.get_running_loop()

            def handler_factory():
                return SMTPProxyHandler(
                    config_manager=self.account_manager,
                    oauth_manager=self.oauth_manager,
                    upstream_relay=self.upstream_relay,
                    dry_run=self.settings.dry_run,
                    global_concurrency_limit=self.settings.global_concurrency_limit
                )

            # Create SMTP server
            self.server = await loop.create_server(
                handler_factory,
                self.settings.host,
                self.settings.port
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

        await self.metrics_server.stop()
        await self.upstream_relay.shutdown()
        await self.oauth_manager.cleanup()

        logger.info("[SMTPProxyServer] Shutdown complete")
