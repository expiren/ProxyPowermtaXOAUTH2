"""SMTP protocol handler for incoming connections"""

import asyncio
import base64
import logging
import re
from typing import List, Optional

from src.accounts.models import AccountConfig
from src.oauth2.manager import OAuth2Manager
from src.smtp.upstream import UpstreamRelay

logger = logging.getLogger('xoauth2_proxy')

# Pre-encoded common SMTP responses (bytes passthrough optimization)
# Avoids repeated encode() calls for high-frequency responses
_RESPONSE_OK = b'250 OK\r\n'
_RESPONSE_250_OK = b'250 2.1.0 OK\r\n'
_RESPONSE_250_DATA_OK = b'250 2.0.0 OK\r\n'
_RESPONSE_354_START_DATA = b'354 Start mail input; end with <CRLF>.<CRLF>\r\n'
_RESPONSE_502_NOT_IMPL = b'502 Command not implemented\r\n'
_RESPONSE_503_BAD_SEQ = b'503 Bad sequence of commands\r\n'

# Pre-compiled regex patterns (performance optimization)
# Avoids re-compiling on every MAIL/RCPT command (1666+ compilations/sec at 833 msg/sec)
_MAIL_FROM_PATTERN = re.compile(r'FROM:<(.+?)>', re.IGNORECASE)
_RCPT_TO_PATTERN = re.compile(r'TO:<(.+?)>', re.IGNORECASE)


