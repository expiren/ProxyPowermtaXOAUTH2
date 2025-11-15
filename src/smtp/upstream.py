"""Upstream XOAUTH2 relay - sends messages to Gmail/Outlook SMTP (Fully Async with Connection Pooling)"""

import asyncio
import logging
import base64
import time
from typing import Optional, List, Tuple

from src.accounts.models import AccountConfig
from src.oauth2.manager import OAuth2Manager
from src.metrics.collector import MetricsCollector
from src.smtp.connection_pool import SMTPConnectionPool
from src.smtp.exceptions import (
    SMTPAuthenticationError, SMTPConnectionError,
    SMTPRelayError, InvalidRecipient, SMTPTimeout
)

logger = logging.getLogger('xoauth2_proxy')

# Alias for metrics
Metrics = MetricsCollector


class UpstreamRelay:
    """Handles relay of messages to upstream SMTP servers via XOAUTH2 (Fully Async)"""

    def __init__(
        self,
        oauth_manager: OAuth2Manager,
        max_connections_per_account: int = 50,
        max_messages_per_connection: int = 100
    ):
        self.oauth_manager = oauth_manager

        # Create SMTP connection pool (fully async, no thread pool needed!)
        self.connection_pool = SMTPConnectionPool(
            max_connections_per_account=max_connections_per_account,
            max_messages_per_connection=max_messages_per_connection,
            connection_max_age=300,      # 5 minutes
            connection_idle_timeout=60   # 1 minute
        )

        # Start cleanup task
        self.cleanup_task = None

        logger.info(
            f"[UpstreamRelay] Initialized with connection pooling "
            f"(max_conn_per_account={max_connections_per_account}, "
            f"max_msg_per_conn={max_messages_per_connection})"
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
        Send message via upstream SMTP server using XOAUTH2 (Fully Async)

        Args:
            account: Account configuration
            message_data: Raw message bytes
            mail_from: Sender email
            rcpt_tos: List of recipients
            dry_run: If True, test connection but don't send

        Returns:
            (success: bool, smtp_code: int, message: str)
        """
        start_time = time.time()

        try:
            # Refresh token if needed
            token = await self.oauth_manager.get_or_refresh_token(account)
            if not token:
                logger.error(f"[{account.email}] Failed to get OAuth2 token")
                return (False, 454, "4.7.0 Temporary service unavailable")

            # Build XOAUTH2 auth string (RAW, not base64 - pool will encode it)
            # Using \1 literal (octal escape for byte 0x01)
            xoauth2_string = f"user={mail_from}\1auth=Bearer {token.access_token}\1\1"

            logger.debug(
                f"[{account.email}] XOAUTH2 string prepared: "
                f"user={mail_from}, token_length={len(token.access_token)}, "
                f"expires_in={token.expires_in_seconds()}s"
            )

            # Parse SMTP endpoint
            smtp_host, smtp_port_str = account.oauth_endpoint.split(':')
            smtp_port = int(smtp_port_str)

            logger.info(
                f"[{account.email}] Relaying to {smtp_host}:{smtp_port} "
                f"({account.provider.upper()}) - {len(rcpt_tos)} recipients"
            )

            # Acquire connection from pool (async, reuses existing authenticated connections!)
            connection = await self.connection_pool.acquire(
                account_email=account.email,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                xoauth2_string=xoauth2_string
            )

            try:
                # Dry-run mode
                if dry_run:
                    logger.info(f"[{account.email}] DRY-RUN: Would send to {rcpt_tos}")
                    # Release connection back to pool
                    await self.connection_pool.release(account.email, connection, increment_count=False)
                    return (True, 250, "2.0.0 OK (dry-run)")

                # Send message (fully async!)
                logger.info(f"[{account.email}] Sending message to {rcpt_tos}...")

                # Convert message_data to string if needed
                if isinstance(message_data, bytes):
                    message_str = message_data.decode('utf-8', errors='replace')
                else:
                    message_str = message_data

                # Send with aiosmtplib (fully async, no blocking!)
                errors, response = await connection.sendmail(
                    mail_from,
                    rcpt_tos,
                    message_str
                )

                # Release connection back to pool
                await self.connection_pool.release(account.email, connection, increment_count=True)

                # Check for rejected recipients
                if errors:
                    logger.warning(f"[{account.email}] Some recipients rejected: {errors}")
                    rejected_str = ", ".join([f"{addr}" for addr in errors.keys()])
                    return (False, 553, f"5.1.3 Some recipients rejected: {rejected_str[:50]}")

                # Success
                duration = time.time() - start_time
                Metrics.messages_total.labels(account=account.email, result='success').inc()
                Metrics.messages_duration_seconds.labels(account=account.email).observe(duration)

                logger.info(
                    f"[{account.email}] Message relayed successfully to {len(rcpt_tos)} recipients "
                    f"({duration:.3f}s)"
                )
                return (True, 250, "2.0.0 OK")

            except asyncio.TimeoutError:
                # Release connection on error
                await self.connection_pool.release(account.email, connection, increment_count=False)

                duration = time.time() - start_time
                logger.error(f"[{account.email}] SMTP timeout")
                Metrics.messages_total.labels(account=account.email, result='failure').inc()
                Metrics.messages_duration_seconds.labels(account=account.email).observe(duration)
                return (False, 450, "4.4.2 Connection timeout")

            except Exception as e:
                # Release connection on error
                await self.connection_pool.release(account.email, connection, increment_count=False)

                duration = time.time() - start_time
                logger.error(f"[{account.email}] SMTP send error: {e}")
                Metrics.messages_total.labels(account=account.email, result='failure').inc()
                Metrics.messages_duration_seconds.labels(account=account.email).observe(duration)

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
            duration = time.time() - start_time
            logger.error(f"[{account.email}] Unexpected error in relay: {e}")
            Metrics.messages_total.labels(account=account.email, result='failure').inc()
            Metrics.errors_total.labels(account=account.email, error_type='relay').inc()
            Metrics.messages_duration_seconds.labels(account=account.email).observe(duration)
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
