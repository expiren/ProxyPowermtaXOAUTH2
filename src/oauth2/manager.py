"""OAuth2 token manager with pooling and caching"""

import asyncio
import logging
import json
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

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.token_cache: Dict[str, TokenCache] = {}
        self.lock = asyncio.Lock()
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
        """Initialize HTTP connection pool"""
        await http_pool.initialize()
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
        async with self.lock:
            cached = self.token_cache.get(email)
            if cached and cached.is_valid():
                return cached
            return None

    async def _cache_token(self, email: str, token: OAuthToken):
        """Cache token"""
        async with self.lock:
            self.token_cache[email] = TokenCache(token=token)
            logger.debug(f"[OAuth2Manager] Cached token for {email}")

    async def _refresh_token_internal(self, account: 'AccountConfig') -> Optional[OAuthToken]:
        """Refresh OAuth2 token with retry and circuit breaker"""
        self.metrics['refresh_attempts'] += 1

        try:
            # Use circuit breaker per provider
            breaker = await self.circuit_breaker_manager.get_or_create(
                f"oauth2_{account.provider}"
            )

            retry_config = RetryConfig(max_attempts=2)
            token = await retry_async(
                self._do_refresh_token,
                account,
                config=retry_config,
            )

            # Call through circuit breaker for next time
            await breaker.call(self._do_refresh_token, account)

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
            response = await http_pool.post(token_url, payload, timeout=self.timeout)

            if response.status_code != 200:
                error_msg = response.text[:300]
                logger.error(
                    f"[OAuth2Manager] Token refresh failed ({response.status_code}): {error_msg}"
                )

                # Parse error response
                try:
                    error_data = response.json()
                    error_code = error_data.get('error', '')

                    if error_code == 'invalid_grant':
                        raise InvalidGrant(f"Invalid refresh token for {account.email}")
                    elif response.status_code >= 500:
                        raise ServiceUnavailable(f"OAuth2 service error: {error_code}")
                except json.JSONDecodeError:
                    pass

                raise TokenRefreshError(f"HTTP {response.status_code}: {error_msg}")

            token_data = response.json()

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
        async with self.lock:
            self.token_cache.clear()
        logger.info("[OAuth2Manager] Cleaned up")
