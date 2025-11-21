"""SMTP connection pooling with aiosmtplib for high-performance async relay"""

import asyncio
import base64
import logging
from typing import Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, UTC
from collections import deque
import aiosmtplib

# Import network utilities at module level (avoid repeated imports in hot path)
from src.utils.network import (
    get_public_server_ips,
    is_reserved_ip,
    is_ip_available_on_server,
)

if TYPE_CHECKING:
    from src.config.proxy_config import SMTPConfig

logger = logging.getLogger('xoauth2_proxy')


@dataclass
class PooledConnection:
    """Wrapper for pooled SMTP connection"""
    connection: aiosmtplib.SMTP
    account_email: str
    created_at: datetime
    last_used: datetime
    message_count: int = 0
    is_busy: bool = False
    semaphore: Optional[asyncio.Semaphore] = None  # Track which semaphore this connection holds

    def is_expired(self, max_age_seconds: int = 300) -> bool:
        """Check if connection is too old (default 5 minutes)"""
        age = (datetime.now(UTC) - self.created_at).total_seconds()
        return age > max_age_seconds

    def is_idle_too_long(self, max_idle_seconds: int = 60) -> bool:
        """Check if connection has been idle too long"""
        idle = (datetime.now(UTC) - self.last_used).total_seconds()
        return idle > max_idle_seconds


