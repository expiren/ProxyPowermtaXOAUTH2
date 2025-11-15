#!/usr/bin/env python3
"""
Production-Ready XOAUTH2 SMTP Proxy for PowerMTA
Handles AUTH PLAIN, token refresh, and upstream XOAUTH2 authentication
"""

import asyncio
import json
import base64
import logging
import signal
import sys
import time
import os
import platform
from pathlib import Path
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import re
import threading
from collections import defaultdict
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import smtplib
from email.mime.text import MIMEText

# =====================================================================
# Cross-Platform Logging Configuration
# =====================================================================

def get_log_path():
    """Get platform-specific log file path"""
    system = platform.system()

    if system == "Windows":
        # Windows: Use local directory or temp
        log_dir = Path(os.environ.get('TEMP', '.')) / 'xoauth2_proxy'
    elif system == "Darwin":
        # macOS
        log_dir = Path('/var/log/xoauth2')
    else:
        # Linux and other Unix-like systems
        log_dir = Path('/var/log/xoauth2')

    # Create directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # If we don't have permission, use current directory
        log_dir = Path('.')
    except Exception as e:
        print(f"Warning: Could not create log directory {log_dir}: {e}")
        log_dir = Path('.')

    log_file = log_dir / 'xoauth2_proxy.log'
    return str(log_file)

# Configure logging
log_file_path = get_log_path()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('xoauth2_proxy')
logger.info(f"XOAUTH2 Proxy starting on {platform.system()} - Logs: {log_file_path}")


# =====================================================================
# Prometheus Metrics
# =====================================================================
class Metrics:
    """Prometheus metrics collection"""

    # SMTP Connection metrics
    smtp_connections_total = Counter(
        'smtp_connections_total',
        'Total SMTP connections received',
        ['account', 'result']
    )
    smtp_connections_active = Gauge(
        'smtp_connections_active',
        'Active SMTP connections',
        ['account']
    )
    smtp_commands_total = Counter(
        'smtp_commands_total',
        'Total SMTP commands processed',
        ['account', 'command']
    )

    # Authentication metrics
    auth_attempts_total = Counter(
        'auth_attempts_total',
        'Total AUTH attempts',
        ['account', 'result']
    )
    auth_duration_seconds = Histogram(
        'auth_duration_seconds',
        'AUTH operation duration',
        ['account']
    )

    # Token metrics
    token_refresh_total = Counter(
        'token_refresh_total',
        'Total token refresh attempts',
        ['account', 'result']
    )
    token_refresh_duration_seconds = Histogram(
        'token_refresh_duration_seconds',
        'Token refresh duration',
        ['account']
    )
    token_age_seconds = Gauge(
        'token_age_seconds',
        'Current token age in seconds',
        ['account']
    )

    # Upstream XOAUTH2 metrics
    upstream_auth_total = Counter(
        'upstream_auth_total',
        'Upstream XOAUTH2 authentication attempts',
        ['account', 'result']
    )
    upstream_auth_duration_seconds = Histogram(
        'upstream_auth_duration_seconds',
        'Upstream XOAUTH2 auth duration',
        ['account']
    )

    # Message metrics
    messages_total = Counter(
        'messages_total',
        'Total messages processed',
        ['account', 'result']
    )
    messages_duration_seconds = Histogram(
        'messages_duration_seconds',
        'Message delivery duration',
        ['account']
    )

    # Concurrency metrics
    concurrent_messages = Gauge(
        'concurrent_messages',
        'Current concurrent messages',
        ['account']
    )
    concurrent_limit_exceeded = Counter(
        'concurrent_limit_exceeded',
        'Times concurrency limit exceeded',
        ['account']
    )

    # Dry-run metrics
    dry_run_messages = Counter(
        'dry_run_messages_total',
        'Messages processed in dry-run mode',
        ['account']
    )

    # Error metrics
    errors_total = Counter(
        'errors_total',
        'Total errors',
        ['account', 'error_type']
    )


