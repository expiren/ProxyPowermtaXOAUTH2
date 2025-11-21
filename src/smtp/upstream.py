"""Upstream XOAUTH2 relay - sends messages to Gmail/Outlook SMTP (Fully Async with Connection Pooling)"""

import asyncio
import logging
from typing import Optional, List, Tuple, TYPE_CHECKING

from src.accounts.models import AccountConfig
from src.oauth2.manager import OAuth2Manager
from src.smtp.connection_pool import SMTPConnectionPool


if TYPE_CHECKING:
    from src.config.proxy_config import SMTPConfig

logger = logging.getLogger('xoauth2_proxy')


class UpstreamRelay:
    """Handles relay of messages to upstream SMTP servers via XOAUTH2 (Fully Async)"""

    def __init__(
        self,
        oauth_manager: OAuth2Manager,
        max_connections_per_account: int = 50,
        max_messages_per_connection: int = 100,
        connection_max_age: int = 300,  # ✅ Configurable connection max age (seconds)
        connection_idle_timeout: int = 60,  # ✅ Configurable idle timeout (seconds)
        rate_limiter = None,  # ✅ Optional RateLimiter for per-account rate limiting
        smtp_config: Optional['SMTPConfig'] = None  # ✅ SMTP config for IP binding
    ):
        self.oauth_manager = oauth_manager
        self.rate_limiter = rate_limiter  # ✅ Store rate limiter

        # Create SMTP connection pool (fully async, no thread pool needed!)
        self.connection_pool = SMTPConnectionPool(
            max_connections_per_account=max_connections_per_account,
            max_messages_per_connection=max_messages_per_connection,
            connection_max_age=connection_max_age,  # ✅ From config
            connection_idle_timeout=connection_idle_timeout,  # ✅ From config
            smtp_config=smtp_config  # ✅ Pass SMTP config for IP binding
        )

        # Start cleanup task
        self.cleanup_task = None

        logger.info(
            f"[UpstreamRelay] Initialized with connection pooling "
            f"(max_conn_per_account={max_connections_per_account}, "
            f"max_msg_per_conn={max_messages_per_connection}, "
            f"max_age={connection_max_age}s, idle_timeout={connection_idle_timeout}s, "
            f"rate_limiting={'enabled' if rate_limiter else 'disabled'})"
        )

    async def initialize(self):
        """Initialize and start background tasks"""
        # Start connection cleanup task
        self.cleanup_task = asyncio.create_task(self.connection_pool.cleanup_idle_connections())
        logger.info("[UpstreamRelay] Started connection pool cleanup task")

    async def send_message(
        self,
        account: AccountConfig,
        message_data: bytes,
        mail_from: str,
        rcpt_tos: List[str],
        dry_run: bool = False
    ) -> Tuple[bool, int, str]:
        """
        Send message via upstream SMTP server using XOAUTH2 with connection reuse

        NOTE: PowerMTA sends one message per SMTP conversation:
        - Different messages have different content
        - Each message has ONE recipient (len(rcpt_tos) == 1)
        - Connection reuse happens across sequential messages from SAME sender account

        Args:
            account: Account configuration
            message_data: Raw message bytes (unique per message)
            mail_from: Sender email
            rcpt_tos: List of recipients (typically 1 recipient per message)
            dry_run: If True, test connection but don't send

        Returns:
            (success: bool, smtp_code: int, message: str)
        """
        # ✅ FIX BUG #4: Removed unused start_time variable (wasted 1,166 time.time() calls/sec)
        # start_time = time.time()

        try:
            # ✅ Check rate limit BEFORE doing any work (token refresh, connection pool, etc.)
            if self.rate_limiter:
                try:
                    # Acquire token from rate limiter with per-account settings
                    # (raises RateLimitExceeded if over limit)
                    await self.rate_limiter.acquire(account.email, account=account)
                except Exception as e:
                    # Rate limit exceeded - reject with temporary failure
                    logger.warning(f"[{account.email}] Rate limit exceeded: {e}")
                    return (False, 451, "4.4.4 Rate limit exceeded, try again later")

            # Refresh token if needed
            token = await self.oauth_manager.get_or_refresh_token(account)
            if not token:
                logger.error(f"[{account.email}] Failed to get OAuth2 token")
                return (False, 454, "4.7.0 Temporary service unavailable")

            # Validate mail_from doesn't contain control characters that could corrupt XOAUTH2
            # XOAUTH2 uses \1 (ASCII 0x01) as separator, so we must reject it in mail_from
            if '\x01' in mail_from or '\x00' in mail_from:
                logger.error(
                    f"[{account.email}] Invalid mail_from contains control characters: {repr(mail_from)}"
                )
                return (False, 501, "5.5.2 Invalid sender address")

            # Build XOAUTH2 auth string (RAW, not base64 - pool will encode it)
            xoauth2_string = f"user={mail_from}\1auth=Bearer {token.access_token}\1\1"

            # Parse SMTP endpoint
            smtp_host, smtp_port_str = account.oauth_endpoint.split(':')
            smtp_port = int(smtp_port_str)

            # Acquire connection from pool (reuses existing authenticated connections!)
            # ✅ Pass account object for per-account connection pool settings
            # ✅ Moved inside try block to ensure semaphore is always released on any exception
            connection = None  # Initialize to None so exception handlers can check if assigned
            try:
                connection = await self.connection_pool.acquire(
                    account_email=account.email,
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    xoauth2_string=xoauth2_string,
                    account=account  # ✅ Per-account settings (max_connections, max_messages)
                )
                # Dry-run mode
                if dry_run:
                    await self.connection_pool.release(account.email, connection, increment_count=False)
                    return (True, 250, "2.0.0 OK (dry-run)")

                # ✅ FIX: Keep message_data as bytes to preserve Unicode characters
                # Email messages should be handled as bytes throughout SMTP protocol
                # Converting to string causes aiosmtplib to re-encode with ASCII (fails on Unicode!)
                # Examples that fail with ASCII: Don't (curly apostrophe \u2019), café, etc.
                if not isinstance(message_data, bytes):
                    # If somehow we got a string, encode it to UTF-8 bytes
                    message_bytes = message_data.encode('utf-8')
                else:
                    message_bytes = message_data

                # ✅ USE LOW-LEVEL SMTP COMMANDS FOR CONNECTION REUSE
                # This keeps connection state clean and ready for next message

                # MAIL FROM
                code, msg = await connection.mail(mail_from)
                if code not in (250, 251):
                    logger.error(f"[{account.email}] MAIL FROM rejected: {code} {msg}")
                    await self.connection_pool.remove_and_close(account.email, connection)
                    return (False, code, msg)

                # RCPT TO (for each recipient - typically just one)
                rejected_recipients = []
                for rcpt in rcpt_tos:
                    code, msg = await connection.rcpt(rcpt)
                    if code not in (250, 251):
                        logger.warning(f"[{account.email}] RCPT TO {rcpt} rejected: {code} {msg}")
                        rejected_recipients.append(rcpt)

                # If all recipients rejected, fail
                if rejected_recipients and len(rejected_recipients) == len(rcpt_tos):
                    logger.error(f"[{account.email}] All recipients rejected")
                    await self.connection_pool.remove_and_close(account.email, connection)
                    return (False, 553, "5.1.3 All recipients rejected")

                # DATA (send message body) - pass bytes directly to preserve encoding
                code, msg = await connection.data(message_bytes)
                if code != 250:
                    logger.error(f"[{account.email}] DATA rejected: {code} {msg}")
                    await self.connection_pool.remove_and_close(account.email, connection)
                    return (False, code, msg)

                # ✅ SUCCESS - Return connection to pool (KEEP ALIVE for reuse)
                # Connection is now in clean state, ready for next MAIL FROM command
                await self.connection_pool.release(account.email, connection, increment_count=True)

                if rejected_recipients:
                    rejected_str = ", ".join(rejected_recipients[:3])
                    return (True, 250, f"2.0.0 OK (some recipients rejected: {rejected_str})")

                return (True, 250, "2.0.0 OK")

            except asyncio.TimeoutError:
                # Timeout - close connection, don't reuse
                logger.error(f"[{account.email}] SMTP timeout")
                if connection:  # Only release if connection was acquired
                    await self.connection_pool.remove_and_close(account.email, connection)

                return (False, 450, "4.4.2 Connection timeout")

            except Exception as e:
                # Error - close connection, don't reuse
                logger.error(f"[{account.email}] SMTP send error: {e}")
                if connection:  # Only release if connection was acquired
                    await self.connection_pool.remove_and_close(account.email, connection)

                # Parse error for better response
                error_str = str(e).lower()
                if 'auth' in error_str:
                    return (False, 454, "4.7.0 Authentication failed")
                elif 'timeout' in error_str:
                    return (False, 450, "4.4.2 Connection timeout")
                elif 'refused' in error_str:
                    return (False, 450, "4.4.2 Connection refused")
                else:
                    return (False, 452, "4.3.0 SMTP error")

        except Exception as e:
            logger.error(f"[{account.email}] Unexpected error in relay: {e}")
            return (False, 450, "4.4.2 Internal error")

    async def shutdown(self):
        """Shutdown relay and cleanup resources"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        await self.connection_pool.close_all()
        logger.info("[UpstreamRelay] Shutdown complete")

    def get_stats(self) -> dict:
        """Get relay statistics"""
        return {
            'connection_pool': self.connection_pool.get_stats(),
        }
