"""HTTP connection pooling for OAuth2 requests (async with aiohttp)"""

import asyncio
import logging
from typing import Optional
import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger('xoauth2_proxy')


class HTTPSessionPool:
    """Singleton HTTP session pool for OAuth2 requests (fully async)"""

    _instance: Optional['HTTPSessionPool'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._init_lock = asyncio.Lock()
        return cls._instance

    async def initialize(
        self,
        max_retries: int = 3,
        timeout: int = 10,
        total_connections: int = 500,
        connections_per_host: int = 100,
        dns_cache_ttl: int = 300,
        connect_timeout: int = 5
    ):
        """
        Initialize HTTP session with connection pooling (thread-safe)

        Args:
            max_retries: Maximum number of retries for failed requests
            timeout: Total timeout for requests in seconds
            total_connections: Maximum total HTTP connections across all hosts
            connections_per_host: Maximum connections per host (Google/Microsoft OAuth2 endpoints)
            dns_cache_ttl: DNS cache TTL in seconds
            connect_timeout: Connection timeout in seconds
        """
        async with self._init_lock:
            if self._initialized:
                return

            # Create connector with configurable settings
            # Note: aiohttp uses connector for connection pooling
            connector = TCPConnector(
                limit=total_connections,              # Total connection limit
                limit_per_host=connections_per_host,  # Connections per host
                ttl_dns_cache=dns_cache_ttl,          # DNS cache TTL
                enable_cleanup_closed=True
            )

            # Create timeout config
            timeout_config = ClientTimeout(
                total=timeout,
                connect=connect_timeout,
                sock_read=timeout
            )

            # Create aiohttp session (fully async - no thread pool needed!)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout_config,
                raise_for_status=False  # We'll handle status codes manually
            )

            self.max_retries = max_retries
            self.timeout = timeout
            self._initialized = True

            logger.info(
                f"[HTTPPool] Async HTTP session pool initialized "
                f"(limit={total_connections}, limit_per_host={connections_per_host}, "
                f"dns_cache_ttl={dns_cache_ttl}s, timeout={timeout}s)"
            )

    async def close(self):
        """Close session (thread-safe)"""
        async with self._init_lock:
            if hasattr(self, 'session') and self.session:
                try:
                    # Close the session
                    await self.session.close()
                    # Wait for the connector to close all connections
                    # This prevents "Unclosed client session" warnings
                    await asyncio.sleep(0.5)
                    self._initialized = False
                    logger.info("[HTTPPool] Async HTTP session closed")
                except Exception as e:
                    logger.warning(f"[HTTPPool] Error during session close: {e}")
                    self._initialized = False

    def get_session(self) -> aiohttp.ClientSession:
        """Get HTTP session"""
        if not hasattr(self, 'session') or not self.session:
            raise RuntimeError("HTTP session not initialized")
        return self.session

    async def post(self, url: str, data: dict, timeout: Optional[int] = None) -> dict:
        """
        Make POST request with automatic retry (fully async)

        Returns:
            dict: Parsed JSON response

        Raises:
            aiohttp.ClientError: On network/HTTP errors after retries
        """
        session = self.get_session()
        timeout_val = timeout or self.timeout
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                async with session.post(url, data=data, timeout=timeout_val) as response:
                    # Check for retryable status codes
                    if response.status in [429, 500, 502, 503, 504] and attempt < self.max_retries:
                        wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                        logger.warning(
                            f"[HTTPPool] Retryable error {response.status}, "
                            f"retry {attempt + 1}/{self.max_retries} after {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    # Raise for non-retryable errors
                    if response.status >= 400:
                        text = await response.text()
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}: {text}"
                        )

                    # Success - parse JSON and return
                    return await response.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(
                        f"[HTTPPool] Request failed: {e}, "
                        f"retry {attempt + 1}/{self.max_retries} after {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # All retries exhausted
                    logger.error(f"[HTTPPool] Request failed after {self.max_retries} retries: {e}")
                    raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error

    def get_stats(self) -> dict:
        """Get pool statistics"""
        if not hasattr(self, 'session'):
            return {'status': 'not_initialized'}

        connector = self.session.connector
        return {
            'status': 'initialized',
            'timeout': self.timeout,
            'limit': connector.limit if connector else None,
            'limit_per_host': connector.limit_per_host if connector else None,
        }


# Singleton instance
http_pool = HTTPSessionPool()
