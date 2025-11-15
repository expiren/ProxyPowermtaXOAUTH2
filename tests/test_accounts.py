"""Tests for accounts module"""

import unittest
from src.accounts.models import AccountConfig


class TestAccountConfig(unittest.TestCase):
    """Test AccountConfig model"""

    def setUp(self):
        """Create a test account"""
        self.account = AccountConfig(
            account_id="test_1",
            email="test@gmail.com",
            ip_address="192.168.1.1",
            vmta_name="vmta_1",
            provider="gmail",
            client_id="client_1",
            client_secret="secret_1",
            refresh_token="refresh_1",
            oauth_endpoint="https://oauth2.googleapis.com",
            oauth_token_url="https://oauth2.googleapis.com/token"
        )

    def test_account_creation(self):
        """Test account creation"""
        self.assertEqual(self.account.account_id, "test_1")
        self.assertEqual(self.account.email, "test@gmail.com")
        self.assertEqual(self.account.provider, "gmail")

    def test_is_gmail(self):
        """Test Gmail provider detection"""
        self.assertTrue(self.account.is_gmail)

    def test_is_outlook(self):
        """Test Outlook provider detection"""
        outlook_account = AccountConfig(
            account_id="test_2",
            email="test@outlook.com",
            ip_address="192.168.1.2",
            vmta_name="vmta_2",
            provider="outlook",
            client_id="client_2",
            client_secret="secret_2",
            refresh_token="refresh_2",
            oauth_endpoint="https://login.microsoftonline.com",
            oauth_token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token"
        )
        self.assertFalse(outlook_account.is_gmail)

    def test_default_concurrency_limit(self):
        """Test default concurrency limit"""
        self.assertEqual(self.account.max_concurrent_messages, 10)
        self.assertEqual(self.account.max_messages_per_hour, 10000)

    def test_custom_concurrency_limit(self):
        """Test custom concurrency limit"""
        account = AccountConfig(
            account_id="test_3",
            email="test3@gmail.com",
            ip_address="192.168.1.3",
            vmta_name="vmta_3",
            provider="gmail",
            client_id="client_3",
            client_secret="secret_3",
            refresh_token="refresh_3",
            oauth_endpoint="https://oauth2.googleapis.com",
            oauth_token_url="https://oauth2.googleapis.com/token",
            max_concurrent_messages=50,
            max_messages_per_hour=5000
        )
        self.assertEqual(account.max_concurrent_messages, 50)
        self.assertEqual(account.max_messages_per_hour, 5000)


if __name__ == '__main__':
    unittest.main()
