"""OAuth2 token manager with pooling and caching"""

import asyncio
import logging
import aiohttp
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime, timedelta, UTC

from src.oauth2.models import OAuthToken, TokenCache
from src.oauth2.exceptions import TokenRefreshError, InvalidGrant, ServiceUnavailable
from src.utils.http_pool import http_pool
from src.utils.retry import retry_async, RetryConfig
from src.utils.circuit_breaker import CircuitBreakerManager

if TYPE_CHECKING:
    from src.accounts.models import AccountConfig

logger = logging.getLogger('xoauth2_proxy')


class OAuth2Manager:
    """Manages OAuth2 token refresh with pooling and caching"""

    def __init__(
        self,
        timeout: int = 10,
        http_pool_config: Optional[Dict] = None
    ):
        self.timeout = timeout
        self.http_pool_config = http_pool_config or {}
        self.token_cache: Dict[str, TokenCache] = {}
        # REMOVED: global lock (caused 10-20% throughput loss!)
        # Now using per-email locks for token cache access
        self.cache_locks: Dict[str, asyncio.Lock] = {}
        self._dict_lock = asyncio.Lock()  # Only for modifying locks dict
        self.circuit_breaker_manager = CircuitBreakerManager()

        # Metrics
        self.metrics = {
            'refresh_attempts': 0,
            'refresh_success': 0,
            'refresh_failures': 0,
            'cache_hits': 0,
            'cache_misses': 0,
        }

    async def initialize(self):
        """Initialize HTTP connection pool with configuration"""
        # Pass config from global.http_pool settings
        await http_pool.initialize(
            timeout=self.timeout,
            total_connections=self.http_pool_config.get('total_connections', 500),
            connections_per_host=self.http_pool_config.get('connections_per_host', 100),
            dns_cache_ttl=self.http_pool_config.get('dns_cache_ttl_seconds', 300),
            connect_timeout=self.http_pool_config.get('connect_timeout_seconds', 5)
        )
        logger.info("[OAuth2Manager] Initialized")

    async def get_or_refresh_token(
        self,
        account: 'AccountConfig',
        force_refresh: bool = False
    ) -> Optional[OAuthToken]:
        """
        Get token for account (cached or refreshed)

        Args:
            account: Account configuration
            force_refresh: Force token refresh

        Returns:
            OAuthToken if successful, None if failed
        """
        # Check cache if not forcing refresh
        if not force_refresh:
            cached = await self._get_cached_token(account.email)
            if cached:
                self.metrics['cache_hits'] += 1
                return cached.token

        self.metrics['cache_misses'] += 1

        # Refresh token
        token = await self._refresh_token_internal(account)
        if token:
            await self._cache_token(account.email, token)
            account.token = token
            return token

        return None

    async def _get_cached_token(self, email: str) -> Optional[TokenCache]:
        """Get cached token if valid"""
        # Get or create per-email lock
        if email not in self.cache_locks:
            async with self._dict_lock:
                if email not in self.cache_locks:
                    self.cache_locks[email] = asyncio.Lock()

        async with self.cache_locks[email]:
            cached = self.token_cache.get(email)
            if cached and cached.is_valid():
                return cached
            return None

    async def _cache_token(self, email: str, token: OAuthToken):
        """Cache token"""
        # Get or create per-email lock
        if email not in self.cache_locks:
            async with self._dict_lock:
                if email not in self.cache_locks:
                    self.cache_locks[email] = asyncio.Lock()

        async with self.cache_locks[email]:
            self.token_cache[email] = TokenCache(token=token)
            logger.debug(f"[OAuth2Manager] Cached token for {email}")

    async def cache_verification_token(self, email: str, token_data: dict):
        """
        Cache a token obtained during verification (e.g., from AdminServer)

        Args:
            email: Account email
            token_data: Token response dict with 'access_token', 'expires_in', etc.
        """
        try:
            access_token = token_data.get('access_token')
            if not access_token:
                logger.warning(f"[OAuth2Manager] Cannot cache verification token for {email}: no access_token")
                return

            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            token = OAuthToken(
                access_token=access_token,
                expires_at=expires_at,
                refresh_token=token_data.get('refresh_token', ''),
                scope=token_data.get('scope', ''),
                token_type=token_data.get('token_type', 'Bearer')
            )

            await self._cache_token(email, token)
            logger.info(f"[OAuth2Manager] Cached verification token for {email} (expires in {expires_in}s)")

        except Exception as e:
            logger.error(f"[OAuth2Manager] Error caching verification token for {email}: {e}")

    async def _refresh_token_internal(self, account: 'AccountConfig') -> Optional[OAuthToken]:
        """Refresh OAuth2 token with retry and circuit breaker"""
        self.metrics['refresh_attempts'] += 1

        try:
            # Use circuit breaker per provider to prevent cascading failures
            # ✅ Get per-account circuit breaker config (or provider defaults)
            cb_config = account.get_circuit_breaker_config() if account else None
            breaker = await self.circuit_breaker_manager.get_or_create(
                f"oauth2_{account.provider}",
                failure_threshold=cb_config.failure_threshold if cb_config else 5,
                recovery_timeout=cb_config.recovery_timeout_seconds if cb_config else 60
            )

            # Circuit breaker wraps retry logic:
            # 1. Circuit breaker prevents calls if provider is known to be down
            # 2. Retry handles transient failures (network hiccups)
            # 3. If retry fails, circuit breaker tracks the failure
            # ✅ Use per-account retry config (or provider defaults)
            retry_cfg = account.get_retry_config() if account else None
            retry_config = RetryConfig(
                max_attempts=retry_cfg.max_attempts if retry_cfg else 2,
                backoff_factor=retry_cfg.backoff_factor if retry_cfg else 2.0,
                max_delay=retry_cfg.max_delay_seconds if retry_cfg else 30,
                jitter=retry_cfg.jitter_enabled if retry_cfg else True
            )

            # Wrap retry with circuit breaker
            token = await breaker.call(
                retry_async,
                self._do_refresh_token,
                account,
                config=retry_config,
            )

            self.metrics['refresh_success'] += 1
            return token

        except Exception as e:
            self.metrics['refresh_failures'] += 1
            logger.error(f"[OAuth2Manager] Token refresh failed for {account.email}: {e}")
            return None

    async def _do_refresh_token(self, account: 'AccountConfig') -> OAuthToken:
        """Do actual token refresh via HTTP"""
        logger.info(f"[OAuth2Manager] Refreshing token for {account.email} ({account.provider})")

        token_url = account.oauth_token_url

        # Build provider-specific payload
        if account.is_outlook:
            payload = {
                'grant_type': 'refresh_token',
                'client_id': account.client_id,
                'refresh_token': account.refresh_token,
            }
        else:  # Gmail
            payload = {
                'grant_type': 'refresh_token',
                'client_id': account.client_id,
                'client_secret': account.client_secret,
                'refresh_token': account.refresh_token,
            }

        try:
            # aiohttp-based http_pool.post() returns dict directly (or raises exception)
            token_data = await http_pool.post(token_url, payload, timeout=self.timeout)

            # Extract token info
            access_token = token_data.get('access_token')
            if not access_token:
                raise TokenRefreshError("No access_token in response")

            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            # Some providers return updated refresh token
            refresh_token = token_data.get('refresh_token', account.refresh_token)

            token = OAuthToken(
                access_token=access_token,
                expires_at=expires_at,
                refresh_token=refresh_token,
                scope=token_data.get('scope', ''),
            )

            logger.info(
                f"[OAuth2Manager] Token refreshed for {account.email} "
                f"(expires in {expires_in}s)"
            )

            # Update account if refresh token changed
            if refresh_token != account.refresh_token:
                old_short = account.refresh_token[:20] + "..."
                new_short = refresh_token[:20] + "..."
                logger.info(
                    f"[OAuth2Manager] Refresh token updated for {account.email} "
                    f"(was {old_short}, now {new_short})"
                )
                account.refresh_token = refresh_token

            return token

        except TokenRefreshError:
            raise
        except aiohttp.ClientResponseError as e:
            # HTTP error from OAuth provider
            if e.status == 400:
                raise InvalidGrant(f"Invalid refresh token for {account.email}")
            elif e.status >= 500:
                raise ServiceUnavailable(f"OAuth2 service error: HTTP {e.status}")
            raise TokenRefreshError(f"Token refresh HTTP error: {e}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Network error or timeout
            raise TokenRefreshError(f"Token refresh network error: {e}")
        except Exception as e:
            raise TokenRefreshError(f"Token refresh failed: {e}")

    def get_stats(self) -> dict:
        """Get manager statistics"""
        return {
            'metrics': self.metrics.copy(),
            'cached_tokens': len(self.token_cache),
            'circuit_breakers': self.circuit_breaker_manager.get_stats(),
        }

    async def cleanup(self):
        """Cleanup resources"""
        # No lock needed - called during shutdown only
        self.token_cache.clear()
        self.cache_locks.clear()
        # Close HTTP connection pool to prevent connection leaks
        await http_pool.close()
        logger.info("[OAuth2Manager] Cleaned up (including HTTP pool)")
