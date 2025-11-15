"""Configuration loader for accounts.json"""

import json
import logging
from pathlib import Path
from typing import Dict

from src.accounts.models import AccountConfig
from src.utils.exceptions import ConfigError, DuplicateAccount

logger = logging.getLogger('xoauth2_proxy')


class ConfigLoader:
    """Loads and validates accounts configuration"""

    @staticmethod
    def load(config_path: Path) -> Dict[str, AccountConfig]:
        """
        Load accounts from JSON file

        Args:
            config_path: Path to accounts.json

        Returns:
            Dict of email -> AccountConfig

        Raises:
            ConfigError: If file not found or invalid JSON
            DuplicateAccount: If duplicate accounts found
        """
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in {config_path}: {e}")

        accounts: Dict[str, AccountConfig] = {}
        seen_ids = set()

        # Handle both formats: array at root or {"accounts": [...]}
        if isinstance(data, list):
            account_list = data
        elif isinstance(data, dict):
            account_list = data.get('accounts', [])
        else:
            raise ConfigError(f"Invalid config format: expected array or object with 'accounts' key, got {type(data)}")

        for account_data in account_list:
            try:
                account = AccountConfig(**account_data)

                # Check for duplicate emails
                if account.email in accounts:
                    raise DuplicateAccount(f"Duplicate email: {account.email}")

                # Check for duplicate IDs
                if account.account_id in seen_ids:
                    raise DuplicateAccount(f"Duplicate account_id: {account.account_id}")

                accounts[account.email] = account
                seen_ids.add(account.account_id)

                logger.debug(f"[ConfigLoader] Loaded account: {account.email}")

            except TypeError as e:
                raise ConfigError(f"Missing required field: {e}")

        logger.info(f"[ConfigLoader] Loaded {len(accounts)} accounts from {config_path}")
        return accounts

    @staticmethod
    def validate_account(account: AccountConfig) -> bool:
        """Validate account configuration"""
        if not account.email or '@' not in account.email:
            raise ConfigError(f"Invalid email: {account.email}")

        if account.provider not in ['gmail', 'outlook']:
            raise ConfigError(f"Invalid provider: {account.provider}")

        if not account.client_id or not account.refresh_token:
            raise ConfigError(f"Missing OAuth2 credentials for {account.email}")

        return True
