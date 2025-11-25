"""
Mock OAuth2 Token Cache for Testing

This module provides cached/mock OAuth2 tokens for testing without real credentials.
It generates realistic-looking XOAUTH2 authentication strings that work with the proxy.

The proxy will validate these tokens as if they were real, allowing full end-to-end
testing of the SMTP flow without needing real Gmail/Outlook credentials.

Usage:
    from mock_oauth2_tokens import get_cached_access_token, generate_xoauth2_string

    # Get a cached access token
    token = get_cached_access_token('test.account1@gmail.com')

    # Generate XOAUTH2 string (base64 encoded)
    xoauth2_string = generate_xoauth2_string('test.account1@gmail.com')
"""

import base64
import time
import json
from typing import Dict, Optional
from datetime import datetime, timedelta

# Mock tokens cache - simulates what the OAuth2Manager would cache
MOCK_TOKENS_CACHE: Dict[str, Dict] = {
    'test.account1@gmail.com': {
        'access_token': 'ya29.a0AfH6SMBz1234567890abcdefghijklmnopqrstuvwxyz',
        'token_type': 'Bearer',
        'expires_in': 3599,
        'refresh_token': '1//0gxyz9876543210fedcba9876543210fedcba9876543210',
        'scope': 'https://mail.google.com/',
        'created_at': time.time(),
        'provider': 'gmail'
    },
    'test.account2@gmail.com': {
        'access_token': 'ya29.b0BeGH6SMCz9876543210abcdefghijklmnopqrstuvwx',
        'token_type': 'Bearer',
        'expires_in': 3599,
        'refresh_token': '1//0hxyz9876543210fedcba9876543210fedcba9876543210',
        'scope': 'https://mail.google.com/',
        'created_at': time.time(),
        'provider': 'gmail'
    },
    'test.account1@outlook.com': {
        'access_token': 'EwAoA8l6BAAURNvFLcaAUzrq1234567890abcdefghijklmnopqrstuvwxyz',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'refresh_token': 'M.R3_BAY.c1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJK',
        'scope': 'IMAP.AccessAsUser.All POP.AccessAsUser.All SMTP.Send',
        'created_at': time.time(),
        'provider': 'outlook'
    },
    'test.account2@outlook.com': {
        'access_token': 'EwAoA8l6BAAURNvFLcaAUzrq9876543210zyxwvutsrqponmlkjihgfedcba',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'refresh_token': 'M.R3_BAY.c9876543210zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPO',
        'scope': 'IMAP.AccessAsUser.All POP.AccessAsUser.All SMTP.Send',
        'created_at': time.time(),
        'provider': 'outlook'
    }
}


def get_cached_access_token(email: str) -> Optional[str]:
    """
    Get a cached access token for the given email.

    This simulates what the OAuth2Manager.get_access_token() would do,
    but returns a pre-cached token instead of refreshing from the provider.

    Args:
        email: Email address (must be in test accounts)

    Returns:
        Access token string, or None if email not found
    """
    if email not in MOCK_TOKENS_CACHE:
        return None

    token_data = MOCK_TOKENS_CACHE[email]

    # Check if token is expired
    created_at = token_data.get('created_at', time.time())
    expires_in = token_data.get('expires_in', 3600)
    expires_at = created_at + expires_in

    if time.time() < expires_at:
        # Token still valid
        return token_data['access_token']
    else:
        # In real code, we'd refresh here
        # For mock, just return the token (tests will work anyway)
        return token_data['access_token']


def generate_xoauth2_string(email: str) -> Optional[str]:
    """
    Generate an XOAUTH2 authentication string.

    XOAUTH2 format:
    base64("user=<email>\x01auth=Bearer <access_token>\x01\x01")

    This is what the proxy sends to Gmail/Outlook SMTP servers.

    Args:
        email: Email address (must be in test accounts)

    Returns:
        Base64-encoded XOAUTH2 string, or None if email not found
    """
    access_token = get_cached_access_token(email)
    if not access_token:
        return None

    # Build XOAUTH2 string
    xoauth2_str = f"user={email}\x01auth=Bearer {access_token}\x01\x01"

    # Encode to base64
    xoauth2_b64 = base64.b64encode(xoauth2_str.encode()).decode()

    return xoauth2_b64


def refresh_all_tokens():
    """
    Refresh all mock tokens (update their created_at timestamp).

    This simulates the proxy pre-warming tokens on startup.
    """
    current_time = time.time()
    for email, token_data in MOCK_TOKENS_CACHE.items():
        token_data['created_at'] = current_time
        # In real life, would call OAuth2 provider here
        logger.debug(f"Mock token refreshed for {email}")


def get_token_info(email: str) -> Optional[Dict]:
    """
    Get full token information for debugging/testing.

    Returns:
        Token data dictionary, or None if email not found
    """
    if email not in MOCK_TOKENS_CACHE:
        return None

    token_data = MOCK_TOKENS_CACHE[email].copy()

    # Calculate expiration time
    created_at = token_data.get('created_at', time.time())
    expires_in = token_data.get('expires_in', 3600)
    expires_at = created_at + expires_in

    token_data['expires_at'] = expires_at
    token_data['is_expired'] = time.time() > expires_at
    token_data['time_until_expiry'] = max(0, expires_at - time.time())

    return token_data


def list_available_accounts() -> list:
    """List all available test accounts"""
    return list(MOCK_TOKENS_CACHE.keys())


def is_test_account(email: str) -> bool:
    """Check if email is a test account with cached tokens"""
    return email in MOCK_TOKENS_CACHE


# Simple logging
import logging
logger = logging.getLogger('mock_oauth2')


if __name__ == '__main__':
    # Demo usage
    print("Mock OAuth2 Token Cache\n")
    print("=" * 80)

    print("\nAvailable Test Accounts:")
    for email in list_available_accounts():
        info = get_token_info(email)
        print(f"\n  {email}")
        print(f"    Provider: {info['provider']}")
        print(f"    Token: {info['access_token'][:30]}...")
        print(f"    Expires in: {info['time_until_expiry']:.0f} seconds")
        print(f"    Is expired: {info['is_expired']}")

    print("\n" + "=" * 80)
    print("\nExample XOAUTH2 Strings (for testing):")
    for email in list_available_accounts():
        xoauth2 = generate_xoauth2_string(email)
        print(f"\n  {email}:")
        print(f"    {xoauth2}")

    print("\n" + "=" * 80)
    print("\nUsage in proxy:")
    print("  from mock_oauth2_tokens import get_cached_access_token")
    print("  token = get_cached_access_token('test.account1@gmail.com')")
    print("  # Token can now be used for XOAUTH2 authentication")
