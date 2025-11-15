"""HTTP connection pooling for OAuth2 requests"""

import asyncio
import logging
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger('xoauth2_proxy')


class HTTPSessionPool:
    """Singleton HTTP session pool for OAuth2 requests"""

    _instance: Optional['HTTPSessionPool'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self, max_retries: int = 3, timeout: int = 10):
        """Initialize HTTP session with connection pooling"""
        if self._initialized:
            return

        # Create session with connection pooling
        self.session = requests.Session()
        self.session.timeout = timeout

        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["POST", "GET"]
        )

        # Configure adapters for http and https
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._initialized = True
        logger.info("[HTTPPool] HTTP session pool initialized")

    async def close(self):
        """Close session"""
        if hasattr(self, 'session') and self.session:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.session.close)
            self._initialized = False
            logger.info("[HTTPPool] HTTP session closed")

    def get_session(self) -> requests.Session:
        """Get HTTP session"""
        if not hasattr(self, 'session') or not self.session:
            raise RuntimeError("HTTP session not initialized")
        return self.session

    async def post(self, url: str, data: dict, timeout: int = 10) -> requests.Response:
        """Make POST request"""
        loop = asyncio.get_running_loop()
        session = self.get_session()

        response = await loop.run_in_executor(
            None,
            lambda: session.post(url, data=data, timeout=timeout)
        )
        return response

    def get_stats(self) -> dict:
        """Get pool statistics"""
        if not hasattr(self, 'session'):
            return {'status': 'not_initialized'}

        return {
            'status': 'initialized',
            'timeout': getattr(self.session, 'timeout', None),
        }


# Singleton instance
http_pool = HTTPSessionPool()
