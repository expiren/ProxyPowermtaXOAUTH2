"""Tests for OAuth2 module"""

import unittest
import asyncio
from datetime import datetime, timedelta, UTC

from src.oauth2.models import OAuthToken, TokenCache


class TestOAuthToken(unittest.TestCase):
    """Test OAuthToken model"""

    def test_token_not_expired(self):
        """Test token that is not expired"""
        future = datetime.now(UTC) + timedelta(hours=1)
        token = OAuthToken(
            access_token="test_token",
            expires_at=future,
            refresh_token="refresh"
        )
        self.assertFalse(token.is_expired())

    def test_token_expired(self):
        """Test token that is expired"""
        past = datetime.now(UTC) - timedelta(hours=1)
        token = OAuthToken(
            access_token="test_token",
            expires_at=past,
            refresh_token="refresh"
        )
        self.assertTrue(token.is_expired())

    def test_token_expiring_soon(self):
        """Test token that will expire soon (within buffer)"""
        # Set expiry to 5 minutes from now, with 10 minute buffer
        soon = datetime.now(UTC) + timedelta(minutes=5)
        token = OAuthToken(
            access_token="test_token",
            expires_at=soon,
            refresh_token="refresh"
        )
        # Should be considered expired due to 300 second buffer
        self.assertTrue(token.is_expired(buffer_seconds=600))

    def test_token_custom_buffer(self):
        """Test token with custom buffer"""
        soon = datetime.now(UTC) + timedelta(minutes=6)
        token = OAuthToken(
            access_token="test_token",
            expires_at=soon,
            refresh_token="refresh"
        )
        # With 300 second (5 minute) buffer, should not be expired
        self.assertFalse(token.is_expired(buffer_seconds=300))


class TestTokenCache(unittest.TestCase):
    """Test TokenCache model"""

    def test_cache_creation(self):
        """Test token cache creation"""
        future = datetime.now(UTC) + timedelta(hours=1)
        token = OAuthToken(
            access_token="test_token",
            expires_at=future,
            refresh_token="refresh"
        )
        cache = TokenCache(token=token, cache_age=0)
        self.assertEqual(cache.token.access_token, "test_token")
        self.assertEqual(cache.cache_age, 0)

    def test_cache_age_increment(self):
        """Test cache age tracking"""
        future = datetime.now(UTC) + timedelta(hours=1)
        token = OAuthToken(
            access_token="test_token",
            expires_at=future,
            refresh_token="refresh"
        )
        cache = TokenCache(token=token, cache_age=100)
        self.assertEqual(cache.cache_age, 100)


if __name__ == '__main__':
    unittest.main()
