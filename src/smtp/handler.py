"""SMTP protocol handler for incoming connections"""

import asyncio
import base64
import logging
import time
import re
from typing import Dict, List, Optional
from collections import defaultdict

from src.accounts.models import AccountConfig
from src.oauth2.manager import OAuth2Manager
from src.metrics.collector import MetricsCollector
from src.smtp.upstream import UpstreamRelay

logger = logging.getLogger('xoauth2_proxy')

# Alias for metrics
Metrics = MetricsCollector


class SMTPProxyHandler(asyncio.Protocol):
    """SMTP protocol handler"""

    def __init__(
        self,
        config_manager,
        oauth_manager: OAuth2Manager,
        upstream_relay: UpstreamRelay,
        dry_run: bool = False,
        global_concurrency_limit: int = 100
    ):
        self.config_manager = config_manager
        self.oauth_manager = oauth_manager
        self.upstream_relay = upstream_relay
        self.dry_run = dry_run
        self.global_concurrency_limit = global_concurrency_limit

        self.transport = None
        self.peername = None
        self.current_account: Optional[AccountConfig] = None
        self.authenticated = False
        self.mail_from = None
        self.rcpt_tos: List[str] = []
        self.message_data = b''
        self.buffer = b''
        self.state = 'INITIAL'

        # Per-account tracking
        self.active_connections: Dict[str, int] = defaultdict(int)
        self.lock = asyncio.Lock()

        # Line processing queue (to avoid task spam)
        self.line_queue = asyncio.Queue()
        self.processing_task = None

    def connection_made(self, transport):
        """New connection established"""
        self.transport = transport
        self.peername = transport.get_extra_info('peername')
        logger.info(f"Connection made from {self.peername}")

        # Send initial greeting
        self.send_response(220, "ESMTP service ready")
        self.state = 'INITIAL'

        # Start ONE task per connection to process lines (not per-line!)
        self.processing_task = asyncio.create_task(self._process_lines())

    def connection_lost(self, exc):
        """Connection closed"""
        if exc:
            logger.error(f"Connection lost (error): {exc}")
        else:
            logger.info(f"Connection closed normally")

        # Cancel processing task
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()

        # Update metrics synchronously (no task needed - runs in event loop)
        if self.current_account:
            # Metrics updates are thread-safe, no need for async task
            if self.current_account.account_id in self.active_connections:
                self.active_connections[self.current_account.account_id] -= 1
                Metrics.smtp_connections_active.labels(
                    account=self.current_account.email
                ).set(self.active_connections[self.current_account.account_id])

    def data_received(self, data):
        """Data received from client"""
        self.buffer += data

        # Extract complete lines and queue them for processing
        while b'\r\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\r\n', 1)
            # Put line in queue instead of creating task (queuing is sync and fast)
            self.line_queue.put_nowait(line)

    async def _process_lines(self):
        """Process lines from queue (ONE task per connection instead of per-line)"""
        try:
            while True:
                # Wait for next line from queue
                line = await self.line_queue.get()
                try:
                    await self.handle_line(line)
                except Exception as e:
                    logger.error(f"[{self.peername}] Error processing line: {e}")
                finally:
                    self.line_queue.task_done()
        except asyncio.CancelledError:
            logger.debug(f"[{self.peername}] Line processing task cancelled")
            raise

    async def handle_line(self, line: bytes):
        """Process a single SMTP command line"""
        try:
            # Special handling for DATA state - collect message lines
            if self.state == 'DATA_RECEIVING':
                # Check for end of message marker (single dot on a line)
                if line == b'.':
                    await self.handle_message_data(self.message_data)
                else:
                    # Add line to message data (preserve original line endings)
                    if self.message_data:
                        self.message_data += b'\r\n'
                    self.message_data += line
                return

            line_str = line.decode('utf-8', errors='replace').strip()

            if not line_str:
                return

            logger.debug(f"[{self.peername}] << {line_str[:100]}")

            parts = line_str.split(None, 1)
            command = parts[0].upper() if parts else ''
            args = parts[1] if len(parts) > 1 else ''

            # Log command
            if self.current_account:
                Metrics.smtp_commands_total.labels(
                    account=self.current_account.email,
                    command=command
                ).inc()

            if command == 'EHLO':
                await self.handle_ehlo(args)
            elif command == 'HELO':
                await self.handle_helo(args)
            elif command == 'AUTH':
                await self.handle_auth(args)
            elif command == 'MAIL':
                await self.handle_mail(args)
            elif command == 'RCPT':
                await self.handle_rcpt(args)
            elif command == 'DATA':
                await self.handle_data()
            elif command == 'RSET':
                await self.handle_rset()
            elif command == 'QUIT':
                await self.handle_quit()
            elif command == 'NOOP':
                self.send_response(250, "OK")
            else:
                self.send_response(502, "Command not implemented")

        except Exception as e:
            logger.error(f"Error handling line: {e}")
            if self.current_account:
                Metrics.errors_total.labels(
                    account=self.current_account.email,
                    error_type='handler'
                ).inc()
            self.send_response(451, "Internal error")

    async def handle_ehlo(self, hostname: str):
        """Handle EHLO command"""
        self.send_response(250, "xoauth2-proxy", continue_response=True)
        self.send_response(250, "AUTH PLAIN", continue_response=True)
        self.send_response(250, "SIZE 52428800", continue_response=True)
        self.send_response(250, "8BITMIME", continue_response=False)
        self.state = 'HELO_RECEIVED'

        logger.info(f"[{self.peername}] EHLO received: {hostname}")

    async def handle_helo(self, hostname: str):
        """Handle HELO command"""
        self.send_response(250, f"xoauth2-proxy Hello {hostname}")
        self.state = 'HELO_RECEIVED'

        logger.info(f"[{self.peername}] HELO received: {hostname}")

    async def handle_auth(self, auth_data: str):
        """Handle AUTH PLAIN command"""
        start_time = time.time()

        try:
            # Parse AUTH PLAIN
            parts = auth_data.split()
            if len(parts) < 2 or parts[0].upper() != 'PLAIN':
                self.send_response(504, "AUTH mechanism not supported")
                return

            # Decode credentials
            encoded = parts[1]
            try:
                decoded = base64.b64decode(encoded).decode('utf-8')
            except Exception as e:
                logger.error(f"[{self.peername}] AUTH decode failed: {e}")
                Metrics.auth_attempts_total.labels(account='unknown', result='decode_error').inc()
                self.send_response(535, "AUTH mechanism not supported")
                return

            # Parse format: [authorize-id]\0authenticate-id\0passwd
            parts = decoded.split('\0')
            if len(parts) != 3:
                logger.error(f"[{self.peername}] AUTH format invalid")
                Metrics.auth_attempts_total.labels(account='unknown', result='format_error').inc()
                self.send_response(535, "AUTH mechanism not supported")
                return

            auth_email = parts[1]  # authenticate-id
            auth_password = parts[2]  # password (ignored, proxy uses refresh token)

            logger.info(f"[{self.peername}] AUTH attempt for {auth_email}")

            # Look up account
            account = await self.config_manager.get_by_email(auth_email)
            if not account:
                logger.warning(f"[{self.peername}] AUTH failed: account {auth_email} not found")
                Metrics.auth_attempts_total.labels(account=auth_email, result='not_found').inc()
                self.send_response(535, "authentication failed")
                return

            # Check and refresh token if needed
            async with account.lock:
                if account.token.is_expired():
                    logger.info(f"[{auth_email}] Token expired, refreshing")
                    token = await self.oauth_manager.get_or_refresh_token(account, force_refresh=True)
                    if not token:
                        logger.error(f"[{auth_email}] Token refresh failed")
                        Metrics.auth_attempts_total.labels(account=auth_email, result='token_refresh_failed').inc()
                        self.send_response(454, "Temporary authentication failure")
                        return

            # Verify token with upstream XOAUTH2
            if not await self.verify_xoauth2(account):
                logger.error(f"[{auth_email}] XOAUTH2 verification failed")
                Metrics.auth_attempts_total.labels(account=auth_email, result='xoauth2_failed').inc()
                self.send_response(535, "authentication failed")
                return

            # Authentication successful
            self.current_account = account
            self.authenticated = True

            duration = time.time() - start_time
            Metrics.auth_attempts_total.labels(account=auth_email, result='success').inc()
            Metrics.auth_duration_seconds.labels(account=auth_email).observe(duration)

            # Update connection count
            async with self.lock:
                account_id = account.account_id
                self.active_connections[account_id] += 1
                Metrics.smtp_connections_active.labels(account=auth_email).set(
                    self.active_connections[account_id]
                )

            logger.info(f"[{self.peername}] AUTH successful for {auth_email}")
            self.send_response(235, "2.7.0 Authentication successful")
            self.state = 'AUTH_RECEIVED'

        except Exception as e:
            logger.error(f"[{self.peername}] AUTH error: {e}")
            if self.current_account:
                Metrics.errors_total.labels(
                    account=self.current_account.email,
                    error_type='auth'
                ).inc()
            self.send_response(451, "Internal error")

    async def verify_xoauth2(self, account: AccountConfig) -> bool:
        """Verify token via XOAUTH2 authentication"""
        start_time = time.time()

        try:
            logger.info(f"[{account.email}] Verifying XOAUTH2 token (provider: {account.provider})")

            # Get current token
            async with account.lock:
                token = account.token
                if not token or not token.access_token:
                    logger.error(f"[{account.email}] No valid token available for XOAUTH2 verification")
                    return False

            # Construct XOAUTH2 string (using chr(1) for proper byte 0x01 separators)
            xoauth2_string = f"user={account.email}{chr(1)}auth=Bearer {token.access_token}{chr(1)}{chr(1)}"
            xoauth2_b64 = base64.b64encode(xoauth2_string.encode('utf-8')).decode('utf-8')

            logger.debug(
                f"[{account.email}] XOAUTH2 Auth: "
                f"user={account.email}, token_length={len(token.access_token)}, "
                f"expires_in={token.expires_in_seconds()}s"
            )

            # Basic validation
            if not token.access_token or len(token.access_token) < 10:
                logger.error(f"[{account.email}] Invalid token format (too short)")
                return False

            logger.info(
                f"[{account.email}] XOAUTH2 verification: "
                f"string constructed successfully "
                f"(provider={account.provider}, endpoint={account.oauth_endpoint})"
            )

            duration = time.time() - start_time
            Metrics.upstream_auth_total.labels(account=account.email, result='success').inc()
            Metrics.upstream_auth_duration_seconds.labels(account=account.email).observe(duration)

            return True

        except Exception as e:
            duration = time.time() - start_time
            Metrics.upstream_auth_total.labels(account=account.email, result='failure').inc()
            Metrics.upstream_auth_duration_seconds.labels(account=account.email).observe(duration)

            logger.error(f"[{account.email}] XOAUTH2 verification failed: {e}")
            Metrics.errors_total.labels(account=account.email, error_type='xoauth2_verify').inc()
            return False

    async def handle_mail(self, args: str):
        """Handle MAIL FROM command"""
        if not self.authenticated:
            self.send_response(530, "authentication required")
            return

        match = re.search(r'FROM:<(.+?)>', args, re.IGNORECASE)
        if not match:
            self.send_response(501, "Syntax error")
            return

        self.mail_from = match.group(1)
        logger.info(f"[{self.current_account.email}] MAIL FROM: {self.mail_from}")
        self.send_response(250, "2.1.0 OK")

    async def handle_rcpt(self, args: str):
        """Handle RCPT TO command"""
        if not self.mail_from:
            self.send_response(503, "MAIL first")
            return

        match = re.search(r'TO:<(.+?)>', args, re.IGNORECASE)
        if not match:
            self.send_response(501, "Syntax error")
            return

        rcpt_to = match.group(1)
        self.rcpt_tos.append(rcpt_to)
        logger.info(f"[{self.current_account.email}] RCPT TO: {rcpt_to}")
        self.send_response(250, "2.1.5 OK")

    async def handle_data(self):
        """Handle DATA command"""
        if not self.mail_from:
            self.send_response(503, "MAIL first")
            return

        if not self.rcpt_tos:
            self.send_response(503, "RCPT first")
            return

        # Increment concurrency counter
        async with self.current_account.lock:
            self.current_account.concurrent_messages += 1
            Metrics.concurrent_messages.labels(
                account=self.current_account.email
            ).set(self.current_account.concurrent_messages)

        logger.info(f"[{self.current_account.email}] DATA: {len(self.rcpt_tos)} recipients")
        self.send_response(354, "Start mail input; end with <CRLF>.<CRLF>")
        self.state = 'DATA_RECEIVING'
        self.message_data = b''

    async def handle_message_data(self, data: bytes):
        """Handle message data (called when <CRLF>.<CRLF> received)"""
        try:
            logger.info(f"[{self.current_account.email}] Processing message for {len(self.rcpt_tos)} recipients")

            # Send message via XOAUTH2 to upstream SMTP server
            success, smtp_code, smtp_message = await self.upstream_relay.send_message(
                account=self.current_account,
                message_data=self.message_data,
                mail_from=self.mail_from,
                rcpt_tos=self.rcpt_tos,
                dry_run=self.dry_run
            )

            # Update concurrency
            async with self.current_account.lock:
                self.current_account.concurrent_messages -= 1
                Metrics.concurrent_messages.labels(
                    account=self.current_account.email
                ).set(self.current_account.concurrent_messages)

            # Send response to PowerMTA
            if success:
                self.send_response(250, "2.0.0 OK")
                logger.info(f"[{self.current_account.email}] Relayed message successfully")
            else:
                self.send_response(smtp_code, smtp_message)
                logger.warning(f"[{self.current_account.email}] Relay failed: {smtp_code} {smtp_message}")

            # Reset message state
            self.mail_from = None
            self.rcpt_tos = []
            self.message_data = b''
            self.state = 'AUTH_RECEIVED'

        except Exception as e:
            logger.error(f"[{self.current_account.email}] Error processing message: {e}")
            Metrics.errors_total.labels(
                account=self.current_account.email,
                error_type='message_processing'
            ).inc()

            try:
                async with self.current_account.lock:
                    self.current_account.concurrent_messages -= 1
                    Metrics.concurrent_messages.labels(
                        account=self.current_account.email
                    ).set(self.current_account.concurrent_messages)
            except:
                pass

            self.send_response(450, "4.4.2 Temporary service failure")

            self.mail_from = None
            self.rcpt_tos = []
            self.message_data = b''
            self.state = 'AUTH_RECEIVED'

    async def handle_rset(self):
        """Handle RSET command"""
        self.mail_from = None
        self.rcpt_tos = []
        self.message_data = b''
        self.state = 'AUTH_RECEIVED' if self.authenticated else 'HELO_RECEIVED'

        logger.info(f"[{self.peername}] RSET")
        self.send_response(250, "2.0.0 OK")

    async def handle_quit(self):
        """Handle QUIT command"""
        logger.info(f"[{self.peername}] QUIT")
        self.send_response(221, "2.0.0 Goodbye")
        self.transport.close()

    def send_response(self, code: int, message: str, continue_response: bool = False):
        """Send SMTP response"""
        separator = '-' if continue_response else ' '
        response = f"{code}{separator}{message}\r\n".encode('utf-8')
        self.transport.write(response)

        safe_msg = message[:100] if len(message) <= 100 else message[:97] + "..."
        logger.debug(f"[{self.peername}] >> {code}{separator}{safe_msg}")
