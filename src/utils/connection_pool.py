"""SMTP connection pooling for performance"""

import asyncio
import smtplib
import logging
from typing import Dict, Optional, List
from datetime import datetime, UTC
from collections import defaultdict

from src.smtp.constants import DEFAULT_POOL_MIN_SIZE, DEFAULT_POOL_MAX_SIZE

logger = logging.getLogger('xoauth2_proxy')


class PooledSMTPConnection:
    """Wrapper for pooled SMTP connection"""

    def __init__(self, host: str, port: int, timeout: int = 15):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.connection: Optional[smtplib.SMTP] = None
        self.created_at: Optional[datetime] = None
        self.last_used_at: Optional[datetime] = None
        self.in_use = False

    async def connect(self) -> bool:
        """Connect to SMTP server"""
        try:
            loop = asyncio.get_running_loop()
            self.connection = await loop.run_in_executor(
                None,
                lambda: smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            )
            self.created_at = datetime.now(UTC)
            self.last_used_at = datetime.now(UTC)
            return True
        except Exception as e:
            logger.error(f"[ConnectionPool] Failed to connect to {self.host}:{self.port}: {e}")
            return False

    async def close(self):
        """Close connection"""
        if self.connection:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.connection.quit)
            except Exception as e:
                logger.warning(f"[ConnectionPool] Error closing connection: {e}")
            finally:
                self.connection = None

    def is_alive(self) -> bool:
        """Check if connection is still valid"""
        if not self.connection:
            return False
        try:
            # Send NOOP to check if connection is alive
            code, _ = self.connection.noop()
            return code == 250
        except Exception:
            return False

    def mark_used(self):
        """Mark connection as used"""
        self.last_used_at = datetime.now(UTC)

    def age_seconds(self) -> float:
        """Get connection age in seconds"""
        if not self.created_at:
            return 0
        return (datetime.now(UTC) - self.created_at).total_seconds()


class SMTPConnectionPool:
    """SMTP connection pool for upstream servers"""

    def __init__(self, min_size: int = DEFAULT_POOL_MIN_SIZE, max_size: int = DEFAULT_POOL_MAX_SIZE):
        self.min_size = min_size
        self.max_size = max_size
        self.pools: Dict[str, List[PooledSMTPConnection]] = defaultdict(list)
        self.lock = asyncio.Lock()
        self.metrics = {
            'created': 0,
            'closed': 0,
            'reused': 0,
            'failed': 0,
        }

    def _get_pool_key(self, host: str, port: int) -> str:
        """Get pool key for host:port"""
        return f"{host}:{port}"

    async def acquire(self, host: str, port: int, timeout: int = 15) -> Optional[PooledSMTPConnection]:
        """Acquire connection from pool"""
        pool_key = self._get_pool_key(host, port)

        async with self.lock:
            pool = self.pools[pool_key]

            # Try to reuse existing connection
            for conn in pool:
                if not conn.in_use and conn.is_alive():
                    conn.in_use = True
                    conn.mark_used()
                    self.metrics['reused'] += 1
                    return conn

            # Create new connection if under limit
            if len(pool) < self.max_size:
                conn = PooledSMTPConnection(host, port, timeout)
                if await conn.connect():
                    conn.in_use = True
                    pool.append(conn)
                    self.metrics['created'] += 1
                    return conn
                else:
                    self.metrics['failed'] += 1
                    return None

            # All connections in use, wait for one to be released
            logger.warning(f"[ConnectionPool] All connections in use for {pool_key}")
            return None

    async def release(self, conn: PooledSMTPConnection):
        """Release connection back to pool"""
        async with self.lock:
            conn.in_use = False

    async def close_all(self):
        """Close all connections"""
        async with self.lock:
            for pool in self.pools.values():
                for conn in pool:
                    await conn.close()
                    self.metrics['closed'] += 1
            self.pools.clear()

    async def cleanup_idle(self, idle_threshold_seconds: int = 300):
        """Close idle connections"""
        async with self.lock:
            for pool_key, pool in list(self.pools.items()):
                active_pool = []
                for conn in pool:
                    if not conn.in_use:
                        idle_time = (datetime.now(UTC) - conn.last_used_at).total_seconds()
                        if idle_time > idle_threshold_seconds:
                            await conn.close()
                            self.metrics['closed'] += 1
                            continue
                    active_pool.append(conn)
                self.pools[pool_key] = active_pool

    def get_stats(self) -> Dict:
        """Get pool statistics"""
        total_connections = sum(len(pool) for pool in self.pools.values())
        in_use = sum(1 for pool in self.pools.values() for conn in pool if conn.in_use)

        return {
            'total_connections': total_connections,
            'in_use': in_use,
            'pools': len(self.pools),
            'metrics': self.metrics.copy(),
        }