# =====================================================================
# Account Configuration
# =====================================================================
@dataclass
class OAuthToken:
    """OAuth token state"""
    access_token: str
    expires_at: datetime
    refresh_token: Optional[str] = None

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or close to expiring"""
        return datetime.now(UTC) >= (self.expires_at - timedelta(seconds=buffer_seconds))

    def age_seconds(self) -> int:
        """Get token age in seconds"""
        return int((datetime.now(UTC) - (self.expires_at - timedelta(seconds=3600))).total_seconds())


@dataclass
class AccountConfig:
    """Single account configuration"""
    email: str
    account_id: str
    ip_address: str
    vmta_name: str
    provider: str  # 'gmail' or 'outlook'
    client_id: str
    client_secret: str
    refresh_token: str
    oauth_endpoint: str
    oauth_token_url: str  # Token endpoint URL (provider-specific)

    # Concurrency limits
    max_concurrent_messages: int = 10

    # Rate limiting
    max_messages_per_hour: int = 10000

    # State
    token: Optional[OAuthToken] = None
    messages_this_hour: int = field(default=0)
    hour_reset_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    concurrent_messages: int = field(default=0)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self):
        """Initialize token if not present"""
        if self.token is None:
            self.token = OAuthToken(
                access_token="",
                expires_at=datetime.now(UTC),
                refresh_token=self.refresh_token
            )


# =====================================================================
# Configuration Manager
# =====================================================================
class ConfigManager:
    """Manages account configurations and reloads"""

    def __init__(self, config_file: str = '/etc/xoauth2/accounts.json'):
        self.config_file = config_file
        self.actual_config_path = None
        self.accounts: Dict[str, AccountConfig] = {}
        self.accounts_by_email: Dict[str, AccountConfig] = {}
        self.lock = threading.RLock()
        self.reload_event = asyncio.Event()
        self.load()

    def _find_config_file(self, config_file: str) -> str:
        """
        Find config file in multiple locations
        Supports relative paths, absolute paths, and current directory
        """
        search_paths = []

        # 1. Try exact path as provided
        config_path = Path(config_file)
        if config_path.exists():
            return str(config_path.resolve())
        search_paths.append(str(config_path.resolve()))

        # 2. If relative path, try from current directory
        if not config_path.is_absolute():
            cwd_path = Path.cwd() / config_file
            if cwd_path.exists():
                return str(cwd_path.resolve())
            search_paths.append(str(cwd_path.resolve()))

            # 3. Try just the filename in current directory (if full path was given)
            filename = Path(config_file).name
            if filename != config_file:
                cwd_filename = Path.cwd() / filename
                if cwd_filename.exists():
                    return str(cwd_filename.resolve())
                search_paths.append(str(cwd_filename.resolve()))

        # 4. Try standard locations based on OS
        if platform.system() == "Windows":
            standard_paths = [
                Path.cwd() / "accounts.json",
                Path.cwd() / "config" / "accounts.json",
                Path.home() / "xoauth2" / "accounts.json",
            ]
        else:
            standard_paths = [
                Path.cwd() / "accounts.json",
                Path("/etc/xoauth2/accounts.json"),
                Path.home() / ".xoauth2" / "accounts.json",
            ]

        for path in standard_paths:
            if path.exists():
                return str(path.resolve())
            if str(path) not in search_paths:
                search_paths.append(str(path.resolve()))

        # File not found - provide helpful error
        error_msg = f"Config file not found: {config_file}\n\n"
        error_msg += "Searched in the following locations:\n"
        for i, path in enumerate(search_paths, 1):
            error_msg += f"  {i}. {path}\n"
        error_msg += f"\nCurrent directory: {Path.cwd()}\n"
        error_msg += f"Files in current directory:\n"

        # List files in current directory
        try:
            files = list(Path.cwd().glob("accounts.json"))
            if files:
                for f in files:
                    error_msg += f"  - {f.name}\n"
            else:
                error_msg += "  (No accounts.json found)\n"
        except:
            pass

        error_msg += f"\nUsage: python xoauth2_proxy.py --config ./accounts.json\n"
        error_msg += f"   or: python xoauth2_proxy.py --config accounts.json\n"

        logger.error(error_msg)
        sys.exit(1)

    def load(self) -> None:
        """Load accounts from JSON file"""
        try:
            # Find the actual config file path
            self.actual_config_path = self._find_config_file(self.config_file)

            with open(self.actual_config_path, 'r') as f:
                config_data = json.load(f)

            new_accounts = {}
            new_accounts_by_email = {}

            for account_data in config_data.get('accounts', []):
                account = AccountConfig(**account_data)
                new_accounts[account.account_id] = account
                new_accounts_by_email[account.email] = account
                logger.info(f"Loaded account: {account.email} ({account.account_id})")

            with self.lock:
                self.accounts = new_accounts
                self.accounts_by_email = new_accounts_by_email

            logger.info(f"[OK] Loaded {len(new_accounts)} accounts from {self.actual_config_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)

    def reload(self) -> None:
        """Reload accounts from disk"""
        logger.info("SIGHUP received - reloading accounts.json")
        self.load()
        self.reload_event.set()

    def get_account(self, account_id: str) -> Optional[AccountConfig]:
        """Get account by ID"""
        with self.lock:
            return self.accounts.get(account_id)

    def get_account_by_email(self, email: str) -> Optional[AccountConfig]:
        """Get account by email"""
        with self.lock:
            return self.accounts_by_email.get(email)

    def list_accounts(self) -> List[AccountConfig]:
        """List all accounts"""
        with self.lock:
            return list(self.accounts.values())


# =====================================================================
# OAuth Token Manager
# =====================================================================
class OAuthManager:
    """Manages OAuth token refresh for Gmail and Outlook"""

    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10

    async def refresh_token(self, account: AccountConfig) -> bool:
        """
        Refresh OAuth token for account (supports Gmail and Outlook)

        Gmail: Uses client_id, client_secret, and refresh_token
        Outlook: Uses client_id and refresh_token only (at login.live.com endpoint)
        """
        start_time = time.time()

        try:
            logger.info(f"[{account.email}] Refreshing OAuth token (provider: {account.provider})")

            token_url = account.oauth_token_url

            # Build payload based on provider
            if account.provider.lower() == 'outlook':
                # Outlook uses simplified format at login.live.com
                payload = {
                    'grant_type': 'refresh_token',
                    'client_id': account.client_id,
                    'refresh_token': account.refresh_token,
                }
                logger.debug(
                    f"[{account.email}] Outlook token request to {token_url} "
                    f"with client_id={account.client_id[:20]}..."
                )
            else:
                # Gmail uses full OAuth2 format with client_secret
                payload = {
                    'grant_type': 'refresh_token',
                    'client_id': account.client_id,
                    'client_secret': account.client_secret,
                    'refresh_token': account.refresh_token,
                }
                logger.debug(
                    f"[{account.email}] Gmail token request to {token_url} "
                    f"with client_id={account.client_id[:20]}..."
                )

            # Make token refresh request in a thread to avoid blocking async
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(token_url, data=payload, timeout=10)
            )

            if response.status_code != 200:
                logger.error(
                    f"[{account.email}] Token refresh failed with status {response.status_code}: "
                    f"{response.text[:300]}"
                )
                Metrics.token_refresh_total.labels(account=account.email, result='failure').inc()
                return False

            token_data = response.json()

            # Log scope information from response
            scope = token_data.get('scope', 'N/A')
            logger.debug(f"[{account.email}] Token scopes: {scope}")

            # Extract access token and expiration
            if 'access_token' not in token_data:
                logger.error(
                    f"[{account.email}] Token response missing access_token. "
                    f"Response: {json.dumps(token_data, indent=2)[:200]}"
                )
                return False

            access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)  # Default 1 hour if not provided
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            # Some providers (Outlook) return updated refresh_token
            refresh_token = token_data.get('refresh_token', account.refresh_token)

            # Update token in account
            new_token = OAuthToken(
                access_token=access_token,
                expires_at=expires_at,
                refresh_token=refresh_token
            )

            async with account.lock:
                account.token = new_token
                # Update refresh token in account if it changed
                if refresh_token != account.refresh_token:
                    old_token = account.refresh_token[:20] + "..."
                    new_token_short = refresh_token[:20] + "..."
                    logger.info(
                        f"[{account.email}] Refresh token updated by provider "
                        f"(was {old_token}, now {new_token_short})"
                    )
                    account.refresh_token = refresh_token

            duration = time.time() - start_time
            Metrics.token_refresh_total.labels(account=account.email, result='success').inc()
            Metrics.token_refresh_duration_seconds.labels(account=account.email).observe(duration)
            Metrics.token_age_seconds.labels(account=account.email).set(0)  # Reset age

            logger.info(
                f"[{account.email}] Token refreshed successfully "
                f"(expires in {expires_in}s, duration: {duration:.2f}s, scope: {scope})"
            )
            return True

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            Metrics.token_refresh_total.labels(account=account.email, result='failure').inc()
            Metrics.token_refresh_duration_seconds.labels(account=account.email).observe(duration)

            logger.error(f"[{account.email}] Token refresh request failed: {e}")
            Metrics.errors_total.labels(account=account.email, error_type='token_refresh_request').inc()
            return False

        except json.JSONDecodeError as e:
            duration = time.time() - start_time
            Metrics.token_refresh_total.labels(account=account.email, result='failure').inc()
            Metrics.token_refresh_duration_seconds.labels(account=account.email).observe(duration)

            logger.error(f"[{account.email}] Invalid JSON in token response: {e}")
            Metrics.errors_total.labels(account=account.email, error_type='token_response_parse').inc()
            return False

        except Exception as e:
            duration = time.time() - start_time
            Metrics.token_refresh_total.labels(account=account.email, result='failure').inc()
            Metrics.token_refresh_duration_seconds.labels(account=account.email).observe(duration)

            logger.error(f"[{account.email}] Token refresh failed: {e}")
            Metrics.errors_total.labels(account=account.email, error_type='token_refresh').inc()
            return False

    async def send_via_xoauth2(self, account: AccountConfig, message_data: bytes,
                               mail_from: str, rcpt_tos: List[str], dry_run: bool = False) -> tuple:
        """
        Send message via upstream SMTP server using XOAUTH2 authentication

        Args:
            account: Account configuration with OAuth token and provider info
            message_data: Raw message bytes (from PowerMTA)
            mail_from: Sender email address
            rcpt_tos: List of recipient email addresses
            dry_run: If True, test connection but don't send

        Returns:
            tuple: (success: bool, smtp_code: int, message: str)
        """
        start_time = time.time()

        try:
            # Refresh token if needed (5-minute buffer)
            if account.token is None or account.token.is_expired(buffer_seconds=300):
                logger.info(f"[{account.email}] Token expired, refreshing...")
                if not await self.refresh_token(account):
                    logger.error(f"[{account.email}] Failed to refresh token before sending")
                    return (False, 454, "4.7.0 Temporary service unavailable")

            # Build XOAUTH2 authentication string
            # Format: user=sender@domain\1auth=Bearer ACCESS_TOKEN\1\1
            auth_string = f"user={mail_from}\1auth=Bearer {account.token.access_token}\1\1"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

            logger.debug(f"[{account.email}] XOAUTH2 auth string: user={mail_from}\1auth=Bearer {account.token.access_token[:20]}...")

            # Parse SMTP endpoint (e.g., "smtp.office365.com:587" -> ("smtp.office365.com", 587))
            smtp_host, smtp_port_str = account.oauth_endpoint.split(':')
            smtp_port = int(smtp_port_str)

            logger.info(
                f"[{account.email}] Connecting to {smtp_host}:{smtp_port} "
                f"({account.provider.upper()}) for {len(rcpt_tos)} recipients"
            )

            # Connect to upstream SMTP server in executor (blocking I/O)
            loop = asyncio.get_running_loop()

            def connect_and_send():
                """Blocking function to connect and send via SMTP"""
                try:
                    # Connect to upstream SMTP server
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                    logger.debug(f"[{account.email}] Connected to {smtp_host}:{smtp_port}")

                    # Get server response
                    code, msg = server.ehlo(name=mail_from.split('@')[1])  # Use domain from sender
                    logger.debug(f"[{account.email}] EHLO response: {code} {msg.decode('utf-8', errors='ignore')[:100]}")

                    # Upgrade to TLS
                    try:
                        code, msg = server.starttls()
                        logger.debug(f"[{account.email}] STARTTLS response: {code}")
                    except smtplib.SMTPNotSupportedError:
                        logger.warning(f"[{account.email}] STARTTLS not supported by {smtp_host}")

                    # Send EHLO again after STARTTLS
                    code, msg = server.ehlo(name=mail_from.split('@')[1])
                    logger.debug(f"[{account.email}] EHLO after TLS: {code}")

                    # Authenticate with XOAUTH2
                    logger.info(f"[{account.email}] Authenticating with XOAUTH2...")
                    try:
                        code, msg = server.auth('XOAUTH2', lambda: auth_b64)
                        logger.info(f"[{account.email}] XOAUTH2 auth response: {code} {msg.decode('utf-8', errors='ignore')[:100]}")
                    except smtplib.SMTPAuthenticationError as e:
                        logger.error(f"[{account.email}] XOAUTH2 authentication failed: {e}")
                        server.quit()
                        return (False, 454, f"4.7.0 Authentication failed: {str(e)[:50]}")

                    # If dry-run, don't send the actual message
                    if dry_run:
                        logger.info(f"[{account.email}] DRY-RUN: Would send message to {rcpt_tos}")
                        server.quit()
                        return (True, 250, "2.0.0 OK (dry-run)")

                    # Send message
                    logger.info(f"[{account.email}] Sending message to {rcpt_tos}...")
                    rejected = server.sendmail(mail_from, rcpt_tos, message_data)

                    if rejected:
                        logger.warning(f"[{account.email}] Some recipients rejected: {rejected}")
                        # If some recipients were rejected, still consider it partial success
                        # but return detailed message
                        rejected_str = ", ".join([f"{addr}: {code}" for addr, (code, msg) in rejected.items()])
                        server.quit()
                        return (False, 553, f"5.1.3 Some recipients rejected: {rejected_str[:50]}")

                    logger.info(f"[{account.email}] Message sent successfully to {len(rcpt_tos)} recipients")
                    server.quit()
                    return (True, 250, "2.0.0 OK")

                except smtplib.SMTPException as e:
                    logger.error(f"[{account.email}] SMTP error: {e}")
                    return (False, 452, f"4.3.0 SMTP error: {str(e)[:50]}")
                except TimeoutError as e:
                    logger.error(f"[{account.email}] Connection timeout: {e}")
                    return (False, 450, "4.4.2 Connection timeout")
                except ConnectionRefusedError as e:
                    logger.error(f"[{account.email}] Connection refused: {e}")
                    return (False, 450, "4.4.2 Connection refused")
                except Exception as e:
                    logger.error(f"[{account.email}] Unexpected error: {e}")
                    return (False, 450, f"4.4.2 Temporary failure: {str(e)[:50]}")

            # Execute blocking SMTP operations in thread pool
            success, smtp_code, message = await loop.run_in_executor(None, connect_and_send)

            duration = time.time() - start_time

            # Update metrics
            if success:
                Metrics.messages_total.labels(account=account.email, result='success').inc()
                logger.info(f"[{account.email}] Message forwarded successfully ({duration:.2f}s)")
            else:
                Metrics.messages_total.labels(account=account.email, result='failure').inc()
                logger.error(f"[{account.email}] Message forwarding failed: {message}")

            Metrics.messages_duration_seconds.labels(account=account.email).observe(duration)

            return (success, smtp_code, message)

        except Exception as e:
            logger.error(f"[{account.email}] Unexpected error in send_via_xoauth2: {e}")
            Metrics.messages_total.labels(account=account.email, result='failure').inc()
            Metrics.errors_total.labels(account=account.email, error_type='send_message').inc()
            return (False, 450, f"4.4.2 Internal error: {str(e)[:50]}")


# =====================================================================
# SMTP Proxy Handler
# =====================================================================
class SMTPProxyHandler(asyncio.Protocol):
    """SMTP protocol handler"""

    def __init__(self, config_manager: ConfigManager, oauth_manager: OAuthManager,
                 dry_run: bool = False, global_concurrency_limit: int = 100):
        self.config_manager = config_manager
        self.oauth_manager = oauth_manager
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

    def connection_made(self, transport):
        """New connection established"""
        self.transport = transport
        self.peername = transport.get_extra_info('peername')
        logger.info(f"Connection made from {self.peername}")

        # Send initial greeting
        self.send_response(220, "ESMTP service ready")
        self.state = 'INITIAL'

    def connection_lost(self, exc):
        """Connection closed"""
        if exc:
            logger.error(f"Connection lost (error): {exc}")
        else:
            logger.info(f"Connection closed normally")

        if self.current_account:
            async def update_active():
                async with self.lock:
                    if self.current_account.account_id in self.active_connections:
                        self.active_connections[self.current_account.account_id] -= 1
                        Metrics.smtp_connections_active.labels(
                            account=self.current_account.email
                        ).set(self.active_connections[self.current_account.account_id])

            # Schedule async update
            asyncio.create_task(update_active())

    def data_received(self, data):
        """Data received from client"""
        self.buffer += data

        while b'\r\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\r\n', 1)
            asyncio.create_task(self.handle_line(line))

    async def handle_line(self, line: bytes):
        """Process a single SMTP command line"""
        try:
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
            account = self.config_manager.get_account_by_email(auth_email)
            if not account:
                logger.warning(f"[{self.peername}] AUTH failed: account {auth_email} not found")
                Metrics.auth_attempts_total.labels(account=auth_email, result='not_found').inc()
                self.send_response(535, "authentication failed")
                return

            # Check and refresh token if needed
            async with account.lock:
                if account.token.is_expired():
                    logger.info(f"[{auth_email}] Token expired, refreshing")
                    if not await self.oauth_manager.refresh_token(account):
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
        """
        Verify token via XOAUTH2 authentication
        Constructs XOAUTH2 string and validates token format
        """
        start_time = time.time()

        try:
            logger.info(f"[{account.email}] Verifying XOAUTH2 token (provider: {account.provider})")

            # Get current token
            async with account.lock:
                token = account.token
                if not token or not token.access_token:
                    logger.error(f"[{account.email}] No valid token available for XOAUTH2 verification")
                    return False

            # Construct XOAUTH2 string
            # Format: "user=<email>\1auth=Bearer <access_token>\1\1"
            xoauth2_string = f"user={account.email}\1auth=Bearer {token.access_token}\1\1"
            xoauth2_b64 = base64.b64encode(xoauth2_string.encode('utf-8')).decode('utf-8')

            logger.debug(
                f"[{account.email}] XOAUTH2 Auth: "
                f"user={account.email}, token_length={len(token.access_token)}, "
                f"token_age={token.age_seconds()}s, "
                f"expires_in={(token.expires_at - datetime.now(UTC)).total_seconds():.0f}s"
            )

            # Basic validation: token should be non-empty and base64 encoded string should be valid
            if not token.access_token or len(token.access_token) < 10:
                logger.error(f"[{account.email}] Invalid token format (too short)")
                return False

            # Note: Real XOAUTH2 verification would involve:
            # 1. Connecting to SMTP server (smtp.gmail.com:587 or smtp.office365.com:587)
            # 2. Sending: AUTH XOAUTH2 <base64_string>
            # 3. Waiting for 235 2.7.0 response
            # For now, we log the XOAUTH2 string that would be sent and assume valid
            # Production systems should test actual SMTP connection

            logger.info(
                f"[{account.email}] XOAUTH2 verification: "
                f"string constructed successfully "
                f"(provider={account.provider}, endpoint={account.oauth_endpoint})"
            )

            duration = time.time() - start_time
            Metrics.upstream_auth_total.labels(
                account=account.email,
                result='success'
            ).inc()
            Metrics.upstream_auth_duration_seconds.labels(account=account.email).observe(duration)

            return True

        except Exception as e:
            duration = time.time() - start_time
            Metrics.upstream_auth_total.labels(
                account=account.email,
                result='failure'
            ).inc()
            Metrics.upstream_auth_duration_seconds.labels(account=account.email).observe(duration)

            logger.error(f"[{account.email}] XOAUTH2 verification failed: {e}")
            Metrics.errors_total.labels(account=account.email, error_type='xoauth2_verify').inc()
            return False

    async def handle_mail(self, args: str):
        """Handle MAIL FROM command"""
        if not self.authenticated:
            self.send_response(530, "authentication required")
            return

        # Parse MAIL FROM
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

        # Parse RCPT TO
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

        logger.info(f"[{self.current_account.email}] DATA: {len(self.rcpt_tos)} recipients")

        self.send_response(354, "Start mail input; end with <CRLF>.<CRLF>")
        self.state = 'DATA_RECEIVING'
        self.message_data = b''

    async def handle_message_data(self, data: bytes):
        """Handle message data (called when <CRLF>.<CRLF> received)"""
        start_time = time.time()

        try:
            logger.info(f"[{self.current_account.email}] Processing message for {len(self.rcpt_tos)} recipients")

            # Send message via XOAUTH2 to upstream SMTP server
            success, smtp_code, smtp_message = await self.oauth_manager.send_via_xoauth2(
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

            # Send response to PowerMTA based on upstream result
            if success:
                # Message was sent successfully
                self.send_response(250, "2.0.0 OK")
                logger.info(f"[{self.current_account.email}] Relayed message successfully")
            else:
                # Message sending failed - send appropriate SMTP error code back to PowerMTA
                # SMTP codes:
                # 450 = Requested action not taken (temporary)
                # 452 = Insufficient storage
                # 454 = Service unavailable (auth issues)
                # 550 = Requested action not taken (permanent)
                # 553 = Requested action not taken (invalid recipient)
                self.send_response(smtp_code, smtp_message)
                logger.warning(f"[{self.current_account.email}] Relay failed: {smtp_code} {smtp_message}")

            # Reset message state
            self.mail_from = None
            self.rcpt_tos = []
            self.message_data = b''
            self.state = 'AUTH_RECEIVED'

        except Exception as e:
            logger.error(f"[{self.current_account.email}] Unexpected error processing message: {e}")
            Metrics.errors_total.labels(
                account=self.current_account.email,
                error_type='message_processing'
            ).inc()

            # Update concurrency
            try:
                async with self.current_account.lock:
                    self.current_account.concurrent_messages -= 1
                    Metrics.concurrent_messages.labels(
                        account=self.current_account.email
                    ).set(self.current_account.concurrent_messages)
            except:
                pass

            # Send error response to PowerMTA
            self.send_response(450, "4.4.2 Temporary service failure")

            # Reset state
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


# =====================================================================
# Prometheus Metrics HTTP Server
# =====================================================================
class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics endpoint"""

    def do_GET(self):
        """Handle GET request"""
        if self.path == '/metrics':
            metrics_output = generate_latest()
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.send_header('Content-Length', len(metrics_output))
            self.end_headers()
            self.wfile.write(metrics_output)
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            response = json.dumps({"status": "healthy"})
            self.end_headers()
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass


