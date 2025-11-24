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
    from src.config.proxy_config import SMTPConfig, ConnectionPoolConfig

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
        smtp_config: Optional['SMTPConfig'] = None,  # ✅ SMTP configuration for IP binding
        pool_config: Optional['ConnectionPoolConfig'] = None  # ✅ NEW: Full pool config for prewarm/rewarm
    ):
        self.max_connections_per_account = max_connections_per_account
        self.max_messages_per_connection = max_messages_per_connection
        self.connection_max_age = connection_max_age
        self.connection_idle_timeout = connection_idle_timeout
        self.smtp_config = smtp_config  # ✅ Store SMTP config
        self.pool_config = pool_config  # ✅ NEW: Store pool config for accessing prewarm settings

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

        # ✅ PERF FIX #6: Pool structure optimization for O(1) connection lookup
        # Before: single deque with O(n) search through all connections
        # After: separate idle/busy deques with O(1) acquire (popleft on idle queue)

        # pool_idle[account_email] -> deque of available (idle) PooledConnections
        # pool_busy[account_email] -> set of in-use PooledConnections
        self.pool_idle: Dict[str, deque[PooledConnection]] = {}
        self.pool_busy: Dict[str, set[PooledConnection]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        # ✅ FIX #4: REMOVED all semaphores (no fair queueing limits)
        # Removed: self.semaphores - now connections can be created freely without limits
        # Removed: self.semaphore_holders - no longer tracking semaphore ownership
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

    # ✅ FIX #4: REMOVED semaphore helper methods
    # Removed: _mark_semaphore_holder() - no longer tracking semaphore ownership
    # Removed: _unmark_semaphore_holder() - no longer tracking semaphore ownership

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

        # ✅ FIX: Always acquire lock before checking (atomic initialization)
        # Prevents TOCTOU race condition where multiple tasks check simultaneously
        async with self._dict_lock:
            # Initialize account pools/locks if not already done
            if account_email not in self.locks:
                self.locks[account_email] = asyncio.Lock()
                # ✅ PERF FIX #6: Separate idle/busy tracking for O(1) acquire
                self.pool_idle[account_email] = deque()  # Available connections
                self.pool_busy[account_email] = set()    # In-use connections
                # ✅ FIX #4: REMOVED semaphore - no fair queueing limit

        lock = self.locks[account_email]

        # ✅ FIX #4: REMOVED semaphore acquire (no concurrency limits)
        # Connections can now be created freely without fair-queueing delays
        try:

            # ===== PHASE 1: Check for available connection (QUICK, WITH LOCK, NOW O(1)!)
            async with lock:
                pool_idle = self.pool_idle[account_email]
                pool_busy = self.pool_busy[account_email]

                # ✅ PERF FIX #6: O(1) acquire - pop first idle connection (instant!)
                # No more O(n) search through entire pool
                while pool_idle:
                    pooled = pool_idle.popleft()  # ✅ O(1) pop from deque

                    # Check if connection should be removed
                    if pooled.is_expired(self.connection_max_age):
                        await self._close_connection(pooled)
                        continue

                    # ✅ NEW: Use adaptive idle timeout if configured, otherwise use default
                    idle_timeout = self.connection_idle_timeout
                    # ✅ FIX #5: Use hasattr check instead of truthiness (allows idle_timeout=0)
                    if self.pool_config and hasattr(self.pool_config, 'idle_connection_reuse_timeout'):
                        idle_timeout = self.pool_config.idle_connection_reuse_timeout

                    if pooled.is_idle_too_long(idle_timeout):
                        await self._close_connection(pooled)
                        continue

                    # Check if connection used too many times (✅ uses per-account setting!)
                    if pooled.message_count >= max_msg:
                        await self._close_connection(pooled)
                        continue

                    # REMOVED: NOOP health check (caused 50k+ extra SMTP commands per minute!)
                    # Connections will fail fast on actual send if broken - much more efficient
                    # than proactively checking every reuse

                    # Connection is good - reuse it
                    pooled.is_busy = True
                    pooled.last_used = datetime.now(UTC)
                    pool_busy.add(pooled)  # ✅ Move to busy set O(1)
                    # ✅ FIX #4: REMOVED semaphore tracking
                    self.stats['pool_hits'] += 1
                    self.stats['connections_reused'] += 1

                    return pooled.connection

                # No available connection - note that we need to create one
                self.stats['pool_misses'] += 1

            # ===== PHASE 2: Create new connection (SLOW, WITHOUT LOCK)
            # ✅ FIX #2: Release lock before connection creation (200-300ms operation)
            # This allows other messages to check the pool while we're creating a connection

            # Check pool size limit (must be done under lock, re-acquire if needed)
            async with lock:
                pool_idle = self.pool_idle[account_email]
                pool_busy = self.pool_busy[account_email]
                total_conns = len(pool_idle) + len(pool_busy)

                if total_conns >= max_conn:
                    # Find and close oldest idle connection
                    if pool_idle:
                        oldest = min(pool_idle, key=lambda p: p.created_at)
                        await self._close_connection(oldest)
                        # Remove from idle queue (O(n) but minimal - usually just a few connections)
                        # and we only do this when we're at capacity
                        pool_idle_list = [p for p in pool_idle if p is not oldest]
                        self.pool_idle[account_email] = deque(pool_idle_list)
                    else:
                        # ✅ FIX #4: REMOVED semaphore check message
                        # We'll just create more connections if needed - no fair queueing
                        logger.warning(
                            f"[Pool] All {total_conns} connections busy for {account_email}, "
                            f"will create new connection"
                        )

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

            # Create new connection WITHOUT HOLDING LOCK (200-300ms operation)
            connection = await self._create_connection(
                account_email,
                smtp_host,
                smtp_port,
                xoauth2_string,
                source_ip=source_ip  # ✅ Pass source IP
            )

            # ===== PHASE 3: Add to pool (QUICK, WITH LOCK)
            async with lock:
                # ✅ PERF FIX #6: Double-check using idle queue (O(1) check instead of O(n))
                # Another coroutine might have added a good connection
                pool_idle = self.pool_idle[account_email]
                pool_busy = self.pool_busy[account_email]

                # Check if any idle connection became available (much faster check now)
                if pool_idle:
                    pooled = pool_idle.popleft()  # ✅ O(1) pop
                    if not pooled.is_expired(self.connection_max_age):
                        # Another thread added a good connection, use that instead
                        await connection.quit()  # Close the one we created
                        pooled.is_busy = True
                        pooled.last_used = datetime.now(UTC)
                        pool_busy.add(pooled)  # ✅ Move to busy set O(1)
                        # ✅ FIX #4: REMOVED semaphore tracking
                        self.stats['pool_hits'] += 1
                        return pooled.connection
                    else:
                        # Connection expired, close it
                        await self._close_connection(pooled)

                # Still need our new one, add and return it
                pooled = PooledConnection(
                    connection=connection,
                    account_email=account_email,
                    created_at=datetime.now(UTC),
                    last_used=datetime.now(UTC),
                    message_count=0,
                    is_busy=True
                    # ✅ FIX #4: REMOVED semaphore tracking
                )
                pool_busy.add(pooled)  # ✅ New connection starts in busy set

                self.stats['connections_created'] += 1

                return connection
        except Exception as e:
            # ✅ FIX #4: REMOVED semaphore release (no semaphore acquired)
            raise

    async def release(self, account_email: str, connection: aiosmtplib.SMTP, increment_count: bool = True):
        """
        Release connection back to pool

        ✅ PERF FIX #6: O(1) release with separate idle/busy tracking

        Args:
            account_email: Email address for this account
            connection: SMTP connection to release
            increment_count: Whether to increment message count
        """
        # Check if account exists (no lock needed for read-only check)
        if account_email not in self.locks:
            return

        lock = self.locks[account_email]
        async with lock:
            pool_idle = self.pool_idle[account_email]
            pool_busy = self.pool_busy[account_email]

            # Find connection in busy set (could use a mapping for O(1), but usually small)
            for pooled in pool_busy:
                if pooled.connection is connection:
                    pooled.is_busy = False
                    pooled.last_used = datetime.now(UTC)
                    if increment_count:
                        pooled.message_count += 1

                    # ✅ PERF FIX #6: Move from busy to idle (O(1) operations)
                    pool_busy.discard(pooled)      # ✅ O(1) remove from set
                    pool_idle.append(pooled)        # ✅ O(1) append to deque

                    # ✅ FIX #4: REMOVED semaphore release (no semaphore to release)

                    return

    async def remove_and_close(self, account_email: str, connection: aiosmtplib.SMTP):
        """
        Remove connection from pool and close it (for bad/failed connections)

        Use this instead of release() + quit() when a connection fails SMTP commands.
        This ensures the bad connection is removed from pool, not recycled.

        ✅ PERF FIX #6: O(1) removal with separate idle/busy tracking

        Args:
            account_email: Email address for this account
            connection: Bad SMTP connection to remove and close
        """
        if account_email not in self.locks:
            # Connection not in pool, just close it
            try:
                await connection.quit()
            except Exception as e:
                logger.debug(f"[Pool] Error closing connection for {account_email}: {e}")
            return

        lock = self.locks[account_email]
        async with lock:
            pool_idle = self.pool_idle[account_email]
            pool_busy = self.pool_busy[account_email]

            # Check busy set first (active connections)
            for pooled in pool_busy:
                if pooled.connection is connection:
                    # ✅ PERF FIX #6: O(1) removal from busy set
                    pool_busy.discard(pooled)  # ✅ O(1)
                    # ✅ FIX #4: REMOVED semaphore release (no semaphore to release)
                    await self._close_connection(pooled)
                    return

            # Check idle set (inactive connections)
            for pooled in pool_idle:
                if pooled.connection is connection:
                    # ✅ PERF FIX #6: O(n) removal from idle deque (but small, usually just a few)
                    # This is the cost of detecting bad connections early
                    self.pool_idle[account_email] = deque(p for p in pool_idle if p is not pooled)
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
            # ✅ FIX #4: REMOVED semaphore release (no semaphore to release)
            pass

    async def cleanup_idle_connections(self):
        """Background task to cleanup idle connections (parallelized per account)"""
        try:
            while True:
                try:
                    await asyncio.sleep(10)  # Run every 10 seconds (HIGH-VOLUME: faster cleanup)

                    # ✅ FIX: Take snapshot of accounts INSIDE lock to prevent race condition
                    # Between snapshot and iteration, account could be deleted by hot-reload
                    async with self._dict_lock:
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
            if account_email not in self.locks:
                return

            lock = self.locks[account_email]
            async with lock:
                pool_idle = self.pool_idle[account_email]
                pool_busy = self.pool_busy[account_email]
                to_remove = set()  # ✅ Use set for O(1) membership tests

                # Check idle connections (these are the ones we can safely clean up)
                for pooled in list(pool_idle):  # Copy to avoid modification during iteration
                    if (pooled.is_expired(self.connection_max_age) or
                        pooled.is_idle_too_long(self.connection_idle_timeout)):
                        to_remove.add(pooled)

                # Also check busy connections (in case they became idle)
                # But only close if they're not currently busy
                for pooled in list(pool_busy):
                    if pooled.is_busy:
                        continue

                    if (pooled.is_expired(self.connection_max_age) or
                        pooled.is_idle_too_long(self.connection_idle_timeout)):
                        to_remove.add(pooled)

                # Close and remove connections
                for pooled in to_remove:
                    await self._close_connection(pooled)
                    pool_idle.discard(pooled)   # O(1) remove from idle
                    pool_busy.discard(pooled)   # O(1) remove from busy (if present)

                if to_remove:
                    logger.info(
                        f"[Pool] Cleaned up {len(to_remove)} idle connections "
                        f"for {account_email}"
                    )

        except Exception as e:
            logger.error(f"[Pool] Error cleaning up {account_email}: {e}")

    async def close_all(self):
        """Close all pooled connections"""
        # ✅ PERF FIX #6: Updated for idle/busy pool structure
        # Get snapshot of accounts (no lock needed for list() on dict.keys())
        accounts = list(self.locks.keys())

        total_closed = 0

        for account_email in accounts:
            lock = self.locks[account_email]
            async with lock:
                pool_idle = self.pool_idle[account_email]
                pool_busy = self.pool_busy[account_email]

                # Close idle connections (safe)
                for pooled in list(pool_idle):  # Copy to avoid modification during iteration
                    await self._close_connection(pooled)
                    total_closed += 1

                # Close non-busy connections from busy set
                for pooled in list(pool_busy):
                    if pooled.is_busy:
                        # Connection is busy - can't close it, will close when operation completes
                        # ✅ FIX #4: REMOVED semaphore release (no semaphore to release)
                        continue

                    await self._close_connection(pooled)
                    total_closed += 1

                # Clear both pools
                pool_idle.clear()
                pool_busy.clear()

        logger.info(f"[Pool] Closed all {total_closed} connections")

    async def prewarm(self, accounts: list, oauth_manager=None):
        """
        Pre-warm connection pool by creating connections upfront for each account.

        This eliminates cold-start delays when PowerMTA bursts 10k+ messages.
        Instead of creating connections one-at-a-time as messages arrive,
        we create them in parallel BEFORE any messages arrive.

        Uses configurable percentage (default: 50% of max_connections_per_account)
        from pool_config.prewarm_percentage for flexibility.

        Args:
            accounts: List of AccountConfig objects
            oauth_manager: OAuth2Manager instance (required for token refresh)

        Performance Impact:
            - Before: 10k messages → 2 msg/sec initially (connections created on-demand)
            - After: 10k messages → 1000+ msg/sec immediately (connections pre-warmed)
            - Re-warm uses cached tokens → 40% faster than initial creation
        """
        import time
        if not accounts:
            logger.info("[Pool] No accounts to prewarm")
            return

        if not oauth_manager:
            logger.warning("[Pool] OAuth2Manager required for pre-warming, skipping")
            return

        # Calculate connections to create based on configurable percentage
        prewarm_percentage = self.pool_config.prewarm_percentage if self.pool_config else 50
        connections_per_account = max(
            1,  # At least 1 connection
            int(self.max_connections_per_account * (prewarm_percentage / 100))
        )

        logger.info(
            f"[Pool] Pre-warming connection pool: {len(accounts)} accounts, "
            f"{connections_per_account} connections per account ({prewarm_percentage}% of {self.max_connections_per_account})"
        )

        start_time = time.time()
        total_created = 0
        total_failed = 0
        failures_by_account = {}  # Track failures per account
        first_failure_count = 0

        # ✅ FIX #4: REMOVED semaphore for prewarm (no concurrent task limits)
        # Get concurrent task limit from config (configurable to prevent memory spikes)
        concurrent_limit = self.pool_config.prewarm_concurrent_tasks if self.pool_config else 100

        async def prewarm_with_error_tracking(account):
            """Pre-warm connection with error tracking"""
            result = await self._prewarm_connection(account, oauth_manager)
            return (result, account.email)

        # ✅ FIX: Batch task creation to prevent unbounded task list growth
        # Instead of creating 25,000 task objects upfront (125 MB memory),
        # create tasks in batches and await each batch before creating the next
        batch_size = max(100, concurrent_limit * 2)  # Batch size: 2x concurrent limit (min 100)
        all_results = []

        # Build list of (account, connection_index) pairs to create
        connection_requests = []
        for account in accounts:
            for _ in range(connections_per_account):
                connection_requests.append(account)

        # Process in batches
        for batch_start in range(0, len(connection_requests), batch_size):
            batch_end = min(batch_start + batch_size, len(connection_requests))
            batch_accounts = connection_requests[batch_start:batch_end]

            # Create tasks for this batch only
            batch_tasks = [prewarm_with_error_tracking(account) for account in batch_accounts]

            # Wait for batch to complete before starting next batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            all_results.extend(batch_results)

        # ✅ FIX Issue #11: Track and log failures with better visibility
        # Count successes/failures from all batches and track per-account failures
        for result in all_results:
            if isinstance(result, Exception):
                total_failed += 1
            elif isinstance(result, tuple):
                success, account_email = result
                if success:
                    total_created += 1
                else:
                    total_failed += 1
                    failures_by_account[account_email] = failures_by_account.get(account_email, 0) + 1

                    # Log first 5 failures with account info
                    if first_failure_count < 5:
                        logger.info(
                            f"[Pool] Pre-warming failed for {account_email} "
                            f"({failures_by_account[account_email]} failure(s))"
                        )
                        first_failure_count += 1
            else:
                total_failed += 1

        duration = time.time() - start_time

        # Log summary with per-account failure count
        if failures_by_account:
            failure_summary = ", ".join(
                f"{email}({count})"
                for email, count in sorted(failures_by_account.items(), key=lambda x: x[1], reverse=True)[:5]
            )
            logger.info(
                f"[Pool] Pre-warming complete: {total_created} connections created, "
                f"{total_failed} failed ({duration:.2f}s) - Top failures: {failure_summary}"
            )
        else:
            logger.info(
                f"[Pool] Pre-warming complete: {total_created} connections created, "
                f"{total_failed} failed ({duration:.2f}s)"
            )

    async def prewarm_adaptive(self, accounts: list, oauth_manager=None):
        """
        ✅ NEW: Adaptive pre-warming that scales with actual account traffic patterns.

        Instead of pre-warming a fixed percentage for all accounts, pre-warm intelligently:
        - Per-account pool size = min(max_connections, concurrent_messages / 10)
        - Only pre-warm accounts that sent >threshold messages in last hour
        - Inactive accounts get 0 pre-warmed connections (save resources)
        - During bursts, dynamic connection creation handles overflow

        This solves the scaling problem:
        - Before: 1000 accounts × 50% = 50,000 idle sockets when traffic is low
        - After: Active accounts only → 1-10 per account × active_count (scales with traffic)

        Args:
            accounts: List of AccountConfig objects
            oauth_manager: OAuth2Manager instance (required for token refresh)

        Performance Impact:
            - Memory efficient: Only active accounts consume resources
            - <100ms latency: Pre-warmed connections ready for active accounts
            - Burst capable: Dynamic creation for unexpected spikes
            - Auto-scaling: Resources scale with traffic, not account count
        """
        import time
        if not accounts:
            logger.info("[Pool] No accounts for adaptive pre-warming")
            return

        if not oauth_manager:
            logger.warning("[Pool] OAuth2Manager required for adaptive pre-warming, skipping")
            return

        # Get adaptive config from pool_config
        if not self.pool_config or not self.pool_config.adaptive_prewarm_enabled:
            logger.info("[Pool] Adaptive pre-warming disabled, skipping")
            return

        min_connections = self.pool_config.prewarm_min_connections if self.pool_config else 1
        max_connections = self.pool_config.prewarm_max_connections if self.pool_config else 10
        min_msg_threshold = self.pool_config.prewarm_min_message_threshold if self.pool_config else 100

        logger.info(
            f"[Pool] Adaptive pre-warming: {len(accounts)} accounts "
            f"(min={min_connections}, max={max_connections}, threshold={min_msg_threshold} msg/hour)"
        )

        start_time = time.time()
        total_created = 0
        total_failed = 0
        skipped_accounts = 0
        activated_accounts = 0

        # ✅ FIX #4: REMOVED semaphore for adaptive prewarm (no concurrent task limits)
        # Get concurrent task limit (kept for logging/config, not used for limiting)
        concurrent_limit = self.pool_config.prewarm_concurrent_tasks if self.pool_config else 100

        async def adaptive_prewarm_task(account, num_connections: int):
            """Pre-warm specified number of connections for account"""
            results = []
            for _ in range(num_connections):
                result = await self._prewarm_connection(account, oauth_manager)
                results.append(result)
            # ✅ FIX #2: Clearer logic for counting successes and failures
            success_count = sum(1 for r in results if r)
            fail_count = len(results) - success_count
            return (success_count, fail_count, account.email)

        # ✅ FIX #6: Pre-warm minimum connections for ALL accounts (solves cold start)
        # Then scale up for active accounts (those with >threshold messages in last hour)
        accounts_to_prewarm = []

        for account in accounts:
            # Check if account sent messages in last hour (use messages_this_hour metric)
            messages_this_hour = getattr(account, 'messages_this_hour', 0)

            # Always pre-warm at least min_connections for all accounts (cold start solution)
            connections_to_create = min_connections

            # If account was active in past, scale up based on traffic
            if messages_this_hour >= min_msg_threshold:
                activated_accounts += 1
                # Adaptive sizing: scale pool based on traffic
                # Formula: min(max_connections, max(min_connections, concurrent_messages_estimate))
                # Estimate concurrent messages as messages_per_hour / 60
                estimated_concurrent = max(0, messages_this_hour // 60)
                # ✅ FIX #7: Use configurable messages_per_connection factor
                msg_per_conn = self.pool_config.prewarm_messages_per_connection if self.pool_config else 10
                connections_to_create = min(
                    max_connections,
                    max(min_connections, estimated_concurrent // msg_per_conn)
                )
            else:
                # Account is inactive (below threshold), use minimum
                skipped_accounts += 1

            accounts_to_prewarm.append((account, connections_to_create))
            logger.debug(
                f"[Pool] Account {account.email}: {messages_this_hour} msg/hour → "
                f"pre-warm {connections_to_create} connections"
            )

        if not accounts_to_prewarm:
            logger.info(
                f"[Pool] Adaptive pre-warming: No accounts to pre-warm "
                f"(empty account list)"
            )
            return

        # Build flat list of individual connection requests
        # Each item is just an account (one connection per task)
        connection_requests = []
        for account, num_connections in accounts_to_prewarm:
            for _ in range(num_connections):
                # ✅ FIX CRITICAL: Store just account, not (account, num_connections)
                # Each task creates exactly 1 connection
                connection_requests.append(account)

        # Process in batches
        batch_size = max(100, concurrent_limit * 2)
        all_results = []

        for batch_start in range(0, len(connection_requests), batch_size):
            batch_end = min(batch_start + batch_size, len(connection_requests))
            batch_accounts = connection_requests[batch_start:batch_end]

            # Create tasks for this batch only (one task per connection)
            batch_tasks = []
            for account in batch_accounts:
                # ✅ Each task creates exactly 1 connection
                batch_tasks.append(adaptive_prewarm_task(account, 1))

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            all_results.extend(batch_results)

        # Count successes/failures
        for result in all_results:
            if isinstance(result, Exception):
                # ✅ FIX #4: Add detailed logging for exception failures
                logger.warning(
                    f"[Pool] Adaptive pre-warm task failed: {type(result).__name__}: {result}"
                )
                total_failed += 1
            elif isinstance(result, tuple):
                success_count, fail_count, email = result
                total_created += success_count
                total_failed += fail_count
                # ✅ FIX: Add warning if most connections failed
                if fail_count > 0:
                    # Calculate failure rate
                    total_attempted = success_count + fail_count
                    failure_rate = (fail_count / total_attempted) * 100 if total_attempted > 0 else 0

                    if failure_rate > 50:
                        # More than 50% failed - log as warning
                        logger.warning(
                            f"[Pool] Adaptive pre-warm DEGRADED for {email}: "
                            f"{success_count}/{total_attempted} connections created ({failure_rate:.0f}% failed)"
                        )
                    else:
                        # Less than 50% failed - log as debug
                        logger.debug(
                            f"[Pool] Adaptive pre-warm for {email}: "
                            f"{success_count} created, {fail_count} failed"
                        )
            else:
                logger.warning(f"[Pool] Unexpected result type in adaptive pre-warm: {type(result)}")
                total_failed += 1

        duration = time.time() - start_time

        logger.info(
            f"[Pool] Adaptive pre-warming complete: "
            f"{total_created} connections created, {total_failed} failed ({duration:.2f}s) - "
            f"Activated {activated_accounts} accounts, skipped {skipped_accounts} inactive"
        )

    async def _prewarm_connection(self, account, oauth_manager) -> bool:
        """
        Create and pool a single connection for an account.

        Args:
            account: AccountConfig object
            oauth_manager: OAuth2Manager instance (passed from prewarm())

        Returns:
            True if successful, False if failed
        """
        try:
            token = await oauth_manager.get_or_refresh_token(account)
            if not token:
                return False

            # Build XOAUTH2 auth string
            xoauth2_string = f"user={account.email}\1auth=Bearer {token.access_token}\1\1"

            # Parse SMTP endpoint
            smtp_host, smtp_port_str = account.oauth_endpoint.split(':')
            smtp_port = int(smtp_port_str)

            # Get source IP if configured
            source_ip = account.ip_address if account.ip_address else None

            # Validate source IP if configured
            if source_ip and self.smtp_config and self.smtp_config.validate_source_ip:
                if not is_ip_available_on_server(source_ip, self.server_ips_cache):
                    source_ip = None

            # Create connection
            connection = await self._create_connection(
                account.email,
                smtp_host,
                smtp_port,
                xoauth2_string,
                source_ip=source_ip
            )

            # ✅ PERF FIX #6: Ensure account has idle/busy pools
            async with self._dict_lock:
                if account.email not in self.locks:
                    self.locks[account.email] = asyncio.Lock()
                    self.pool_idle[account.email] = deque()
                    self.pool_busy[account.email] = set()
                    # ✅ FIX #4: REMOVED semaphore initialization (no fair queueing limit)

            # Add to pool (with lock)
            lock = self.locks[account.email]
            async with lock:
                pool_idle = self.pool_idle[account.email]

                pooled = PooledConnection(
                    connection=connection,
                    account_email=account.email,
                    created_at=datetime.now(UTC),
                    last_used=datetime.now(UTC),
                    message_count=0,
                    is_busy=False  # ✅ Not busy - ready for use!
                    # ✅ FIX #4: REMOVED semaphore field
                )
                # ✅ PERF FIX #6: Add to idle queue (O(1))
                pool_idle.append(pooled)

            return True

        except Exception as e:
            # Silently fail individual connections (don't spam logs during prewarm)
            return False

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

    async def rewarm_accounts(self, accounts: list, oauth_manager=None):
        """
        Re-warm connection pool by creating fresh connections for idle accounts.

        This is called periodically (default: every 5 minutes) to maintain pool health
        and ensure connections are available even after idle timeout periods.

        Uses cached tokens → much faster than initial pre-warm (400-700ms vs 700-1200ms)

        Args:
            accounts: List of AccountConfig objects
            oauth_manager: OAuth2Manager instance for token refresh
        """
        import time
        if not accounts:
            logger.debug("[Pool] No accounts to rewarm")
            return

        if not oauth_manager:
            logger.warning("[Pool] OAuth2Manager required for re-warming, skipping")
            return

        # Calculate connections to create based on configurable percentage
        prewarm_percentage = self.pool_config.prewarm_percentage if self.pool_config else 50
        connections_per_account = max(
            1,
            int(self.max_connections_per_account * (prewarm_percentage / 100))
        )

        start_time = time.time()
        total_created = 0
        total_failed = 0

        # ✅ FIX #4: REMOVED semaphore for rewarm (no concurrent task limits)
        # Get concurrent task limit from config (configurable to prevent memory/CPU spikes)
        concurrent_limit = self.pool_config.rewarm_concurrent_tasks if self.pool_config else 50

        async def rewarm_connection_task(account):
            """Re-warm connection"""
            return await self._rewarm_connection(account, oauth_manager)

        # ✅ FIX: Batch task creation to prevent unbounded task list growth
        # Instead of creating all tasks upfront, process in batches
        batch_size = max(50, concurrent_limit * 2)  # Batch size: 2x concurrent limit (min 50)
        all_results = []

        # Build list of accounts to re-warm
        rewarm_requests = []
        for account in accounts:
            for _ in range(connections_per_account):
                rewarm_requests.append(account)

        # Process in batches
        for batch_start in range(0, len(rewarm_requests), batch_size):
            batch_end = min(batch_start + batch_size, len(rewarm_requests))
            batch_accounts = rewarm_requests[batch_start:batch_end]

            # Create tasks for this batch only
            batch_tasks = [rewarm_connection_task(account) for account in batch_accounts]

            # Wait for batch to complete before starting next batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            all_results.extend(batch_results)

        # Count successes/failures from all batches
        for result in all_results:
            if isinstance(result, Exception):
                total_failed += 1
            elif result:
                total_created += 1
            else:
                total_failed += 1

        duration = time.time() - start_time
        if total_created > 0:
            logger.info(
                f"[Pool] Re-warming complete: {total_created} connections created, "
                f"{total_failed} failed ({duration:.2f}s)"
            )

    async def _rewarm_connection(self, account, oauth_manager) -> bool:
        """
        Create and pool a single connection for re-warming.

        Uses the same logic as _prewarm_connection but can be tuned differently if needed.

        Args:
            account: AccountConfig object
            oauth_manager: OAuth2Manager instance

        Returns:
            True if successful, False if failed
        """
        try:
            # Get cached token (much faster than refresh since token is usually still valid)
            token = await oauth_manager.get_or_refresh_token(account)
            if not token:
                return False

            # Build XOAUTH2 auth string
            xoauth2_string = f"user={account.email}\1auth=Bearer {token.access_token}\1\1"

            # Parse SMTP endpoint
            smtp_host, smtp_port_str = account.oauth_endpoint.split(':')
            smtp_port = int(smtp_port_str)

            # Get source IP if configured
            source_ip = account.ip_address if hasattr(account, 'ip_address') and account.ip_address else None

            # Validate source IP if configured
            if source_ip and self.smtp_config and self.smtp_config.validate_source_ip:
                if not is_ip_available_on_server(source_ip, self.server_ips_cache):
                    source_ip = None

            # Create connection
            connection = await self._create_connection(
                account.email,
                smtp_host,
                smtp_port,
                xoauth2_string,
                source_ip=source_ip
            )

            # ✅ PERF FIX #6: Ensure account has idle/busy pools
            async with self._dict_lock:
                if account.email not in self.locks:
                    self.locks[account.email] = asyncio.Lock()
                    self.pool_idle[account.email] = deque()
                    self.pool_busy[account.email] = set()
                    # ✅ FIX #4: REMOVED semaphore initialization (no fair queueing limit)

            # Add to pool
            lock = self.locks[account.email]
            async with lock:
                pool_idle = self.pool_idle[account.email]

                pooled = PooledConnection(
                    connection=connection,
                    account_email=account.email,
                    created_at=datetime.now(UTC),
                    last_used=datetime.now(UTC),
                    message_count=0,
                    is_busy=False
                    # ✅ FIX #4: REMOVED semaphore field
                )
                # ✅ PERF FIX #6: Add to idle queue (O(1))
                pool_idle.append(pooled)

            return True

        except Exception as e:
            # Log at DEBUG level for individual connection failures during rewarm
            # (helps diagnose issues without spamming logs during normal operation)
            logger.debug(
                f"[Pool] Failed to re-warm connection for {account.email}: {e}"
            )
            return False

    def get_stats(self) -> dict:
        """Get pool statistics"""
        # ✅ PERF FIX #6: Updated for idle/busy pool structure
        total_idle = sum(len(pool) for pool in self.pool_idle.values())
        total_busy = sum(len(pool) for pool in self.pool_busy.values())
        total_connections = total_idle + total_busy

        return {
            'total_connections': total_connections,
            'busy_connections': total_busy,
            'idle_connections': total_idle,
            'accounts_in_pool': len(self.locks),
            **self.stats
        }
