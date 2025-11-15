"""Upstream XOAUTH2 relay - sends messages to Gmail/Outlook SMTP"""

import asyncio
import smtplib
import logging
import base64
from typing import Optional, List, Tuple, Callable, Any
from concurrent.futures import ThreadPoolExecutor

from src.accounts.models import AccountConfig
from src.oauth2.manager import OAuth2Manager
from src.metrics.collector import MetricsCollector
from src.smtp.exceptions import (
    SMTPAuthenticationError, SMTPConnectionError,
    SMTPRelayError, InvalidRecipient, SMTPTimeout
)

logger = logging.getLogger('xoauth2_proxy')

# Alias for metrics
Metrics = MetricsCollector


class UpstreamRelay:
    """Handles relay of messages to upstream SMTP servers via XOAUTH2"""

    def __init__(self, oauth_manager: OAuth2Manager, max_workers: int = 500):
        self.oauth_manager = oauth_manager

        # Create dedicated thread pool for SMTP operations (high concurrency)
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="smtp_relay"
        )
        logger.info(f"[UpstreamRelay] Initialized with {max_workers} worker threads")

    async def send_message(
        self,
        account: AccountConfig,
        message_data: bytes,
        mail_from: str,
        rcpt_tos: List[str],
        dry_run: bool = False
    ) -> Tuple[bool, int, str]:
        """
        Send message via upstream SMTP server using XOAUTH2

        Args:
            account: Account configuration
            message_data: Raw message bytes
            mail_from: Sender email
            rcpt_tos: List of recipients
            dry_run: If True, test connection but don't send

        Returns:
            (success: bool, smtp_code: int, message: str)
        """
        import time
        start_time = time.time()

        try:
            # Refresh token if needed
            token = await self.oauth_manager.get_or_refresh_token(account)
            if not token:
                logger.error(f"[{account.email}] Failed to get OAuth2 token")
                return (False, 454, "4.7.0 Temporary service unavailable")

            # Build XOAUTH2 auth string
            # IMPORTANT: Return the RAW XOAUTH2 string, NOT base64 encoded
            # smtplib.auth() handles base64 encoding internally
            # Using \1 literal (octal escape for byte 0x01), not chr(1)
            xoauth2_string = f"user={mail_from}\1auth=Bearer {token.access_token}\1\1"

            logger.debug(
                f"[{account.email}] XOAUTH2 string: "
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

            # Connect and send in executor
            loop = asyncio.get_running_loop()

            def connect_and_send():
                """Blocking SMTP operations"""
                try:
                    # Connect
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                    logger.debug(f"[{account.email}] Connected to {smtp_host}:{smtp_port}")

                    # EHLO
                    code, msg = server.ehlo(name=mail_from.split('@')[1])
                    logger.debug(f"[{account.email}] EHLO: {code}")

                    # STARTTLS
                    try:
                        code, msg = server.starttls()
                        logger.debug(f"[{account.email}] STARTTLS: {code}")
                    except smtplib.SMTPNotSupportedError:
                        logger.warning(f"[{account.email}] STARTTLS not supported")

                    # EHLO again
                    code, msg = server.ehlo(name=mail_from.split('@')[1])
                    logger.debug(f"[{account.email}] EHLO after TLS: {code}")

                    # AUTH XOAUTH2
                    logger.info(f"[{account.email}] Authenticating with XOAUTH2...")
                    try:
                        # Return the RAW XOAUTH2 string, smtplib.auth() handles base64 encoding internally
                        auth_callback: Callable[..., str] = lambda: xoauth2_string  # type: ignore
                        code, msg = server.auth('XOAUTH2', auth_callback)  # type: ignore
                        logger.info(f"[{account.email}] XOAUTH2 auth successful: {code}")
                    except smtplib.SMTPAuthenticationError as e:
                        logger.error(f"[{account.email}] XOAUTH2 auth failed: {e}")
                        server.quit()
                        return (False, 454, "4.7.0 Authentication failed")

                    # Dry-run mode
                    if dry_run:
                        logger.info(f"[{account.email}] DRY-RUN: Would send to {rcpt_tos}")
                        server.quit()
                        return (True, 250, "2.0.0 OK (dry-run)")

                    # Send message
                    logger.info(f"[{account.email}] Sending message to {rcpt_tos}...")
                    rejected = server.sendmail(mail_from, rcpt_tos, message_data)

                    if rejected:
                        logger.warning(f"[{account.email}] Recipients rejected: {rejected}")
                        rejected_str = ", ".join([f"{addr}: {code}" for addr, (code, msg) in rejected.items()])
                        server.quit()
                        return (False, 553, f"5.1.3 Some recipients rejected: {rejected_str[:50]}")

                    logger.info(f"[{account.email}] Message sent to {len(rcpt_tos)} recipients")
                    server.quit()
                    return (True, 250, "2.0.0 OK")

                except smtplib.SMTPException as e:
                    logger.error(f"[{account.email}] SMTP error: {e}")
                    return (False, 452, "4.3.0 SMTP error")
                except TimeoutError as e:
                    logger.error(f"[{account.email}] Connection timeout: {e}")
                    return (False, 450, "4.4.2 Connection timeout")
                except ConnectionRefusedError as e:
                    logger.error(f"[{account.email}] Connection refused: {e}")
                    return (False, 450, "4.4.2 Connection refused")
                except Exception as e:
                    logger.error(f"[{account.email}] Unexpected error: {e}")
                    return (False, 450, "4.4.2 Temporary failure")

            # Execute in dedicated thread pool (500 workers for high concurrency)
            result: Tuple[bool, int, str] = await loop.run_in_executor(self.executor, connect_and_send)  # type: ignore
            success, smtp_code, message = result

            # Update metrics
            duration = time.time() - start_time
            if success:
                Metrics.messages_total.labels(account=account.email, result='success').inc()
                logger.info(f"[{account.email}] Message relayed successfully ({duration:.2f}s)")
            else:
                Metrics.messages_total.labels(account=account.email, result='failure').inc()
                logger.error(f"[{account.email}] Message relay failed: {message}")

            Metrics.messages_duration_seconds.labels(account=account.email).observe(duration)

            return (success, smtp_code, message)

        except Exception as e:
            logger.error(f"[{account.email}] Unexpected error in relay: {e}")
            Metrics.messages_total.labels(account=account.email, result='failure').inc()
            Metrics.errors_total.labels(account=account.email, error_type='relay').inc()
            return (False, 450, "4.4.2 Internal error")
