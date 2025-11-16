"""Account manager with caching and hot-reload"""

import asyncio
import logging
from typing import Dict, Optional
from pathlib import Path

from src.accounts.models import AccountConfig
from src.config.loader import ConfigLoader

logger = logging.getLogger('xoauth2_proxy')


class AccountManager:
    """Manages accounts with in-memory caching"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.accounts: Dict[str, AccountConfig] = {}  # email -> account
        self.accounts_by_id: Dict[str, AccountConfig] = {}  # account_id -> account
        self.lock = asyncio.Lock()
        self.reload_event = asyncio.Event()

        # Email lookup cache (fast path)
        self.email_cache: Dict[str, AccountConfig] = {}

    async def load(self) -> int:
        """Load accounts from config file"""
        from src.config.loader import ConfigLoader
        accounts = ConfigLoader.load(self.config_path)

        async with self.lock:
            self.accounts = accounts
            self.accounts_by_id = {acc.account_id: acc for acc in accounts.values()}
            self.email_cache = accounts.copy()

        logger.info(f"[AccountManager] Loaded {len(self.accounts)} accounts")
        return len(self.accounts)

    async def get_by_email(self, email: str) -> Optional[AccountConfig]:
        """
        Get account by email (cached, race-condition safe)

        Args:
            email: Email address

        Returns:
            AccountConfig or None if not found
        """
        # Try cache first (lock-free - dict.get is atomic)
        cached = self.email_cache.get(email)
        if cached is not None:
            return cached

        # Cache miss - try main store (lock-free read - safe for read-mostly workload)
        # Note: Python dict reads are atomic (GIL protected), accounts rarely change
        account = self.accounts.get(email)
        if account:
            # Populate cache (atomic write)
            self.email_cache[email] = account
            return account

        return None

    async def get_by_id(self, account_id: str) -> Optional[AccountConfig]:
        """Get account by ID (lock-free read)"""
        return self.accounts_by_id.get(account_id)

    async def get_all(self) -> list[AccountConfig]:
        """Get all accounts (lock-free read)"""
        return list(self.accounts.values())

    async def verify_account(self, email: str) -> bool:
        """Verify account exists"""
        account = await self.get_by_email(email)
        return account is not None

    async def reload(self) -> int:
        """Reload accounts from config (hot-reload)"""
        try:
            accounts = ConfigLoader.load(self.config_path)

            async with self.lock:
                # Keep existing tokens for accounts that didn't change
                for email, new_account in accounts.items():
                    if email in self.accounts:
                        old_account = self.accounts[email]
                        if new_account.refresh_token == old_account.refresh_token:
                            new_account.token = old_account.token

                self.accounts = accounts
                self.accounts_by_id = {acc.account_id: acc for acc in accounts.values()}
                self.email_cache.clear()

            logger.info(f"[AccountManager] Reloaded {len(accounts)} accounts")
            self.reload_event.set()
            return len(accounts)

        except Exception as e:
            logger.error(f"[AccountManager] Reload failed: {e}")
            raise

    def get_stats(self) -> dict:
        """Get account manager statistics"""
        return {
            'total_accounts': len(self.accounts),
            'cache_size': len(self.email_cache),
            'config_path': str(self.config_path),
        }
