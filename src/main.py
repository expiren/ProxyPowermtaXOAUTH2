"""Main entry point for XOAUTH2 Proxy"""

import asyncio
import logging
import signal
import sys
import platform

from src.cli import parse_arguments, create_settings
from src.logging.setup import setup_logging
from src.smtp.proxy import SMTPProxyServer


# Setup logging early
setup_logging()
logger = logging.getLogger('xoauth2_proxy')


class Application:
    """Main application orchestrator"""

    def __init__(self):
        self.proxy_server = None
        self.running = False

    async def run(self):
        """Main application loop"""
        try:
            # Parse CLI arguments (returns config_path and accounts_path separately)
            args, config_path, accounts_path = parse_arguments()

            # Verify both config files exist
            if not config_path.exists():
                logger.error(f"Config file not found: {config_path}")
                sys.exit(1)

            if not accounts_path.exists():
                logger.error(f"Accounts file not found: {accounts_path}")
                sys.exit(1)

            # Create settings
            settings = create_settings(args)

            # Create and start proxy server
            logger.info(f"Initializing XOAUTH2 Proxy")
            logger.info(f"  Config: {config_path}")
            logger.info(f"  Accounts: {accounts_path}")
            self.proxy_server = SMTPProxyServer(
                config_path=config_path,
                accounts_path=accounts_path,
                settings=settings
            )

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start proxy
            self.running = True
            await self.proxy_server.start()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            await self.shutdown()
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            sys.exit(1)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown - cross-platform (Windows/Linux/macOS)"""
        loop = asyncio.get_running_loop()

        async def shutdown_handler():
            await self.shutdown()

        async def reload_handler():
            """Handle SIGHUP - reload full configuration (accounts + provider settings)"""
            logger.info("Received SIGHUP - reloading configuration...")
            try:
                if self.proxy_server:
                    num_accounts = await self.proxy_server.reload()
                    logger.info(f"Configuration reloaded successfully ({num_accounts} accounts)")
                else:
                    logger.warning("Cannot reload: proxy_server not initialized")
            except Exception as e:
                logger.error(f"Error reloading configuration: {e}", exc_info=True)

        if platform.system() == "Windows":
            # Windows - signal handlers run outside event loop, must use call_soon_threadsafe
            def windows_shutdown_handler(sig, frame):
                logger.info(f"Received signal {sig} on Windows - initiating graceful shutdown")
                loop.call_soon_threadsafe(lambda: asyncio.create_task(shutdown_handler()))

            signal.signal(signal.SIGTERM, windows_shutdown_handler)
            signal.signal(signal.SIGINT, windows_shutdown_handler)
            logger.debug("[Main] Signal handlers registered for Windows (SIGTERM, SIGINT)")
        else:
            # Linux, macOS - signal handlers run inside event loop
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown_handler()))
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown_handler()))
            loop.add_signal_handler(signal.SIGHUP, lambda: asyncio.create_task(reload_handler()))
            logger.debug("[Main] Signal handlers registered for Unix-like systems (SIGTERM, SIGINT, SIGHUP)")

    async def shutdown(self):
        """Shutdown application"""
        if not self.running:
            return

        logger.info("Starting graceful shutdown...")
        self.running = False

        if self.proxy_server:
            await self.proxy_server.shutdown()

        logger.info("Application stopped")


def main():
    """Main entry point"""
    app = Application()

    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        logger.info("Terminated")
    finally:
        loop.close()


if __name__ == '__main__':
    main()
