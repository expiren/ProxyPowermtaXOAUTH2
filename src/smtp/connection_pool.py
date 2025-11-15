"""SMTP connection pooling with aiosmtplib for high-performance async relay"""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import aiosmtplib

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
        connection_idle_timeout: int = 60
    ):
        self.max_connections_per_account = max_connections_per_account
        self.max_messages_per_connection = max_messages_per_connection
        self.connection_max_age = connection_max_age
        self.connection_idle_timeout = connection_idle_timeout

        # Pool: account_email -> list of PooledConnection
        self.pools: Dict[str, list[PooledConnection]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.global_lock = asyncio.Lock()

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
        xoauth2_string: str
    ) -> aiosmtplib.SMTP:
        """
        Acquire SMTP connection from pool or create new one

        Args:
            account_email: Email address for this account
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            xoauth2_string: Pre-constructed XOAUTH2 auth string (NOT base64 encoded)

        Returns:
            Connected and authenticated SMTP connection
        """
        # Get or create lock for this account
        async with self.global_lock:
            if account_email not in self.locks:
                self.locks[account_email] = asyncio.Lock()
                self.pools[account_email] = []

        lock = self.locks[account_email]

        async with lock:
            pool = self.pools[account_email]

            # Try to find available connection from pool
            for pooled in pool:
                if pooled.is_busy:
                    continue

                # Skip expired or idle connections
                if pooled.is_expired(self.connection_max_age):
                    logger.debug(f"[Pool] Connection expired for {account_email}")
                    await self._close_connection(pooled)
                    pool.remove(pooled)
                    continue

                if pooled.is_idle_too_long(self.connection_idle_timeout):
                    logger.debug(f"[Pool] Connection idle too long for {account_email}")
                    await self._close_connection(pooled)
                    pool.remove(pooled)
                    continue

                # Check if connection used too many times
                if pooled.message_count >= self.max_messages_per_connection:
                    logger.debug(
                        f"[Pool] Connection reached max messages ({pooled.message_count}) "
                        f"for {account_email}"
                    )
                    await self._close_connection(pooled)
                    pool.remove(pooled)
                    continue

                # Check if connection is still alive
                try:
                    # Quick health check with NOOP
                    await asyncio.wait_for(pooled.connection.noop(), timeout=2.0)

                    # Connection is good - reuse it
                    pooled.is_busy = True
                    pooled.last_used = datetime.now(UTC)
                    self.stats['pool_hits'] += 1
                    self.stats['connections_reused'] += 1

                    logger.debug(
                        f"[Pool] Reusing connection for {account_email} "
                        f"(msg_count={pooled.message_count}, age={int((datetime.now(UTC) - pooled.created_at).total_seconds())}s)"
                    )
                    return pooled.connection

                except (asyncio.TimeoutError, Exception) as e:
                    logger.debug(f"[Pool] Connection health check failed for {account_email}: {e}")
                    await self._close_connection(pooled)
                    pool.remove(pooled)
                    continue

            # No available connection - create new one
            self.stats['pool_misses'] += 1

            # Check pool size limit
            if len(pool) >= self.max_connections_per_account:
                # Find and close oldest non-busy connection
                non_busy = [p for p in pool if not p.is_busy]
                if non_busy:
                    oldest = min(non_busy, key=lambda p: p.created_at)
                    logger.debug(f"[Pool] Closing oldest connection for {account_email}")
                    await self._close_connection(oldest)
                    pool.remove(oldest)
                else:
                    # All connections busy - wait a bit and retry
                    logger.warning(
                        f"[Pool] All {len(pool)} connections busy for {account_email}, waiting..."
                    )
                    await asyncio.sleep(0.1)
                    # Release lock and retry
                    return await self.acquire(account_email, smtp_host, smtp_port, xoauth2_string)

            # Create new connection
            connection = await self._create_connection(
                account_email,
                smtp_host,
                smtp_port,
                xoauth2_string
            )

            # Add to pool
            pooled = PooledConnection(
                connection=connection,
                account_email=account_email,
                created_at=datetime.now(UTC),
                last_used=datetime.now(UTC),
                message_count=0,
                is_busy=True
            )
            pool.append(pooled)

            self.stats['connections_created'] += 1
            logger.info(
                f"[Pool] Created new connection for {account_email} "
                f"(pool_size={len(pool)}/{self.max_connections_per_account})"
            )

            return connection

    async def release(self, account_email: str, connection: aiosmtplib.SMTP, increment_count: bool = True):
        """
        Release connection back to pool

        Args:
            account_email: Email address for this account
            connection: SMTP connection to release
            increment_count: Whether to increment message count
        """
        async with self.global_lock:
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

                    logger.debug(
                        f"[Pool] Released connection for {account_email} "
                        f"(msg_count={pooled.message_count})"
                    )
                    return

    async def _create_connection(
        self,
        account_email: str,
        smtp_host: str,
        smtp_port: int,
        xoauth2_string: str
    ) -> aiosmtplib.SMTP:
        """Create new authenticated SMTP connection"""
        try:
            # Create connection
            smtp = aiosmtplib.SMTP(
                hostname=smtp_host,
                port=smtp_port,
                timeout=15
            )

            # Connect
            await smtp.connect()
            logger.debug(f"[Pool] Connected to {smtp_host}:{smtp_port} for {account_email}")

            # STARTTLS
            if smtp.supports_extension('STARTTLS'):
                await smtp.starttls()
                logger.debug(f"[Pool] STARTTLS completed for {account_email}")

            # Authenticate with XOAUTH2
            # aiosmtplib expects base64-encoded string for auth
            import base64
            xoauth2_b64 = base64.b64encode(xoauth2_string.encode('utf-8')).decode('ascii')

            await smtp.auth('XOAUTH2', xoauth2_b64)
            logger.info(f"[Pool] Authenticated {account_email} with XOAUTH2")

            return smtp

        except Exception as e:
            logger.error(f"[Pool] Failed to create connection for {account_email}: {e}")
            raise

    async def _close_connection(self, pooled: PooledConnection):
        """Close a pooled connection"""
        try:
            await pooled.connection.quit()
            self.stats['connections_closed'] += 1
            logger.debug(f"[Pool] Closed connection for {pooled.account_email}")
        except Exception as e:
            logger.debug(f"[Pool] Error closing connection for {pooled.account_email}: {e}")

    async def cleanup_idle_connections(self):
        """Background task to cleanup idle connections"""
        while True:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds

                async with self.global_lock:
                    accounts = list(self.pools.keys())

                for account_email in accounts:
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

                        for pooled in to_remove:
                            await self._close_connection(pooled)
                            pool.remove(pooled)

                        if to_remove:
                            logger.info(
                                f"[Pool] Cleaned up {len(to_remove)} idle connections "
                                f"for {account_email}"
                            )

            except Exception as e:
                logger.error(f"[Pool] Error in cleanup task: {e}")

    async def close_all(self):
        """Close all pooled connections"""
        async with self.global_lock:
            accounts = list(self.pools.keys())

        for account_email in accounts:
            lock = self.locks[account_email]
            async with lock:
                pool = self.pools[account_email]
                for pooled in pool:
                    await self._close_connection(pooled)
                pool.clear()

        logger.info("[Pool] Closed all connections")

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