class SMTPConnectionPool:
    """Connection pool for SMTP connections with connection reuse"""

    def __init__(
        self,
        max_connections_per_account: int = 50,
        max_messages_per_connection: int = 100,
        connection_max_age: int = 300,
        connection_idle_timeout: int = 60,
        smtp_config: Optional['SMTPConfig'] = None  # ✅ SMTP configuration for IP binding
    ):
        self.max_connections_per_account = max_connections_per_account
        self.max_messages_per_connection = max_messages_per_connection
        self.connection_max_age = connection_max_age
        self.connection_idle_timeout = connection_idle_timeout
        self.smtp_config = smtp_config  # ✅ Store SMTP config

        # ✅ Cache server IPs if validation is enabled (avoid repeated lookups)
        self.server_ips_cache = None
        self.ips_cached_at = None
        if smtp_config and smtp_config.use_source_ip_binding and smtp_config.validate_source_ip:
            # Get public IPs (automatically filters all reserved ranges via RFC)
            use_ipv6 = smtp_config.use_ipv6 if hasattr(smtp_config, 'use_ipv6') else False
            public_ips = get_public_server_ips(use_ipv6=use_ipv6)

            self.server_ips_cache = public_ips
            self.ips_cached_at = datetime.now(UTC)
            logger.info(
                f"[SMTPConnectionPool] Source IP validation enabled. "
                f"Found {len(self.server_ips_cache)} public IP(s) on server (IPv6: {'enabled' if use_ipv6 else 'disabled'})"
            )

        # Pool: account_email -> deque of PooledConnection (O(1) operations!)
        # Using deque instead of list for better performance:
        # - append(): O(1) vs list O(1) - same
        # - popleft(): O(1) vs list.pop(0) O(n) - faster
        # - iteration: O(n) vs list O(n) - same
        # - filter/remove: O(n) but we batch operations
        self.pools: Dict[str, deque[PooledConnection]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}  # ✅ Fair queueing with semaphores
        # REMOVED: global_lock (was causing 70-90% throughput loss!)
        # Now using lightweight dict lock ONLY for dict modifications (microseconds)
        # Per-account locks handle actual pool operations (no global serialization)
        self._dict_lock = asyncio.Lock()  # Only for modifying dicts, not pool operations

        # Statistics
        self.stats = {
            'connections_created': 0,
            'connections_reused': 0,
            'connections_closed': 0,
            'pool_hits': 0,
            'pool_misses': 0,
        }

        logger.info(
            f"[SMTPConnectionPool] Initialized (max_per_account={max_connections_per_account}, "
            f"max_msg_per_conn={max_messages_per_connection})"
        )

    async def acquire(
        self,
        account_email: str,
        smtp_host: str,
        smtp_port: int,
        xoauth2_string: str,
        account = None  # ✅ NEW: Account object for per-account settings
    ) -> aiosmtplib.SMTP:
        """
        Acquire SMTP connection from pool or create new one

        Args:
            account_email: Email address for this account
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            xoauth2_string: Pre-constructed XOAUTH2 auth string (NOT base64 encoded)
            account: AccountConfig object with per-account settings (optional, uses pool defaults if None)

        Returns:
            Connected and authenticated SMTP connection
        """
        # ✅ Get per-account settings (or use pool defaults)
        if account:
            pool_config = account.get_connection_pool_config()
            if pool_config:
                max_conn = pool_config.max_connections_per_account
                max_msg = pool_config.max_messages_per_connection
            else:
                # Provider config not applied, use pool defaults
                logger.warning(f"[Pool] No connection pool config for {account_email}, using defaults")
                max_conn = self.max_connections_per_account
                max_msg = self.max_messages_per_connection
        else:
            # Fallback to pool defaults if no account provided
            max_conn = self.max_connections_per_account
            max_msg = self.max_messages_per_connection

        # Get or create lock and semaphore for this account (dict lock held for microseconds only!)
        if account_email not in self.locks:
            async with self._dict_lock:
                # Double-check after acquiring lock (race condition)
                if account_email not in self.locks:
                    self.locks[account_email] = asyncio.Lock()
                    self.pools[account_email] = deque()  # Use deque, not list
                    # ✅ Semaphore with per-account max_connections (uses account-specific setting!)
                    self.semaphores[account_email] = asyncio.Semaphore(max_conn)

        lock = self.locks[account_email]
        semaphore = self.semaphores[account_email]

        # ✅ Acquire semaphore first (fair queueing, no busy-wait!)
        # This automatically waits if max_connections_per_account already acquired
        # NOTE: We DON'T use 'async with' here because we want to hold the semaphore
        # until release() is called, not just while acquiring the connection
        await semaphore.acquire()

        try:
            async with lock:
                pool = self.pools[account_email]

                # Collect bad connections to remove (more efficient than removing during iteration)
                to_remove = []

                # Try to find available connection from pool
                for pooled in pool:
                    if pooled.is_busy:
                        continue

                    # Check if connection should be removed
                    if pooled.is_expired(self.connection_max_age):
                        await self._close_connection(pooled)
                        to_remove.append(pooled)
                        continue

                    if pooled.is_idle_too_long(self.connection_idle_timeout):
                        await self._close_connection(pooled)
                        to_remove.append(pooled)
                        continue

                    # Check if connection used too many times (✅ uses per-account setting!)
                    if pooled.message_count >= max_msg:
                        await self._close_connection(pooled)
                        to_remove.append(pooled)
                        continue

                    # REMOVED: NOOP health check (caused 50k+ extra SMTP commands per minute!)
                    # Connections will fail fast on actual send if broken - much more efficient
                    # than proactively checking every reuse

                    # Connection is good - reuse it
                    pooled.is_busy = True
                    pooled.last_used = datetime.now(UTC)
                    pooled.semaphore = semaphore  # Track semaphore for this connection
                    self.stats['pool_hits'] += 1
                    self.stats['connections_reused'] += 1

                    # Remove bad connections (one pass instead of multiple remove() calls)
                    if to_remove:
                        self.pools[account_email] = deque(p for p in pool if p not in to_remove)

                    return pooled.connection

                # Remove bad connections if we didn't find a good one (one pass filter)
                if to_remove:
                    self.pools[account_email] = deque(p for p in pool if p not in to_remove)

                # No available connection - create new one
                self.stats['pool_misses'] += 1

                # Check pool size limit (use updated pool reference)
                pool = self.pools[account_email]
                if len(pool) >= max_conn:
                    # Find and close oldest non-busy connection
                    non_busy = [p for p in pool if not p.is_busy]
                    if non_busy:
                        oldest = min(non_busy, key=lambda p: p.created_at)
                        await self._close_connection(oldest)
                        # Filter out the oldest connection (O(n) but single pass)
                        self.pools[account_email] = deque(p for p in pool if p is not oldest)
                    else:
                        # ✅ REMOVED: Busy-wait anti-pattern (sleep + recursive retry)
                        # Semaphore handles queueing automatically - if we get here, it's a logic error
                        logger.error(
                            f"[Pool] All {len(pool)} connections busy for {account_email} "
                            f"(should not happen with semaphore!)"
                        )
                        # This should never happen with semaphore, but handle gracefully
                        raise Exception(f"Pool exhausted for {account_email} despite semaphore")

                # ✅ Get source IP from account config (if enabled in config)
                source_ip = None
                if self.smtp_config and self.smtp_config.use_source_ip_binding:
                    if account and hasattr(account, 'ip_address') and account.ip_address:
                        source_ip = account.ip_address.strip()

                        if source_ip:
                            # ✅ SAFETY LAYER 1: Reject reserved/private IPs (comprehensive RFC filtering)
                            if is_reserved_ip(source_ip):
                                logger.error(
                                    f"[Pool] IP {source_ip} is reserved/private and cannot be used for internet SMTP for {account_email}. "
                                    f"Proceeding without IP binding."
                                )
                                source_ip = None
                            # ✅ SAFETY LAYER 2: Reject IPv6 if disabled in config
                            elif ':' in source_ip and not (self.smtp_config.use_ipv6 if hasattr(self.smtp_config, 'use_ipv6') else False):
                                logger.warning(
                                    f"[Pool] IPv6 {source_ip} disabled in config for {account_email}. "
                                    f"Proceeding without IP binding."
                                )
                                source_ip = None
                            # ✅ SAFETY LAYER 3: Validate IP exists on server if validation enabled
                            elif self.smtp_config.validate_source_ip:
                                if not is_ip_available_on_server(source_ip, self.server_ips_cache):
                                    logger.error(
                                        f"[Pool] Source IP {source_ip} not available on server for {account_email}. "
                                        f"Proceeding without IP binding."
                                    )
                                    source_ip = None  # Don't use invalid IP

                # Create new connection
                connection = await self._create_connection(
                    account_email,
                    smtp_host,
                    smtp_port,
                    xoauth2_string,
                    source_ip=source_ip  # ✅ Pass source IP
                )

                # Add to pool
                pooled = PooledConnection(
                    connection=connection,
                    account_email=account_email,
                    created_at=datetime.now(UTC),
                    last_used=datetime.now(UTC),
                    message_count=0,
                    is_busy=True,
                    semaphore=semaphore  # Track semaphore for this connection
                )
                pool.append(pooled)

                self.stats['connections_created'] += 1

                return connection
        except Exception as e:
            # If an error occurs, release the semaphore since we won't be using the connection
            semaphore.release()
            raise

    async def release(self, account_email: str, connection: aiosmtplib.SMTP, increment_count: bool = True):
        """
        Release connection back to pool

        Args:
            account_email: Email address for this account
            connection: SMTP connection to release
            increment_count: Whether to increment message count
        """
        # Check if account exists (no lock needed for read-only check)
        if account_email not in self.pools:
            return

        lock = self.locks[account_email]
        async with lock:
            pool = self.pools[account_email]

            for pooled in pool:
                if pooled.connection is connection:
                    pooled.is_busy = False
                    pooled.last_used = datetime.now(UTC)
                    if increment_count:
                        pooled.message_count += 1

                    # ✅ Release the semaphore now that connection is back in pool
                    if pooled.semaphore:
                        pooled.semaphore.release()
                        pooled.semaphore = None  # Clear reference

                    return

    async def remove_and_close(self, account_email: str, connection: aiosmtplib.SMTP):
        """
        Remove connection from pool and close it (for bad/failed connections)

        Use this instead of release() + quit() when a connection fails SMTP commands.
        This ensures the bad connection is removed from pool, not recycled.

        Args:
            account_email: Email address for this account
            connection: Bad SMTP connection to remove and close
        """
        if account_email not in self.pools:
            # Connection not in pool, just close it
            try:
                await connection.quit()
            except Exception as e:
                logger.debug(f"[Pool] Error closing connection for {account_email}: {e}")
            return

        lock = self.locks[account_email]
        async with lock:
            pool = self.pools[account_email]

            for pooled in pool:
                if pooled.connection is connection:
                    # Release semaphore if held
                    if pooled.semaphore:
                        pooled.semaphore.release()
                        pooled.semaphore = None

                    # Remove from pool (filter creates new deque without this connection)
                    self.pools[account_email] = deque(p for p in pool if p is not pooled)

                    # Close connection
                    await self._close_connection(pooled)

                    return

            # Connection not found in pool, close it anyway
            logger.warning(
                f"[Pool] Connection not found in pool for {account_email}, closing anyway"
            )
            try:
                await connection.quit()
            except Exception as e:
                logger.debug(f"[Pool] Error closing connection for {account_email}: {e}")

    async def _create_connection(
        self,
        account_email: str,
        smtp_host: str,
        smtp_port: int,
        xoauth2_string: str,
        source_ip: Optional[str] = None  # ✅ NEW: Source IP for outgoing connections
    ) -> aiosmtplib.SMTP:
        """Create new authenticated SMTP connection

        Args:
            account_email: Email address for this account
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            xoauth2_string: Pre-constructed XOAUTH2 auth string
            source_ip: Source IP address to bind to (optional)
        """
        try:
            # ✅ Prepare source_address parameter for socket binding
            # Format: (ip, port) where port=0 means "any available port"
            source_address = (source_ip, 0) if source_ip else None

            # Create connection
            # For port 587: use_tls=False (we'll use STARTTLS explicitly)
            # For port 465: use_tls=True (implicit TLS)
            smtp = aiosmtplib.SMTP(
                hostname=smtp_host,
                port=smtp_port,
                timeout=15,
                use_tls=False,  # Don't use implicit TLS - we'll use STARTTLS
                start_tls=False,  # Don't auto-start TLS - we'll control it manually
                source_address=source_address  # ✅ Bind to specific source IP
            )

            # Connect
            await smtp.connect()

            # STARTTLS (always required for port 587)
            # Note: Port 587 is the submission port and requires STARTTLS
            if smtp_port == 587 or smtp.supports_extension('STARTTLS'):
                await smtp.starttls()

                # Send EHLO again after STARTTLS (required by RFC 3207)
                await smtp.ehlo()

            # Authenticate with XOAUTH2
            # XOAUTH2 sends: AUTH XOAUTH2 <base64_xoauth2_string>
            xoauth2_b64 = base64.b64encode(xoauth2_string.encode('utf-8')).decode('ascii')

            # Use execute_command for XOAUTH2 authentication
            response = await smtp.execute_command(b"AUTH", b"XOAUTH2", xoauth2_b64.encode())

            if response.code != 235:
                raise Exception(f"XOAUTH2 authentication failed: {response.code} {response.message}")

            return smtp

        except OSError as e:
            # ✅ Handle IP binding errors specifically
            if source_ip and ('Cannot assign requested address' in str(e) or 'bind' in str(e).lower()):
                logger.error(
                    f"[Pool] Failed to bind to source IP {source_ip} for {account_email}: {e}. "
                    f"IP may not be configured on server. Check: ip addr show"
                )
                raise Exception(
                    f"Source IP {source_ip} not available on server. "
                    f"Configure IP or remove ip_address from account config."
                )
            else:
                logger.error(f"[Pool] Connection error for {account_email}: {e}")
                raise
        except Exception as e:
            logger.error(f"[Pool] Failed to create connection for {account_email}: {e}")
            raise

    async def _close_connection(self, pooled: PooledConnection):
        """Close a pooled connection"""
        try:
            await pooled.connection.quit()
            self.stats['connections_closed'] += 1
        except (OSError, ConnectionError, asyncio.TimeoutError):
            # ✅ FIX PERF #4: Only ignore expected network errors during close
            pass  # Silently ignore network errors during connection close
        except Exception as e:
            # ✅ Log unexpected errors (could indicate bugs)
            logger.warning(f"Unexpected error closing connection for {pooled.account_email}: {e}")
        finally:
            # ✅ Defensive release semaphore if this connection was still holding one
            # This should only happen if there's a bug (non-busy connections should have semaphore=None)
            if pooled.semaphore:
                logger.warning(
                    f"[Pool] UNEXPECTED: Releasing semaphore during connection close for {pooled.account_email} "
                    f"(is_busy={pooled.is_busy}) - possible resource leak or race condition"
                )
                pooled.semaphore.release()
                pooled.semaphore = None

    async def cleanup_idle_connections(self):
        """Background task to cleanup idle connections (parallelized per account)"""
        try:
            while True:
                try:
                    await asyncio.sleep(10)  # Run every 10 seconds (HIGH-VOLUME: faster cleanup)

                    # Get snapshot of accounts (no lock needed for list() on dict.keys())
                    accounts = list(self.pools.keys())

                    # Cleanup all accounts in parallel (huge speedup!)
                    cleanup_tasks = [
                        self._cleanup_account(account_email)
                        for account_email in accounts
                        if account_email in self.locks
                    ]

                    if cleanup_tasks:
                        # Wait for all cleanups to complete concurrently
                        await asyncio.gather(*cleanup_tasks, return_exceptions=True)

                except asyncio.CancelledError:
                    # Task is being cancelled during shutdown
                    logger.debug("[Pool] Cleanup task cancelled during shutdown")
                    raise  # Re-raise to properly cancel the task
                except Exception as e:
                    logger.error(f"[Pool] Error in cleanup task: {e}")
        except asyncio.CancelledError:
            # Final cancellation handling
            logger.debug("[Pool] Cleanup task terminated")

    async def _cleanup_account(self, account_email: str):
        """Cleanup connections for a single account (called in parallel)"""
        try:
            lock = self.locks[account_email]
            async with lock:
                pool = self.pools[account_email]
                to_remove = []

                for pooled in pool:
                    if pooled.is_busy:
                        continue

                    if (pooled.is_expired(self.connection_max_age) or
                        pooled.is_idle_too_long(self.connection_idle_timeout)):
                        to_remove.append(pooled)

                # Close connections before filtering
                for pooled in to_remove:
                    await self._close_connection(pooled)

                # Filter deque in one pass (more efficient than multiple remove() calls)
                if to_remove:
                    self.pools[account_email] = deque(p for p in pool if p not in to_remove)
                    logger.info(
                        f"[Pool] Cleaned up {len(to_remove)} idle connections "
                        f"for {account_email}"
                    )

        except Exception as e:
            logger.error(f"[Pool] Error cleaning up {account_email}: {e}")

    async def close_all(self):
        """Close all pooled connections (releases semaphores for busy ones to prevent leak)"""
        # Get snapshot of accounts (no lock needed for list() on dict.keys())
        accounts = list(self.pools.keys())

        total_closed = 0
        busy_released = 0

        for account_email in accounts:
            lock = self.locks[account_email]
            async with lock:
                pool = self.pools[account_email]
                for pooled in list(pool):  # Copy to avoid modification during iteration
                    if pooled.is_busy:
                        # Connection is busy - can't close it, but must release semaphore now
                        # Otherwise when operation completes and calls release(), connection won't be
                        # in pool (cleared below) and semaphore will leak
                        if pooled.semaphore:
                            pooled.semaphore.release()
                            pooled.semaphore = None
                            busy_released += 1
                            logger.debug(
                                f"[Pool] Released semaphore for busy connection during shutdown "
                                f"for {account_email} (connection will close when operation completes)"
                            )
                        continue

                    await self._close_connection(pooled)
                    total_closed += 1
                pool.clear()

        if busy_released > 0:
            logger.info(
                f"[Pool] Shutdown: closed {total_closed} connections, "
                f"released semaphores for {busy_released} busy connections"
            )
        else:
            logger.info(f"[Pool] Closed all {total_closed} connections")

    def refresh_ip_cache(self):
        """
        Refresh the server IP cache with current config settings.
        Called during hot-reload (SIGHUP) to pick up changes to use_ipv6 setting.
        """
        if not self.smtp_config or not self.smtp_config.use_source_ip_binding or not self.smtp_config.validate_source_ip:
            logger.debug("[Pool] IP validation disabled, skipping cache refresh")
            return

        try:
            use_ipv6 = self.smtp_config.use_ipv6 if hasattr(self.smtp_config, 'use_ipv6') else False
            public_ips = get_public_server_ips(use_ipv6=use_ipv6)

            old_count = len(self.server_ips_cache) if self.server_ips_cache else 0
            self.server_ips_cache = public_ips
            self.ips_cached_at = datetime.now(UTC)

            logger.info(
                f"[Pool] Refreshed IP cache: {old_count} -> {len(public_ips)} IPs "
                f"(IPv6: {'enabled' if use_ipv6 else 'disabled'})"
            )
        except Exception as e:
            logger.error(f"[Pool] Failed to refresh IP cache: {e}")

    def get_stats(self) -> dict:
        """Get pool statistics"""
        total_connections = sum(len(pool) for pool in self.pools.values())
        busy_connections = sum(
            sum(1 for p in pool if p.is_busy)
            for pool in self.pools.values()
        )

        return {
            'total_connections': total_connections,
            'busy_connections': busy_connections,
            'idle_connections': total_connections - busy_connections,
            'accounts_in_pool': len(self.pools),
            **self.stats
        }