class SMTPProxyHandler(asyncio.Protocol):
    """SMTP protocol handler"""

    def __init__(
        self,
        config_manager,
        oauth_manager: OAuth2Manager,
        upstream_relay: UpstreamRelay,
        dry_run: bool = False,
        global_concurrency_limit: int = 100,
        global_semaphore: asyncio.Semaphore = None,
        backpressure_queue_size: int = 1000
    ):
        self.config_manager = config_manager
        self.oauth_manager = oauth_manager
        self.upstream_relay = upstream_relay
        self.dry_run = dry_run
        self.global_concurrency_limit = global_concurrency_limit
        self.global_semaphore = global_semaphore  # ✅ Global semaphore for backpressure

        self.transport = None
        self.peername = None
        self.current_account: Optional[AccountConfig] = None
        self.authenticated = False
        self.mail_from = None
        self.rcpt_tos: List[str] = []
        self.message_data = b''
        self.buffer = b''
        self.state = 'INITIAL'

        # Line processing queue (✅ with maxsize for backpressure)
        self.line_queue = asyncio.Queue(maxsize=backpressure_queue_size)
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
            # Decrement active connections count (unified tracking in account object)
            if self.current_account.active_connections > 0:
                self.current_account.active_connections -= 1

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

            # Bytes passthrough optimization: work with bytes for command parsing
            # Only decode when we need the arguments (avoids decode/encode overhead)
            line_stripped = line.strip()

            if not line_stripped:
                return

            # Fast command detection with bytes (no decode needed!)
            # Split on first space to get command and args as bytes
            parts_bytes = line_stripped.split(None, 1)
            if not parts_bytes:
                return

            command_bytes = parts_bytes[0].upper()

            # Decode command for logging/comparison (only the command, not args yet)
            command = command_bytes.decode('ascii', errors='replace')
            logger.debug(f"[{self.peername}] << {command}")

            # Decode args only when needed by specific commands
            args = parts_bytes[1].decode('utf-8', errors='replace') if len(parts_bytes) > 1 else ''

            # Log command
            if command:
                pass  # Previously tracked in metrics

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
                self.send_response(535, "AUTH mechanism not supported")
                return

            # Parse format: [authorize-id]\0authenticate-id\0passwd
            parts = decoded.split('\0')
            if len(parts) != 3:
                logger.error(f"[{self.peername}] AUTH format invalid")
                self.send_response(535, "AUTH mechanism not supported")
                return

            auth_email = parts[1]  # authenticate-id
            auth_password = parts[2]  # password (ignored, proxy uses refresh token)

            logger.info(f"[{self.peername}] AUTH attempt for {auth_email}")

            # Look up account
            account = await self.config_manager.get_by_email(auth_email)
            if not account:
                logger.warning(f"[{self.peername}] AUTH failed: account {auth_email} not found")
                self.send_response(535, "authentication failed")
                return

            # Check and refresh token if needed (consolidated under account lock)
            async with account.lock:
                # Defensive check: handle None token or expired token
                if account.token is None or account.token.is_expired():
                    token_status = 'missing' if account.token is None else 'expired'
                    logger.info(f"[{auth_email}] Token {token_status}, refreshing")
                    token = await self.oauth_manager.get_or_refresh_token(account, force_refresh=True)
                    if not token:
                        logger.error(f"[{auth_email}] Token refresh failed")
                        self.send_response(454, "Temporary authentication failure")
                        return

                # ✅ REMOVED: Fake XOAUTH2 verification (was just returning True)
                # Token validation happens during OAuth2 refresh
                # First message relay will fail if token is actually bad (acceptable tradeoff)

                # Authentication successful - update connection count (still under account lock)
                # This consolidates all auth operations under ONE lock instead of multiple
                # Unified tracking: use account.active_connections instead of separate dict
                account.active_connections += 1

            # Set state outside of lock
            self.current_account = account
            self.authenticated = True

            logger.info(f"[{self.peername}] AUTH successful for {auth_email}")
            self.send_response(235, "2.7.0 Authentication successful")
            self.state = 'AUTH_RECEIVED'

        except Exception as e:
            logger.error(f"[{self.peername}] AUTH error: {e}")
            self.send_response(451, "Internal error")

    async def handle_mail(self, args: str):
        """Handle MAIL FROM command"""
        if not self.authenticated:
            self.send_response(530, "authentication required")
            return

        match = _MAIL_FROM_PATTERN.search(args)
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

        match = _RCPT_TO_PATTERN.search(args)
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

        # ✅ Check per-account concurrency limit BEFORE accepting message
        async with self.current_account.lock:
            if not self.current_account.can_send():
                logger.warning(
                    f"[{self.current_account.email}] Per-account concurrency limit reached "
                    f"({self.current_account.concurrent_messages}/{self.current_account.max_concurrent_messages})"
                )
                # Temporary failure - client should retry
                self.send_response(451, "4.4.5 Server busy - per-account limit reached, try again later")
                # Reset message state
                self.mail_from = None
                self.rcpt_tos = []
                return

            # ✅ Increment concurrency counter after check passes
            self.current_account.concurrent_messages += 1

        logger.info(
            f"[{self.current_account.email}] DATA: {len(self.rcpt_tos)} recipients "
            f"(concurrent={self.current_account.concurrent_messages}/{self.current_account.max_concurrent_messages})"
        )
        self.send_response(354, "Start mail input; end with <CRLF>.<CRLF>")
        self.state = 'DATA_RECEIVING'
        self.message_data = b''

    async def handle_message_data(self, data: bytes):
        """Handle message data (called when <CRLF>.<CRLF> received)"""
        try:
            logger.info(f"[{self.current_account.email}] Processing message for {len(self.rcpt_tos)} recipients")

            # ✅ Acquire global semaphore for backpressure (limits concurrent message processing)
            if self.global_semaphore:
                async with self.global_semaphore:
                    # Send message via XOAUTH2 to upstream SMTP server
                    success, smtp_code, smtp_message = await self.upstream_relay.send_message(
                        account=self.current_account,
                        message_data=self.message_data,
                        mail_from=self.mail_from,
                        rcpt_tos=self.rcpt_tos,
                        dry_run=self.dry_run
                    )
            else:
                # Fallback if no global semaphore provided (backward compatibility)
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

            try:
                async with self.current_account.lock:
                    self.current_account.concurrent_messages -= 1
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
        """Send SMTP response (optimized with pre-encoded common responses)"""
        # Fast path: use pre-encoded responses for common cases (avoids encode() overhead)
        if not continue_response:
            if code == 250 and message == "OK":
                self.transport.write(_RESPONSE_OK)
                logger.debug(f"[{self.peername}] >> 250 OK")
                return
            elif code == 250 and message == "2.1.0 OK":
                self.transport.write(_RESPONSE_250_OK)
                logger.debug(f"[{self.peername}] >> 250 2.1.0 OK")
                return
            elif code == 250 and message == "2.0.0 OK":
                self.transport.write(_RESPONSE_250_DATA_OK)
                logger.debug(f"[{self.peername}] >> 250 2.0.0 OK")
                return
            elif code == 354 and message == "Start mail input; end with <CRLF>.<CRLF>":
                self.transport.write(_RESPONSE_354_START_DATA)
                logger.debug(f"[{self.peername}] >> 354 Start mail input")
                return
            elif code == 502 and message == "Command not implemented":
                self.transport.write(_RESPONSE_502_NOT_IMPL)
                logger.debug(f"[{self.peername}] >> 502 Command not implemented")
                return

        # Slow path: encode on demand for uncommon responses
        separator = '-' if continue_response else ' '
        response = f"{code}{separator}{message}\r\n".encode('utf-8')
        self.transport.write(response)

        safe_msg = message[:100] if len(message) <= 100 else message[:97] + "..."
        logger.debug(f"[{self.peername}] >> {code}{separator}{safe_msg}")