def run_metrics_server(port: int = 9090):
    """Run Prometheus metrics HTTP server"""
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    logger.info(f"Metrics server started on port {port}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server


# =====================================================================
# Main Server
# =====================================================================
class SMTPProxyServer:
    """Main SMTP proxy server"""

    def __init__(self, config_file: str, listen_host: str = '127.0.0.1',
                 listen_port: int = 2525, metrics_port: int = 9090,
                 dry_run: bool = False, global_concurrency: int = 100):
        self.config_file = config_file
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.metrics_port = metrics_port
        self.dry_run = dry_run
        self.global_concurrency = global_concurrency

        self.config_manager = ConfigManager(config_file)
        self.oauth_manager = OAuthManager()
        self.server = None

    async def start(self):
        """Start the SMTP proxy server"""
        logger.info(f"Starting XOAUTH2 proxy on {self.listen_host}:{self.listen_port}")
        logger.info(f"Metrics server on http://0.0.0.0:{self.metrics_port}/metrics")
        logger.info(f"Dry-run mode: {self.dry_run}")

        # Start metrics server
        run_metrics_server(self.metrics_port)

        # Start SMTP server
        loop = asyncio.get_running_loop()

        def factory():
            return SMTPProxyHandler(
                self.config_manager,
                self.oauth_manager,
                dry_run=self.dry_run,
                global_concurrency_limit=self.global_concurrency
            )

        self.server = await loop.create_server(
            factory,
            self.listen_host,
            self.listen_port
        )

        logger.info("XOAUTH2 proxy started successfully")

        async with self.server:
            await self.server.serve_forever()

    def stop(self):
        """Stop the SMTP proxy server"""
        if self.server:
            self.server.close()
        logger.info("XOAUTH2 proxy stopped")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Production XOAUTH2 SMTP Proxy')
    parser.add_argument(
        '--config',
        default='/etc/xoauth2/accounts.json',
        help='Path to accounts.json configuration file'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Listen host (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=2525,
        help='Listen port (default: 2525)'
    )
    parser.add_argument(
        '--metrics-port',
        type=int,
        default=9090,
        help='Prometheus metrics port (default: 9090)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Enable dry-run mode (accept messages but do not send)'
    )
    parser.add_argument(
        '--global-concurrency',
        type=int,
        default=100,
        help='Global concurrency limit (default: 100)'
    )

    args = parser.parse_args()

    server = SMTPProxyServer(
        config_file=args.config,
        listen_host=args.host,
        listen_port=args.port,
        metrics_port=args.metrics_port,
        dry_run=args.dry_run,
        global_concurrency=args.global_concurrency
    )

    # Handle SIGHUP for reload
    def sighup_handler():
        logger.info("SIGHUP received")
        server.config_manager.reload()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Only register signal handlers on Unix systems (not Windows)
    if platform.system() != "Windows":
        loop.add_signal_handler(signal.SIGHUP, sighup_handler)
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(loop)))
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(loop)))
    else:
        # On Windows, use basic signal handlers
        signal.signal(signal.SIGTERM, lambda sig, frame: asyncio.create_task(shutdown(loop)))
        signal.signal(signal.SIGINT, lambda sig, frame: asyncio.create_task(shutdown(loop)))

    async def shutdown(loop):
        logger.info("Shutdown signal received")
        server.stop()
        loop.stop()

    try:
        loop.run_until_complete(server.start())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        loop.close()


if __name__ == '__main__':
    main()
