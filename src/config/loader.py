"""Configuration loader for accounts.json with proxy config integration"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from src.accounts.models import AccountConfig
from src.utils.exceptions import ConfigError, DuplicateAccount

logger = logging.getLogger('xoauth2_proxy')


class ConfigLoader:
    """Loads and validates accounts configuration with provider config merging"""

    @staticmethod
    def load(config_path: Path, proxy_config=None) -> Dict[str, AccountConfig]:
        """
        Load accounts from JSON file and merge with provider config

        Args:
            config_path: Path to accounts.json
            proxy_config: ProxyConfig instance (optional, for merging provider defaults)

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
                # Filter out comments (fields starting with _)
                filtered_data = {
                    k: v for k, v in account_data.items()
                    if not k.startswith('_')
                }

                # Validate oauth_endpoint format (must be host:port)
                oauth_endpoint = filtered_data.get('oauth_endpoint', '')
                if not oauth_endpoint or ':' not in oauth_endpoint:
                    raise ConfigError(
                        f"Invalid oauth_endpoint format (must be host:port): "
                        f"{oauth_endpoint} for account {filtered_data.get('email', 'unknown')}"
                    )

                account = AccountConfig(**filtered_data)

                # Check for duplicate emails
                if account.email in accounts:
                    raise DuplicateAccount(f"Duplicate email: {account.email}")

                # Check for duplicate IDs
                if account.account_id in seen_ids:
                    raise DuplicateAccount(f"Duplicate account_id: {account.account_id}")

                # Merge provider defaults with account-specific overrides
                if proxy_config:
                    provider_config = proxy_config.get_provider_config(account.provider)
                    account.apply_provider_config(provider_config)
                    pool_config = account.get_connection_pool_config()
                    if pool_config:
                        logger.debug(
                            f"[ConfigLoader] Applied {account.provider} config to {account.email} "
                            f"(max_connections={pool_config.max_connections_per_account}, "
                            f"max_messages={pool_config.max_messages_per_connection})"
                        )
                    else:
                        logger.warning(f"[ConfigLoader] No connection pool config for {account.email}")

                # Validate account configuration
                ConfigLoader.validate_account(account)

                accounts[account.email] = account
                seen_ids.add(account.account_id)

                logger.debug(f"[ConfigLoader] Loaded account: {account.email}")

            except TypeError as e:
                raise ConfigError(f"Missing required field in account: {e}")

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
