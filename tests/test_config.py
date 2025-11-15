"""Tests for configuration module"""

import unittest
import tempfile
import json
from pathlib import Path

from src.config.settings import Settings
from src.config.loader import ConfigLoader


class TestSettings(unittest.TestCase):
    """Test Settings dataclass"""

    def test_default_settings(self):
        """Test default settings values"""
        settings = Settings()
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 2525)
        self.assertEqual(settings.metrics_port, 9090)
        self.assertEqual(settings.global_concurrency_limit, 100)
        self.assertEqual(settings.smtp_timeout, 15)
        self.assertEqual(settings.oauth2_timeout, 10)
        self.assertFalse(settings.dry_run)

    def test_custom_settings(self):
        """Test custom settings values"""
        settings = Settings(
            host="0.0.0.0",
            port=3000,
            metrics_port=8080,
            global_concurrency_limit=500,
            dry_run=True
        )
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 3000)
        self.assertEqual(settings.metrics_port, 8080)
        self.assertEqual(settings.global_concurrency_limit, 500)
        self.assertTrue(settings.dry_run)


class TestConfigLoader(unittest.TestCase):
    """Test ConfigLoader"""

    def setUp(self):
        """Create temporary config file"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "accounts.json"

    def tearDown(self):
        """Clean up temporary directory"""
        self.temp_dir.cleanup()

    def test_load_valid_config(self):
        """Test loading valid config file"""
        accounts = [
            {
                "account_id": "test_1",
                "email": "test1@gmail.com",
                "ip_address": "192.168.1.1",
                "vmta_name": "vmta_1",
                "provider": "gmail",
                "client_id": "client_1",
                "client_secret": "secret_1",
                "refresh_token": "refresh_1"
            }
        ]
        with open(self.config_file, 'w') as f:
            json.dump(accounts, f)

        loader = ConfigLoader()
        loaded = loader.load(self.config_file)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].email, "test1@gmail.com")

    def test_load_duplicate_emails(self):
        """Test that duplicate emails are rejected"""
        accounts = [
            {
                "account_id": "test_1",
                "email": "test@gmail.com",
                "ip_address": "192.168.1.1",
                "vmta_name": "vmta_1",
                "provider": "gmail",
                "client_id": "client_1",
                "client_secret": "secret_1",
                "refresh_token": "refresh_1"
            },
            {
                "account_id": "test_2",
                "email": "test@gmail.com",
                "ip_address": "192.168.1.2",
                "vmta_name": "vmta_2",
                "provider": "gmail",
                "client_id": "client_2",
                "client_secret": "secret_2",
                "refresh_token": "refresh_2"
            }
        ]
        with open(self.config_file, 'w') as f:
            json.dump(accounts, f)

        loader = ConfigLoader()
        with self.assertRaises(ValueError):
            loader.load(self.config_file)

    def test_load_missing_file(self):
        """Test loading non-existent file"""
        loader = ConfigLoader()
        with self.assertRaises(FileNotFoundError):
            loader.load(Path("/nonexistent/path/accounts.json"))


if __name__ == '__main__':
    unittest.main()
